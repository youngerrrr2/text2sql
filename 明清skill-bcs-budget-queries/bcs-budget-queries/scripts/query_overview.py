#!/usr/bin/env python3
"""Budget overview: aggregated by year + cost center + project.

Usage:
  python query_overview.py --dept 9304,9305 [--project P001,P002] [--year 2024,2025] [--out path.csv]
"""
import argparse
import sys
from datetime import datetime

from lib_oracle import connect, in_clause, print_text_preview, split_list, stream_query_to_csv


def build_sql(dept_codes: list[str], project_codes: list[str], years: list[str]) -> tuple[str, dict]:
    binds: dict = {}
    dept_filter = in_clause("e.DEPARTMENT_CODE", dept_codes, "d", binds)
    project_filter = in_clause("e.PROJECT_CODE", project_codes, "p", binds)
    year_filter = in_clause("SUBSTR(e.PERIOD_NAME, 1, 4)", years, "y", binds)
    sql = f"""
        SELECT
            SUBSTR(e.PERIOD_NAME, 1, 4)                                 AS 年度,
            e.DEPARTMENT_CODE                                           AS 成本中心代码,
            e.DEPARTMENT_NAME                                           AS 成本中心名称,
            e.PROJECT_CODE                                              AS 项目代码,
            e.PROJECT_NAME                                              AS 项目名称,
            SUM(e.BUDGET_AMOUNT)                                        AS 预算总额,
            SUM(e.EXPENSE_AMOUNT)                                       AS 消耗,
            SUM(e.REQUEST_AMOUNT)                                       AS 占用,
            SUM(e.EXPENSE_AMOUNT + e.REQUEST_AMOUNT)                    AS 消耗占用合计,
            SUM(e.BUDGET_AMOUNT - e.EXPENSE_AMOUNT - e.REQUEST_AMOUNT)  AS 预算余额,
            ROUND(
                SUM(e.EXPENSE_AMOUNT + e.REQUEST_AMOUNT)
                / NULLIF(SUM(e.BUDGET_AMOUNT), 0) * 100, 2
            )                                                           AS 执行率_PCT
        FROM ODS_BCS.ZZ_REP_CPHUWHY_BUDGET_EXECUTE e
        WHERE {dept_filter}
          AND {project_filter}
          AND {year_filter}
          AND e.BUDGET_AMOUNT <> 0
          AND e.PROJECT_CODE IS NOT NULL
        GROUP BY
            SUBSTR(e.PERIOD_NAME, 1, 4),
            e.DEPARTMENT_CODE, e.DEPARTMENT_NAME,
            e.PROJECT_CODE, e.PROJECT_NAME
        ORDER BY
            年度, e.DEPARTMENT_CODE, e.PROJECT_CODE
    """
    return sql, binds


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dept", default="", help="逗号分隔的成本中心代码列表,留空=全部")
    parser.add_argument("--project", default="", help="逗号分隔的项目代码列表,留空=全部")
    parser.add_argument("--year", default="", help="逗号分隔的年度列表,留空=全部")
    parser.add_argument("--out", default=None, help="CSV输出路径,默认写到 output/ 下按时间戳命名")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sql, binds = build_sql(split_list(args.dept), split_list(args.project), split_list(args.year))
    out_path = args.out or f"output/budget_overview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    connection = connect()
    try:
        columns, preview_rows, total = stream_query_to_csv(connection, sql, binds, out_path)
    finally:
        connection.close()

    print_text_preview(columns, preview_rows, total)
    print(f"\nCSV 已生成: {out_path} ({total} 行)")


if __name__ == "__main__":
    sys.exit(main())
