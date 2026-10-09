"""Streamlit 前端:数仓问数(GL_BALANCES)。

启动:双击 问数.bat,或 .venv\\Scripts\\python -m streamlit run app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import streamlit as st

import db
import llm
from ask import ANSWER_SYSTEM, SYSTEM_PROMPT, extract_sql

LEDGERS = [
    (2021, "HMPL_PRC", "CNY", "PRIMARY"),
    (2041, "HHLDHHOG_PRC", "CNY", "PRIMARY"),
    (2043, "HSPL_PRC", "CNY", "PRIMARY"),
    (2045, "HMPL_IFRS", "CNY", "SECONDARY"),
    (2047, "HMPL_US", "CNY", "SECONDARY"),
    (2049, "HHLDHHOG_IFRS", "CNY", "SECONDARY"),
    (2052, "HHLDHHOG_US", "CNY", "SECONDARY"),
    (2054, "HSPL_IFRS", "CNY", "SECONDARY"),
    (2056, "HSPL_US", "CNY", "SECONDARY"),
    (2092, "HCM_HKD_FRS", "HKD", "PRIMARY"),
    (2093, "HCM_HKD_IFRS", "HKD", "SECONDARY"),
    (2094, "HCM_HKD_US GAAP", "HKD", "SECONDARY"),
    (2098, "HCM_USD_US GAAP", "USD", "PRIMARY"),
    (2099, "HCM_USD_IFRS", "USD", "SECONDARY"),
    (2104, "HCM_GBP_UK GAAP", "GBP", "PRIMARY"),
    (2105, "HCM_GBP_IFRS", "GBP", "SECONDARY"),
    (2106, "HCM_GBP_US GAAP", "GBP", "SECONDARY"),
    (2120, "HCM_EUR_IFRS", "EUR", "PRIMARY"),
    (2122, "HCM_EUR_US GAAP", "EUR", "SECONDARY"),
    (2140, "HCM_USD_STAT", "USD", "SECONDARY"),
]

EXAMPLES = [
    "HMPL_PRC 2024年12月各币种的本币月末净余额",
    "HUTCHMED 2024年12月末,科目名包含土地使用权的本币净余额",
    "2024年全年 HMPL_PRC 每月的本币借贷发生额",
    "单体8172 和 8163 2024年末资产类净余额对比",
]

SEGMENTS = [
    ("SEGMENT1", "公司 Company", "8172", "HUTCHMED Limited"),
    ("SEGMENT2", "科目 Account", "102200", "无形资产原值-土地使用权(中期)"),
    ("SEGMENT3", "成本中心 CostCenter", "9304", "部门,共 611 个"),
    ("SEGMENT4", "产品/服务 Prod/Serv", "999", "通用"),
    ("SEGMENT5", "渠道 Channel", "00", "—"),
    ("SEGMENT6", "国家 Country", "CN0", "China"),
    ("SEGMENT7", "内部往来 InterComp", "0000", "—"),
    ("SEGMENT8", "项目 Project", "0000", "—"),
    ("SEGMENT9", "备用 Spare", "0", "—"),
]

st.set_page_config(page_title="数仓问数 · 科目余额", page_icon="📊", layout="wide")
st.title("📊 数仓问数 — GL_BALANCES(科目余额)")

with st.sidebar:
    st.caption("Oracle BITEST · ODS_EBS.GL_BALANCES · 只读账号")
    st.warning("数据截止 2025-01")
    st.divider()
    st.subheader("账套字典")
    st.dataframe(
        pd.DataFrame(LEDGERS, columns=["LEDGER_ID", "名称", "本位币", "类型"]),
        width="stretch",
        hide_index=True,
        height=430,
    )
    st.caption("命名:{主体}_{准则}。“单体8172”指公司段 SEGMENT1,不是账套。")
    st.divider()
    st.subheader("科目组合 9 段对照")
    st.dataframe(
        pd.DataFrame(SEGMENTS, columns=["段", "含义", "示例值", "中文名"]),
        width="stretch",
        hide_index=True,
        height=310,
    )
    st.caption("代码→中文名全表:DW.DW_FND_SEGMENTS_NAME(3,211 行)。问数直接用中文即可。")


def render_answer(item: dict) -> None:
    if item.get("sql"):
        with st.expander("📝 生成的 SQL", expanded=False):
            st.code(item["sql"], language="sql")
    if item.get("cols"):
        df = pd.DataFrame(item["rows"], columns=item["cols"])
        num_cfg = {
            c: st.column_config.NumberColumn(format="%,.2f")
            for c in df.columns
            if pd.api.types.is_numeric_dtype(df[c])
        }
        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            column_config=num_cfg,
            height=min(35 * (len(df) + 1) + 3, 480),
        )
        st.caption(f"共 {len(df)} 行" + ("(已截断至 100)" if len(df) == 100 else ""))
    if item.get("answer"):
        st.markdown(item["answer"])
    if item.get("error"):
        st.error(f"出错了:{item['error']}")


if "history" not in st.session_state:
    st.session_state.history = []

for item in st.session_state.history:
    with st.chat_message("user"):
        st.markdown(item["q"])
    with st.chat_message("assistant"):
        render_answer(item)

picked = st.pills("试试示例", EXAMPLES)
question = st.chat_input("用中文提问,例如:单体8172 2024年12月末各科目大类的净余额")
if picked and not question:
    question = picked

if question:
    item = {"q": question}
    st.session_state.history.append(item)
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        try:
            with st.status("GLM 生成 SQL…", expanded=True) as status:
                sql = extract_sql(llm.complete(SYSTEM_PROMPT, question))
                st.code(sql, language="sql")
                status.update(label="连数仓执行查询…")
                cols, rows = db.run_readonly_sql(sql, max_rows=100)
                status.update(label="GLM 总结结果…")
                result_text = "\n".join(str(r) for r in rows[:50])
                answer = llm.complete(
                    ANSWER_SYSTEM,
                    f"问题:{question}\n\nSQL:\n{sql}\n\n列:{cols}\n结果({len(rows)} 行):\n{result_text}",
                )
                status.update(label="完成", state="complete", expanded=False)
            item.update(sql=sql, cols=cols, rows=rows, answer=answer)
            render_answer(item)
        except Exception as e:
            item["error"] = f"{type(e).__name__}: {e}"
            st.error(item["error"])
