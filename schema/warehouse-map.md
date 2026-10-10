# 数仓表关系全景图

> 人类参考文档(不注入 LLM 提示词)。LLM 用的表结构见 [gl_balances.md](gl_balances.md)。
> 标注:✅ = 列级勘察/数据实测验证;📖 = 来自明清 bcs-budget-queries skill 文档;❓ = 未确认。
> 勘察时间:2026-10-10。数仓:Oracle BITEST @ 10.13.100.72:1521,账号 bi_readonly(只读)。

## 一、分层架构总览

```
ODS 层(贴源,原样同步业务系统)
├── ODS_EBS/   ← Oracle EBS 总账(4 张 GL 表)
└── ODS_BCS/   ← BCS 预算系统(2 张预算表 + EM01~03 视图 ❓)

DW 层(ETL 加工,已扁平化维度)
├── GL 余额/报表系列(DW_FIN_*)
├── DW_FND_SEGMENTS_NAME(段值中文字典)
└── TE 差旅费用系列(DW_TE_*)❓

DM 层(报表模型,9 张 DM_FIN_REPORT_*)❓ 未勘察
```

## 二、EBS 总账域(ODS_EBS)——本项目主域 ✅

```
GL_LEDGERS(22 行,账套字典)
    ▲ LEDGER_ID
    │
GL_BALANCES(446 万行,事实表)──CODE_COMBINATION_ID──▶ GL_CODE_COMBINATIONS(6.5 万行,9 段组合)
    │                                                      │ SEGMENT1..9(逐段,见下)
    │ 本币列 _BEQ 折算用的汇率                              ▼
    │                                        (段名+段值)× N 次
GL_DAILY_RATES_V(28 万行)                DW.DW_FND_SEGMENTS_NAME(3,211 行,中文字典)
    从币种/币种/日期/类型 → 汇率
```

| 表 | 粒度 | 关联键 |
|---|---|---|
| GL_BALANCES | 账套 × 组合 × 币种 × 期间 | `LEDGER_ID` → GL_LEDGERS;`CODE_COMBINATION_ID` → GL_CODE_COMBINATIONS |
| GL_CODE_COMBINATIONS | 一个 9 段组合一行 | 主键 CODE_COMBINATION_ID;段值经 DW_FND_SEGMENTS_NAME 译名 |
| GL_LEDGERS | 账套 | 主键 LEDGER_ID;另有 CHART_OF_ACCOUNTS_ID(科目表结构)、各类汇率类型配置 |
| GL_DAILY_RATES_V | 日汇率 | `(FROM_CURRENCY, TO_CURRENCY, CONVERSION_TYPE, CONVERSION_DATE)` → CONVERSION_RATE |

9 段含义(✅ ODS_EBS.FND_ID_FLEX_SEGMENTS,GL# 结构 + DW 层中文注释双重验证):

SEGMENT1 公司段 · SEGMENT2 科目段 · SEGMENT3 成本中心段 · SEGMENT4 产品服务段 ·
SEGMENT5 渠道段 · SEGMENT6 业务国家段 · SEGMENT7 往来段 · SEGMENT8 项目段 · SEGMENT9 备用段

## 三、GL 加工域(DW 层)✅ 列级勘察

ODS 的关联在这里**已被 ETL 打平**——不用再 join,维度列直接在表里:

| 表 | 行数 | 扁平化维度列 |
|---|---|---|
| DW_FIN_GL_BALANCES_F | 251 万 | ENTITY_CODE(单体)、LEDGER_ID、CODE_COMBINATION_ID、CONCAT_SEGMENTS(九段值)、SEGMENT1–9、ACCOUNT_CODE、RATE、ITEM_CODE、SEG_CODE |
| DW_FIN_GL_BALANCES_DETAIL | 274 万 | 同上(无 ITEM_CODE/SEG_CODE),明细试算口径 |
| DW_FIN_GL_REPORT_F | 21.9 万 | ENTITY_CODE、ITEM_CODE(表项)、SEG_CODE、RATE、JE_CODE |
| DW_FIN_REPORT_DISPLAY_F | 60 万 | ENTITY_CODE、ITEM_CODE、JE_CODE(报表展示口径) |

- 加工血缘(DW ← ODS):DW 表同时带 LEDGER_ID/CODE_COMBINATION_ID(ODS 键)和扁平段值,推断由 ODS_EBS GL_BALANCES 加工而来(结构证据充分,未逐表验证 ETL)
- `ENTITY_CODE`(单体)↔ `SEGMENT1`(公司段)同一含义 ✅
- 表项链路:`DW_FIN_REPORT_ACCOUNT_M`(3,282 行,科目映射计算表)维护 ACCOUNT_CODE ↔ ITEM_CODE(报表表项)的映射 ❓ 具体列未勘察
- 汇率:`DW_FIN_GL_DAILY_RATES` 与 ODS 的 GL_DAILY_RATES_V 同构,多一个 PERIOD_NAME 列

## 四、预算域(ODS_BCS)📖 + ✅

| 表 | 行数 | 粒度 | 关键列 |
|---|---|---|---|
| ZZ_REP_CPHUWHY_BUDGET_EXECUTE | 2.3 万 | 部门 × 项目 × 期间(预算额度) | COMPANY_ID、PERIOD_NAME/GL_PERIOD、DEPARTMENT_CODE/NAME、PROJECT_CODE/NAME、BUDGET_CODE |
| ZZ_REP_CPHUWHY_BUDGET_DETAIL | 18.5 万 | 单笔交易/单据 | TRANSACTION_ID、HEADER_ID、C_DEPARTMENT_CODE、C_PROJECT_CODE、C_BUDGET_CODE、COMPANY_ID、PERIOD_NAME |

- 两表关联:`DEPARTMENT_CODE + PROJECT_CODE + 年度`(注意 DETAIL 侧带 `C_` 前缀;两表都没有年份列,用 `SUBSTR(PERIOD_NAME,1,4)` 现算)📖
- **跨域关联**:`DEPARTMENT_CODE` ↔ GL 域 `SEGMENT3`(成本中心段,同一套 9304/9305 代码)✅ 代码值重合验证;`COMPANY_ID` ↔ `SEGMENT1`(单体)推断 ❓
- EM01_V / EM02_V / EM03_V(视图):含义未勘察 ❓

## 五、本项目的查询策略(当前口径)

1. **问科目余额** → ODS_EBS.GL_BALANCES 为主表(数据最全,2018-11 起)
2. **按段值中文名过滤/展示** → join GL_CODE_COMBINATIONS + DW_FND_SEGMENTS_NAME(左连接防模板值丢行)
3. **账套名** → 固化字典(gl_balances.md 内),不实时 join GL_LEDGERS
4. DW 层的 DW_FIN_GL_*_F 已扁平化,若要做"免 join 的快速查询"或对账(ODS vs DW),可直接查,关联键 LEDGER_ID + CODE_COMBINATION_ID 与 ODS 一致

## 六、未勘察区(待扩展)

- DM 层 9 张报表模型(DM_FIN_REPORT_FSG/MPS 系列)
- TE 差旅费用域(DW_TE_EXPENSE_DETAILS 228 万行等)
- ODS_BCS 的 EM01~03 视图
- GL_JE_LINES / GL_JE_HEADERS(凭证明细):**ODS 未同步**,查明细需推动数仓加同步
