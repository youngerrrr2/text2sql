#!/usr/bin/env python3
"""Budget transaction detail: one row per transaction/document, deduped.
Includes SRM contract name/supplier via DW.DW_P2P_CONTRACT (latest per
CONTRACT_NUM) — kept in sync with openwebui-tools/bcs_query.py's
get_consumption_detail, which is the productionized chat-UI version of
this same query.

Usage:
  python query_detail.py --dept 9352 [--project P001] [--budget-code XXXX] [--year 2025] [--out path.csv]
"""
import argparse
import sys
from datetime import datetime

from lib_oracle import connect, in_clause, print_text_preview, split_list, stream_query_to_csv


def build_sql(
    dept_codes: list[str], project_codes: list[str], budget_codes: list[str], years: list[str]
) -> tuple[str, dict]:
    binds: dict = {}
    dept_filter = in_clause("d.C_DEPARTMENT_CODE", dept_codes, "d", binds)
    project_filter = in_clause("d.C_PROJECT_CODE", project_codes, "p", binds)
    budget_filter = in_clause("d.C_BUDGET_CODE", budget_codes, "b", binds)
    year_filter = in_clause("SUBSTR(d.PERIOD_NAME, 1, 4)", years, "y", binds)
    sql = f"""
        WITH ranked AS (
            SELECT
                d.TRANSACTION_ID, d.PERIOD_NAME, d.BUDGET_STATUS, d.BUDGET_AMOUNT,
                d.C_BUDGET_CODE, d.C_BUDGET_NAME,
                d.C_DEPARTMENT_CODE, d.C_DEPARTMENT_NAME,
                d.C_PROJECT_CODE, d.C_PROJECT_NAME,
                d.HEADER_TYPE, d.DOCUMENT_NUM, d.DOCUMENT_STATUS,
                d.CHARGE_USER_NAME, d.CHARGE_LOGIN_NAME, d.EXTERNAL_ID,
                d.SUBMIT_DATE, d.APPROVED_DATE,
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
              AND {budget_filter}
              AND {year_filter}
        ),

        payment AS (
            SELECT DISTINCT SETTLE_NUM, CONTRACT_NUM
            FROM DW.DW_P2P_PAYMENT
        ),

        contract_latest AS (
            SELECT CONTRACT_NUM, CONTRACT_NAME, SUPPLIER_NAME
            FROM (
                SELECT
                    CONTRACT_NUM, CONTRACT_NAME, SUPPLIER_NAME,
                    ROW_NUMBER() OVER (
                        PARTITION BY CONTRACT_NUM
                        ORDER BY CREATION_DATE DESC
                    ) AS rn
                FROM DW.DW_P2P_CONTRACT
            )
            WHERE rn = 1
        ),

        resolved AS (
            SELECT
                r.*,
                CASE
                    WHEN r.HEADER_TYPE = 'SRM合同协议'   THEN r.EXTERNAL_ID
                    WHEN r.HEADER_TYPE = 'SRM预算消耗单' THEN p.CONTRACT_NUM
                    ELSE NULL
                END AS SRM_CONTRACT_NUM
            FROM ranked r
            LEFT JOIN payment p
                ON  r.HEADER_TYPE = 'SRM预算消耗单'
                AND r.EXTERNAL_ID = p.SETTLE_NUM
            WHERE r.RN = 1
        )
        SELECT
            SUBSTR(res.PERIOD_NAME, 1, 4)     AS 年度,
            res.PERIOD_NAME                   AS 期间,
            res.C_DEPARTMENT_CODE             AS 成本中心代码,
            res.C_DEPARTMENT_NAME             AS 成本中心名称,
            res.C_BUDGET_CODE                 AS 预算代码,
            res.C_BUDGET_NAME                 AS 预算名称,
            res.C_PROJECT_CODE                AS 项目代码,
            res.C_PROJECT_NAME                AS 项目名称,
            res.BUDGET_STATUS                 AS 占用消耗状态,
            res.HEADER_TYPE                   AS 单据类型,
            res.DOCUMENT_NUM                  AS 单据编号,
            res.DOCUMENT_STATUS               AS 单据状态,
            res.BUDGET_AMOUNT                 AS 金额,
            res.CHARGE_USER_NAME              AS 申请人,
            res.CHARGE_LOGIN_NAME             AS 申请人邮箱,
            res.EXTERNAL_ID                   AS 外部关联ID,
            res.SRM_CONTRACT_NUM              AS SRM_CONTRACT,
            c.CONTRACT_NAME                   AS 合同名称,
            c.SUPPLIER_NAME                   AS 供应商名称,
            res.SUBMIT_DATE                    AS 提交日期,
            res.APPROVED_DATE                  AS 审批日期
        FROM resolved res
        LEFT JOIN contract_latest c
            ON res.SRM_CONTRACT_NUM = c.CONTRACT_NUM
        ORDER BY
            年度, res.C_BUDGET_CODE, res.BUDGET_STATUS, res.APPROVED_DATE
    """
    return sql, binds


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dept", default="", help="逗号分隔的成本中心代码列表,留空=全部")
    parser.add_argument("--project", default="", help="逗号分隔的项目代码列表,留空=全部")
    parser.add_argument("--budget-code", default="", help="逗号分隔的预算代码列表,留空=全部")
    parser.add_argument("--year", default="", help="逗号分隔的年度列表,留空=全部")
    parser.add_argument("--out", default=None, help="CSV输出路径,默认写到 output/ 下按时间戳命名")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sql, binds = build_sql(
        split_list(args.dept), split_list(args.project), split_list(args.budget_code), split_list(args.year)
    )
    out_path = args.out or f"output/budget_detail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    connection = connect()
    try:
        columns, preview_rows, total = stream_query_to_csv(connection, sql, binds, out_path)
    finally:
        connection.close()

    print_text_preview(columns, preview_rows, total)
    print(f"\nCSV 已生成: {out_path} ({total} 行)")


if __name__ == "__main__":
    sys.exit(main())
