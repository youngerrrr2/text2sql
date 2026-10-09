#!/usr/bin/env python3
"""Consumption summary: DETAIL table deduped by TRANSACTION_ID, then
aggregated by year + cost center + project.

Usage:
  python query_consumption_summary.py --dept 9302 [--project P001] [--year 2024,2025] [--out path.csv]
"""
import argparse
import sys
from datetime import datetime

from lib_oracle import connect, in_clause, print_text_preview, split_list, stream_query_to_csv


def build_sql(dept_codes: list[str], project_codes: list[str], years: list[str]) -> tuple[str, dict]:
    binds: dict = {}
    dept_filter = in_clause("d.C_DEPARTMENT_CODE", dept_codes, "d", binds)
    project_filter = in_clause("d.C_PROJECT_CODE", project_codes, "p", binds)
    year_filter = in_clause("SUBSTR(d.PERIOD_NAME, 1, 4)", years, "y", binds)
    sql = f"""
        WITH detail_dedup AS (
            SELECT
                d.TRANSACTION_ID, d.PERIOD_NAME, d.BUDGET_STATUS, d.BUDGET_AMOUNT,
                d.C_DEPARTMENT_CODE, d.C_PROJECT_CODE, d.C_PROJECT_NAME, d.C_BUDGET_CODE,
                ROW_NUMBER() OVER (
                    PARTITION BY d.TRANSACTION_ID
                    ORDER BY
                        CASE
                            WHEN TRIM(d.C_DEPARTMENT_CODE) IS NOT NULL
                             AND TRIM(d.C_PROJECT_CODE)    IS NOT NULL
                             AND TRIM(d.C_BUDGET_CODE)     IS NOT NULL
                            THEN 1
                            WHEN TRIM(d.C_DEPARTMENT_CODE) IS NOT NULL
                             AND TRIM(d.C_PROJECT_CODE)    IS NOT NULL
                            THEN 2
                            WHEN TRIM(d.C_DEPARTMENT_CODE) IS NOT NULL
                             AND TRIM(d.C_BUDGET_CODE)     IS NOT NULL
                            THEN 3
                            WHEN TRIM(d.C_DEPARTMENT_CODE) IS NOT NULL
                            THEN 4
                            ELSE 5
                        END,
                        d.CID
                ) AS RN
            FROM ODS_BCS.ZZ_REP_CPHUWHY_BUDGET_DETAIL d
            WHERE {dept_filter}
              AND {project_filter}
              AND {year_filter}
        )
        SELECT
            SUBSTR(PERIOD_NAME, 1, 4)                                            AS 年度,
            C_DEPARTMENT_CODE                                                    AS 成本中心代码,
            C_PROJECT_CODE                                                       AS 项目代码,
            C_PROJECT_NAME                                                       AS 项目名称,
            SUM(CASE WHEN BUDGET_STATUS = '消耗' THEN BUDGET_AMOUNT ELSE 0 END)  AS 消耗,
            SUM(CASE WHEN BUDGET_STATUS = '占用' THEN BUDGET_AMOUNT ELSE 0 END)  AS 占用,
            SUM(BUDGET_AMOUNT)                                                    AS 消耗占用合计
        FROM detail_dedup
        WHERE RN = 1
        GROUP BY
            SUBSTR(PERIOD_NAME, 1, 4),
            C_DEPARTMENT_CODE,
            C_PROJECT_CODE,
            C_PROJECT_NAME
        ORDER BY
            年度, C_PROJECT_CODE
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
    out_path = args.out or f"output/budget_consumption_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    connection = connect()
    try:
        columns, preview_rows, total = stream_query_to_csv(connection, sql, binds, out_path)
    finally:
        connection.close()

    print_text_preview(columns, preview_rows, total)
    print(f"\nCSV 已生成: {out_path} ({total} 行)")


if __name__ == "__main__":
    sys.exit(main())
