---
name: bcs-budget-queries
description: Query BCS budget data in the BIPROD Oracle database (ODS_BCS schema) — allocation, 消耗/占用 consumption breakdown, balance, and transaction-level detail by department/project/year. Use when asked for budget execution, consumption, occupation, or balance reports against ODS_BCS.
---

# BCS Budget Queries

## Quick start

Run the matching script for budget requests instead of hand-writing SQL:

```bash
python scripts/query_overview.py            --dept 9304,9305 --project P001,P002 --year 2024,2025
python scripts/query_consumption_summary.py --dept 9302      --project P001      --year 2024,2025
python scripts/query_detail.py              --dept 9352 --budget-code XXXX --year 2025
```

- `query_overview.py` — EXECUTE table, aggregated by year/cost center/project:
  预算总额, 消耗, 占用, 消耗占用合计, 预算余额, 执行率_PCT. Excludes rows where
  `BUDGET_AMOUNT = 0` or `PROJECT_CODE` is null.
- `query_consumption_summary.py` — DETAIL table, deduped by `TRANSACTION_ID`
  then aggregated by year/cost center/project: 消耗, 占用, 消耗占用合计. No
  budget amount or balance — use `query_overview.py` for those.
- `query_detail.py` — one row per transaction/document, deduped: 单据编号,
  申请人, 审批日期, SRM合同号.
- `--dept` / `--project` / `--year` take comma-separated lists; omit to match
  all. `--budget-code` is detail-only.
- Requires `BIPROD_USER`, `BIPROD_PASSWORD`, `BIPROD_HOST`, `BIPROD_PORT`,
  `BIPROD_SERVICE` in the environment (see the `oracle-biprod-connect` skill).
- Prints a text preview (first 50 rows), writes the full result to CSV
  (`output/budget_<script>_<timestamp>.csv` by default, override with
  `--out`), and prints the CSV path.

## Schema

| Table | Grain | Use |
| --- | --- | --- |
| `ODS_BCS.ZZ_REP_CPHUWHY_BUDGET_EXECUTE` | one row per dept + project + period allocation | budget amount, balance |
| `ODS_BCS.ZZ_REP_CPHUWHY_BUDGET_DETAIL` | one row per transaction line | 消耗/占用 breakdown, no allocation amount |

Column prefixes differ: EXECUTE uses `DEPARTMENT_CODE`/`PROJECT_CODE`; DETAIL
uses `C_DEPARTMENT_CODE`/`C_PROJECT_CODE`. Join key across both tables:
`DEPARTMENT_CODE`/`PROJECT_CODE` + year.

Column not listed here: query `ALL_TAB_COLUMNS` instead of guessing —
`SELECT COLUMN_NAME, DATA_TYPE, NULLABLE FROM ALL_TAB_COLUMNS WHERE OWNER = 'ODS_BCS' AND TABLE_NAME = '...'`.

## Query conventions

- **Year**: neither table has a year column — derive with
  `SUBSTR(PERIOD_NAME, 1, 4) AS 年度`.
- **Chinese output aliases**: final columns are aliased in Chinese (预算总额,
  消耗, 占用, 成本中心代码, ...) for report consumption — keep this when
  adding queries.
- **消耗/占用 split**: EXECUTE has separate columns — `EXPENSE_AMOUNT` (消耗),
  `REQUEST_AMOUNT` (占用). DETAIL instead has one `BUDGET_AMOUNT` column
  tagged by `BUDGET_STATUS`; split with
  `SUM(CASE WHEN BUDGET_STATUS = '消耗' THEN BUDGET_AMOUNT ELSE 0 END)` /
  `'占用'`.
- **Editable filters**: mark user-editable `WHERE` values with a trailing
  `-- <-- CHANGE THIS: ...` comment so filters are easy to spot and swap.
- **Blank vs NULL**: Oracle treats `''` as `NULL`. Check both:
  `TRIM(col) IS NOT NULL AND TRIM(col) != ''`.
- **Zero-safe division**: guard rate/percentage calcs with
  `NULLIF(denominator, 0)`.
- **Null-safe join defaults**: use `NVL(col, 0)` for columns coming from a
  `LEFT JOIN` that may not match.
- **Dedup to one row per key**: when a table has multiple candidate rows per
  business key (e.g. `TRANSACTION_ID`), rank with
  `ROW_NUMBER() OVER (PARTITION BY key ORDER BY CASE WHEN ... priority)` then
  filter `WHERE rn = 1`.

## Writing a new query

When a request doesn't fit `overview` or `detail` (e.g. a different grouping
or a new filter dimension), write a new script instead of stretching an
existing one — reuse `scripts/lib_oracle.py` for the execution plumbing and
apply the Query conventions above for the SQL itself:

```python
import sys
from lib_oracle import connect, in_clause, print_text_preview, split_list, stream_query_to_csv

def build_sql(dept_codes: list[str]) -> tuple[str, dict]:
    binds: dict = {}
    dept_filter = in_clause("e.DEPARTMENT_CODE", dept_codes, "d", binds)
    sql = f"SELECT ... FROM ODS_BCS.ZZ_REP_CPHUWHY_BUDGET_EXECUTE e WHERE {dept_filter}"
    return sql, binds

def main() -> None:
    sql, binds = build_sql(split_list(sys.argv[1]))
    connection = connect()
    try:
        columns, preview_rows, total = stream_query_to_csv(connection, sql, binds, "output/out.csv")
    finally:
        connection.close()
    print_text_preview(columns, preview_rows, total)

if __name__ == "__main__":
    main()
```

`lib_oracle.py` never changes per query — it only knows connect / bind / fetch
/ output. Everything query-specific (columns, filters, joins) lives in the
new script's own `build_sql()`.

## Advanced

**Query variants not covered by the two scripts**: See
[reference/budget-overview-queries.sql](reference/budget-overview-queries.sql)
for four aggregate shapes `query_overview.py` doesn't produce (budget-code
breakdown, EXECUTE+DETAIL join, company-wide code totals, balance-status
flag). Start from the closest matching query instead of writing from
scratch.

**Execution primitives**: See
[scripts/lib_oracle.py](scripts/lib_oracle.py) for `connect()`, `in_clause()`,
`stream_query_to_csv()`, and `print_text_preview()` — the reusable parts
behind `query_overview.py` and `query_detail.py`.

**Open WebUI chat deployment**: `openwebui-tools/bcs_query.py` (outside this
skill dir) is a productionized subset of these three scripts, deployed as an
Open WebUI Tool bound to a custom "budget" Model — canned queries only
(no ad-hoc SQL), plus department-level access control and CSV delivery via
the Files API instead of local disk. Open WebUI's Workspace Skills feature
only imports a single Markdown file (no scripts/reference subdirs), so this
integration deliberately went through Tools + a Model system prompt instead
of a Skill import. When you change the SQL shape of one of the three core
queries here, check whether `bcs_query.py`'s matching function needs the
same fix (and vice versa) — they're independent files, not shared code.
