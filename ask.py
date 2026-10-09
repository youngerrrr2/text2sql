"""Text2SQL CLI。

用法:
    python ask.py "2024年12月 HMPL_PRC 各币种本币余额合计"
    python ask.py "..." --sql      # 只生成并打印 SQL,不执行
    python ask.py "..." --raw      # 只看数据表,不要 AI 总结
"""
from __future__ import annotations

import argparse
import re
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import db
import llm

SCHEMA_PATH = Path(__file__).parent / "schema" / "gl_balances.md"

SYSTEM_PROMPT = f"""\
你是资深 Oracle DBA 兼财务分析师。任务:把用户的中文财务问题翻译成**一条** Oracle SQL。

{SCHEMA_PATH.read_text(encoding="utf-8")}

## 输出要求
- 只输出一个 ```sql 代码块,不要任何额外解释
- 只允许 SELECT(只读账号);禁用 DML/DDL
- Oracle 语法:NVL、TO_DATE、FETCH FIRST n ROWS ONLY(不要 LIMIT / IFNULL / DATE())
- 主表 446 万行:WHERE 必须尽量下推过滤(账套 / 币种 / 期间 / 科目段),禁止先全表 JOIN 再过滤
- PERIOD_NAME 为 VARCHAR2,格式 'YYYY-MM'
- 跨币种 / 跨账套汇总金额一律用 _BEQ(本币)列;单币种原币口径才用无后缀列
- 除非用户要求,结果行数默认 <= 100
"""

ANSWER_SYSTEM = (
    "你是财务数据分析师。基于给出的 SQL 查询结果,用中文简洁回答问题:"
    "先一句话结论,再列关键数字(金额千分位、保留两位小数)。"
    "不要编造结果之外的数据;结果为空时如实说明可能原因。"
    "已知该表数据截止 2025-01:若 SQL 用了 MAX(PERIOD_NAME) 之类的兜底条件,"
    "必须向用户说明实际返回的是最新可得期间 2025-01,而非问题中问的月份。"
)


def extract_sql(text: str) -> str:
    m = re.search(r"```sql\s*(.*?)```", text, re.S | re.I)
    sql = (m.group(1) if m else text).strip()
    return sql.rstrip(";").strip()


def fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (float, Decimal)):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def print_table(cols: list[str], rows: list[tuple]) -> None:
    str_rows = [[fmt(v) for v in r] for r in rows]
    widths = []
    for i, col in enumerate(cols):
        w = len(str(col))
        if str_rows:
            w = max([w] + [len(r[i]) for r in str_rows])
        widths.append(min(w, 40))

    numeric = [
        all(r[i] == "" or r[i].replace(",", "").replace(".", "").replace("-", "").isdigit() for r in str_rows)
        for i in range(len(cols))
    ] if str_rows else [False] * len(cols)

    def line(cells: list[str]) -> str:
        return " | ".join(
            cell.rjust(w) if numeric[i] else cell.ljust(w)
            for i, (cell, w) in enumerate(zip(cells, widths))
        )

    print(line([str(c) for c in cols]))
    print("-+-".join("-" * w for w in widths))
    for r in str_rows:
        print(line(r))


def main() -> None:
    ap = argparse.ArgumentParser(description="数仓 Text2SQL(GL_BALANCES)")
    ap.add_argument("question", help="自然语言问题")
    ap.add_argument("--sql", action="store_true", help="只生成 SQL,不执行")
    ap.add_argument("--raw", action="store_true", help="只打印数据,不做 AI 总结")
    ap.add_argument("--max-rows", type=int, default=100)
    args = ap.parse_args()

    print("... 生成 SQL 中")
    sql = extract_sql(llm.complete(SYSTEM_PROMPT, args.question))
    print(f"\nSQL:\n{sql}\n")

    if args.sql:
        return

    print("... 执行查询中")
    cols, rows = db.run_readonly_sql(sql, max_rows=args.max_rows)
    truncated = " (已截断)" if len(rows) == args.max_rows else ""
    print(f"\n结果({len(rows)} 行{truncated}):\n")
    print_table(cols, rows)
    print()

    if args.raw:
        return

    print("... 生成回答中\n")
    result_text = "\n".join(str(r) for r in rows[:50])
    print(llm.complete(ANSWER_SYSTEM, f"问题:{args.question}\n\nSQL:\n{sql}\n\n列:{cols}\n结果({len(rows)} 行):\n{result_text}"))
    print()


if __name__ == "__main__":
    main()
