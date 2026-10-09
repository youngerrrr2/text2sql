# 数仓表结构:GL_BALANCES(EBS 科目余额表)

## 主表 ODS_EBS.GL_BALANCES

EBS 总账科目余额事实表,约 446 万行。
粒度:**账套 × 科目组合 × 币种 × 会计期间**(每行是一个组合的月度余额)。
- ACTUAL_FLAG 全部为 `'A'`(实际数;A=实际 / B=预算 / E=保留)
- SRC_SYSTEM 全部为 `'EBS'`
- 数据范围:PERIOD_YEAR 2018–2025;**最新期间为 2025-01,之后尚未入库**——用户问 2025-02 及以后的数据时,应查询最新可得期间并在回答中说明数据截止 2025-01,不要生成注定为空的期间条件

### 关键业务列

| 列 | 类型 | 说明 |
|---|---|---|
| LEDGER_ID | NUMBER | 账套 ID,映射见下方【账套字典】 |
| CODE_COMBINATION_ID | NUMBER | 科目段组合 ID,展开科目需 join GL_CODE_COMBINATIONS |
| CURRENCY_CODE | VARCHAR2(15) | 币种。行数分布:CNY 322万 / HKD 77万 / USD 33万 / EUR 5.7万 / GBP 5.1万 / AUD / SEK / JPY / MOP / CZK / CHF |
| PERIOD_NAME | VARCHAR2(15) | 期间,**字符串 `'YYYY-MM'`**,如 `'2025-02'`;年末有 `'2024-13'` 调整期 |
| PERIOD_YEAR | NUMBER | 年份,2018–2025 |
| PERIOD_NUM | NUMBER | 期间号,1–12 为正常月份,13 为调整期 |

以下列为本表**内部/技术列,除非用户明确问到,不要使用**:
LAST_UPDATE_DATE、LAST_UPDATED_BY、BUDGET_VERSION_ID、ENCUMBRANCE_TYPE_ID、TRANSLATED_FLAG、REVALUATION_STATUS、PERIOD_TYPE、TEMPLATE_ID、ENCUMBRANCE_DOC_ID、ENCUMBRANCE_LINE_NUM、INSERT_DT、所有 `*_ADB` 列(平均余额,未使用)。

### 金额列(核心)

分两组:**原币列**(未折算,只在同一币种内可比)和**本币列**(后缀 `_BEQ`,已折算为账套记账本位币)。

原币列:
| 列 | 说明 |
|---|---|
| BEGIN_BALANCE_DR / BEGIN_BALANCE_CR | 月初原币借方 / 贷方余额 |
| PERIOD_NET_DR / PERIOD_NET_CR | 本月原币借方 / 贷方发生额 |
| QUARTER_TO_DATE_DR / QUARTER_TO_DATE_CR | 原币借方 / 贷方季累计 |
| PROJECT_TO_DATE_DR / PROJECT_TO_DATE_CR | 原币自启用以来累计 |

本币列(同上,加 `_BEQ` 后缀):
| 列 | 说明 |
|---|---|
| BEGIN_BALANCE_DR_BEQ / BEGIN_BALANCE_CR_BEQ | 月初本币借方 / 贷方余额 |
| PERIOD_NET_DR_BEQ / PERIOD_NET_CR_BEQ | 本月本币借方 / 贷方发生额 |
| QUARTER_TO_DATE_DR_BEQ / QUARTER_TO_DATE_CR_BEQ | 本币借方 / 贷方季累计 |

**计算口径:**
- 月末净余额(净借方)= `(BEGIN_BALANCE_DR + PERIOD_NET_DR) − (BEGIN_BALANCE_CR + PERIOD_NET_CR)`,即"月初余额 + 本月发生"的借贷净额(原币或本币同理)
- 借方为正:资产、成本费用类科目净额为正数;负债、权益、收入类科目为贷方余额,净额为**负数**,报告时通常取反或说明方向
- "年初至今发生额(YTD)"= 对 `PERIOD_NUM <= 当前月` 的 PERIOD_NET 求和;损益类科目年初会清零,只看当年
- **跨币种或跨账套汇总金额,必须用 `_BEQ` 本币列**;单币种口径才用无后缀原币列

### 账套字典(全部 20 个,静态)

| LEDGER_ID | 账套名 | 本位币 | 类型 |
|---|---|---|---|
| 2021 | HMPL_PRC | CNY | PRIMARY 主账套(中国准则) |
| 2041 | HHLDHHOG_PRC | CNY | PRIMARY |
| 2043 | HSPL_PRC | CNY | PRIMARY |
| 2045 | HMPL_IFRS | CNY | SECONDARY(IFRS 调整) |
| 2047 | HMPL_US | CNY | SECONDARY(US GAAP 调整) |
| 2049 | HHLDHHOG_IFRS | CNY | SECONDARY |
| 2052 | HHLDHHOG_US | CNY | SECONDARY |
| 2054 | HSPL_IFRS | CNY | SECONDARY |
| 2056 | HSPL_US | CNY | SECONDARY |
| 2092 | HCM_HKD_FRS | HKD | PRIMARY |
| 2093 | HCM_HKD_IFRS | HKD | SECONDARY |
| 2094 | HCM_HKD_US GAAP | HKD | SECONDARY |
| 2098 | HCM_USD_US GAAP | USD | PRIMARY |
| 2099 | HCM_USD_IFRS | USD | SECONDARY |
| 2104 | HCM_GBP_UK GAAP | GBP | PRIMARY |
| 2105 | HCM_GBP_IFRS | GBP | SECONDARY |
| 2106 | HCM_GBP_US GAAP | GBP | SECONDARY |
| 2120 | HCM_EUR_IFRS | EUR | PRIMARY |
| 2122 | HCM_EUR_US GAAP | EUR | SECONDARY |
| 2140 | HCM_USD_STAT | USD | SECONDARY(统计账套) |

命名规律:`{主体}_{准则}`。主体有 HMPL、HHLDHHOG、HSPL、HCM(HCM 按币种 HKD/USD/GBP/EUR 拆账套);`_PRC` 是各主体的中国准则主账套,`_IFRS` / `_US` 是对应准则差异的调整账套(SECONDARY)。
注意:用户问"单体 8172 / 实体 8172"指的是**公司段 SEGMENT1**(见下),不是账套。

### 科目组合维表 ODS_EBS.GL_CODE_COMBINATIONS(约 6.5 万行,join 用)

关联条件:`GL_BALANCES.CODE_COMBINATION_ID = GL_CODE_COMBINATIONS.CODE_COMBINATION_ID`(别名建议 gcc)

科目弹性域共 9 段,含义来自 ODS_EBS.FND_ID_FLEX_SEGMENTS(ID_FLEX_CODE='GL#'),为权威定义:

| 段 | 含义 | 示例值 |
|---|---|---|
| SEGMENT1 | Company 公司/单体 | 8002, 8163, **8172(=HUTCHMED Limited)** |
| SEGMENT2 | Account 会计科目 | 100200, 102200, B90123(首位含 1–9 及 A、B) |
| SEGMENT3 | CostCenter 成本中心/部门 | 0000(默认), 9100, 9304 |
| SEGMENT4 | Prod/Serv 产品/服务 | 999(=通用) |
| SEGMENT5 | Channel 渠道 | 00 |
| SEGMENT6 | Country 国家 | CN0(=China) |
| SEGMENT7 | InterComp 内部往来 | 0000 |
| SEGMENT8 | Project 项目 | 0000 |
| SEGMENT9 | Spare 备用 | 0 |

注意:余额数据里大量行的 SEGMENT3–5 等为 `'T'` 或 `'0000'` 等模板/默认值,属正常现象(汇总行),不要当异常过滤掉。

### 段值中文名映射 DW.DW_FND_SEGMENTS_NAME(3,211 行,只读 join 用)

把段代码翻译成中文。关键列:`APPLICATION_COLUMN_NAME`(段名)、`FLEX_VALUE`(段值)、`ZHS_DESCRIPTION`(中文名)、`US_DESCRIPTION`(英文名)。
覆盖:SEGMENT1 公司 49 个、SEGMENT2 科目 2031 个、SEGMENT3 成本中心 611 个等。

**用户用中文提到科目/公司/部门名称时,必须 join 此表匹配,展示结果时优先输出中文名,不要输出裸代码**:

```sql
-- 按科目中文名过滤(别名建议 acc / seg1 / seg3 …)
JOIN DW.DW_FND_SEGMENTS_NAME acc
  ON acc.APPLICATION_COLUMN_NAME = 'SEGMENT2' AND acc.FLEX_VALUE = gcc.SEGMENT2
WHERE acc.ZHS_DESCRIPTION LIKE '%土地使用权%'
-- 公司段/成本中心段同理:APPLICATION_COLUMN_NAME 分别取 'SEGMENT1' / 'SEGMENT3'
```

中文名匹配不到的代码('T'、'0000' 等)是模板/默认值,属正常;按科目前缀粗分类(`gcc.SEGMENT2 LIKE '1%'` 资产类等 EBS 惯例)只作兜底手段,能用中文名就用中文名。

### 示例

**例 1(单表):2024 年 12 月 HMPL_PRC 账套(2021)本币月末净余额合计**

```sql
SELECT SUM(b.BEGIN_BALANCE_DR_BEQ + b.PERIOD_NET_DR_BEQ
         - b.BEGIN_BALANCE_CR_BEQ - b.PERIOD_NET_CR_BEQ) AS net_balance_beq
FROM ODS_EBS.GL_BALANCES b
WHERE b.LEDGER_ID = 2021
  AND b.PERIOD_NAME = '2024-12'
```

**例 2(join 维表):单体 8172 在 2025 年 2 月的本币月末净余额,按科目段前 2 位汇总**

```sql
SELECT SUBSTR(gcc.SEGMENT2, 1, 2) AS acct_group,
       SUM(b.BEGIN_BALANCE_DR_BEQ + b.PERIOD_NET_DR_BEQ
         - b.BEGIN_BALANCE_CR_BEQ - b.PERIOD_NET_CR_BEQ) AS net_balance_beq
FROM ODS_EBS.GL_BALANCES b
JOIN ODS_EBS.GL_CODE_COMBINATIONS gcc
  ON gcc.CODE_COMBINATION_ID = b.CODE_COMBINATION_ID
WHERE gcc.SEGMENT1 = '8172'
  AND b.PERIOD_NAME = '2025-02'
GROUP BY SUBSTR(gcc.SEGMENT2, 1, 2)
ORDER BY acct_group
```

**例 3(join 中文名映射):单体 8172 2024 年 12 月末,科目名含"土地使用权"的本币净余额明细**

```sql
SELECT acc.ZHS_DESCRIPTION AS 科目,
       SUM(b.BEGIN_BALANCE_DR_BEQ + b.PERIOD_NET_DR_BEQ
         - b.BEGIN_BALANCE_CR_BEQ - b.PERIOD_NET_CR_BEQ) AS net_balance_beq
FROM ODS_EBS.GL_BALANCES b
JOIN ODS_EBS.GL_CODE_COMBINATIONS gcc
  ON gcc.CODE_COMBINATION_ID = b.CODE_COMBINATION_ID
JOIN DW.DW_FND_SEGMENTS_NAME acc
  ON acc.APPLICATION_COLUMN_NAME = 'SEGMENT2' AND acc.FLEX_VALUE = gcc.SEGMENT2
WHERE gcc.SEGMENT1 = '8172'
  AND b.PERIOD_NAME = '2024-12'
  AND acc.ZHS_DESCRIPTION LIKE '%土地使用权%'
GROUP BY acc.ZHS_DESCRIPTION
ORDER BY net_balance_beq
```
