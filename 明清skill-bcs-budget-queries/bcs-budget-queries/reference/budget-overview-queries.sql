/* ============================================================
   BCS BUDGET QUERY VARIANTS — not covered by scripts/query_overview.py
   Database : BIPROD (Oracle)
   Schema   : ODS_BCS
   Tables   : ODS_BCS.ZZ_REP_CPHUWHY_BUDGET_EXECUTE  -- budget allocation & balance
              ODS_BCS.ZZ_REP_CPHUWHY_BUDGET_DETAIL    -- transaction-level consumption

   query_overview.py already handles the year+dept+project aggregate.
   These four cover shapes it doesn't: budget-code breakdown, an
   EXECUTE+DETAIL join, a company-wide budget-code rollup, and a
   balance-status flag. Start from the closest match instead of
   writing a new query from scratch.

   HOW TO USE:
     - All years are included by default (no year filter).
     - To filter department codes, edit the IN (...) list.
       Add or remove codes separated by commas.
       To query ALL departments, delete the entire WHERE clause line for DEPARTMENT_CODE.
     - Year is extracted from PERIOD_NAME via SUBSTR(PERIOD_NAME, 1, 4)
       and appears as 年度 in results so you can still slice by year.
   ============================================================ */


/* ============================================================
   QUERY 1 — Budget Code Consumption Breakdown by Cost Center (All Years)
   Source  : ODS_BCS.ZZ_REP_CPHUWHY_BUDGET_DETAIL
   Shows   : Each budget code under the specified cost centers,
             with 消耗 and 占用 split, across all years.
   Note    : DETAIL does not carry budget allocation amount;
             use query_overview.py for the budget total and balance.
   ============================================================ */
WITH detail_dedup AS (
    SELECT
        d.TRANSACTION_ID, d.PERIOD_NAME, d.BUDGET_STATUS, d.BUDGET_AMOUNT,
        d.C_DEPARTMENT_CODE, d.C_DEPARTMENT_NAME, d.C_BUDGET_CODE, d.C_BUDGET_NAME,
        d.C_PROJECT_CODE, d.C_PROJECT_NAME,
        ROW_NUMBER() OVER (
            PARTITION BY d.TRANSACTION_ID
            ORDER BY
                CASE
                    WHEN TRIM(d.C_DEPARTMENT_CODE) IS NOT NULL
                     AND TRIM(d.C_PROJECT_CODE)    IS NOT NULL
                     AND TRIM(d.C_BUDGET_CODE)     IS NOT NULL THEN 1
                    WHEN TRIM(d.C_DEPARTMENT_CODE) IS NOT NULL
                     AND TRIM(d.C_PROJECT_CODE)    IS NOT NULL THEN 2
                    WHEN TRIM(d.C_DEPARTMENT_CODE) IS NOT NULL
                     AND TRIM(d.C_BUDGET_CODE)     IS NOT NULL THEN 3
                    WHEN TRIM(d.C_DEPARTMENT_CODE) IS NOT NULL THEN 4
                    ELSE 5
                END,
                d.CID
        ) AS RN
    FROM ODS_BCS.ZZ_REP_CPHUWHY_BUDGET_DETAIL d
    WHERE d.C_DEPARTMENT_CODE IN ('7G29', '7D16')  -- <-- CHANGE THIS: add/remove dept codes
)
SELECT
    SUBSTR(PERIOD_NAME, 1, 4)                                          AS 年度,
    C_DEPARTMENT_CODE                                                  AS 成本中心代码,
    C_DEPARTMENT_NAME                                                  AS 成本中心名称,
    C_BUDGET_CODE                                                      AS 预算代码,
    C_BUDGET_NAME                                                      AS 预算名称,
    C_PROJECT_CODE                                                     AS 项目代码,
    C_PROJECT_NAME                                                     AS 项目名称,
    SUM(CASE WHEN BUDGET_STATUS = '消耗' THEN BUDGET_AMOUNT ELSE 0 END) AS 消耗,
    SUM(CASE WHEN BUDGET_STATUS = '占用' THEN BUDGET_AMOUNT ELSE 0 END) AS 占用,
    SUM(BUDGET_AMOUNT)                                                 AS 消耗占用合计
FROM detail_dedup
WHERE RN = 1
GROUP BY
    SUBSTR(PERIOD_NAME, 1, 4),
    C_DEPARTMENT_CODE,
    C_DEPARTMENT_NAME,
    C_BUDGET_CODE,
    C_BUDGET_NAME,
    C_PROJECT_CODE,
    C_PROJECT_NAME
ORDER BY
    年度,
    C_DEPARTMENT_CODE,
    C_BUDGET_CODE,
    C_PROJECT_CODE;


/* ============================================================
   QUERY 2 — Full Budget Summary: Budget + Code Breakdown + Balance (All Years)
   Source  : ODS_BCS.ZZ_REP_CPHUWHY_BUDGET_EXECUTE  (budget & balance)
             ODS_BCS.ZZ_REP_CPHUWHY_BUDGET_DETAIL    (budget code detail)
   Shows   : Budget by dept+project from EXECUTE joined with
             budget code consumption from DETAIL, all years.
   Join key: DEPARTMENT_CODE + PROJECT_CODE + year
   ============================================================ */
SELECT
    e.年度,
    e.DEPARTMENT_CODE                                                    AS 成本中心代码,
    e.DEPARTMENT_NAME                                                    AS 成本中心名称,
    e.PROJECT_CODE                                                       AS 项目代码,
    e.PROJECT_NAME                                                       AS 项目名称,
    d.C_BUDGET_CODE                                                      AS 预算代码,
    d.C_BUDGET_NAME                                                      AS 预算名称,
    e.BUDGET_AMOUNT                                                      AS 预算总额,
    NVL(d.消耗, 0)                                                       AS 消耗,
    NVL(d.占用, 0)                                                       AS 占用,
    NVL(d.消耗, 0) + NVL(d.占用, 0)                                      AS 消耗占用合计,
    e.BUDGET_AMOUNT - e.EXPENSE_AMOUNT - e.REQUEST_AMOUNT               AS 预算余额
FROM (
    -- Sub-query A: aggregate EXECUTE to dept+project level, by year
    SELECT
        SUBSTR(PERIOD_NAME, 1, 4)           AS 年度,
        DEPARTMENT_CODE,
        DEPARTMENT_NAME,
        PROJECT_CODE,
        PROJECT_NAME,
        SUM(BUDGET_AMOUNT)                  AS BUDGET_AMOUNT,
        SUM(EXPENSE_AMOUNT)                 AS EXPENSE_AMOUNT,
        SUM(REQUEST_AMOUNT)                 AS REQUEST_AMOUNT
    FROM ODS_BCS.ZZ_REP_CPHUWHY_BUDGET_EXECUTE
    WHERE DEPARTMENT_CODE IN ('9304', '9305')  -- <-- CHANGE THIS
    GROUP BY
        SUBSTR(PERIOD_NAME, 1, 4),
        DEPARTMENT_CODE, DEPARTMENT_NAME,
        PROJECT_CODE, PROJECT_NAME
) e
LEFT JOIN (
    -- Sub-query B: dedup DETAIL by TRANSACTION_ID, then aggregate by dept+project+budget code, by year
    WITH detail_dedup AS (
        SELECT
            TRANSACTION_ID, PERIOD_NAME, BUDGET_STATUS, BUDGET_AMOUNT,
            C_DEPARTMENT_CODE, C_PROJECT_CODE, C_BUDGET_CODE, C_BUDGET_NAME,
            ROW_NUMBER() OVER (
                PARTITION BY TRANSACTION_ID
                ORDER BY
                    CASE
                        WHEN TRIM(C_DEPARTMENT_CODE) IS NOT NULL
                         AND TRIM(C_PROJECT_CODE)    IS NOT NULL
                         AND TRIM(C_BUDGET_CODE)     IS NOT NULL THEN 1
                        WHEN TRIM(C_DEPARTMENT_CODE) IS NOT NULL
                         AND TRIM(C_PROJECT_CODE)    IS NOT NULL THEN 2
                        WHEN TRIM(C_DEPARTMENT_CODE) IS NOT NULL
                         AND TRIM(C_BUDGET_CODE)     IS NOT NULL THEN 3
                        WHEN TRIM(C_DEPARTMENT_CODE) IS NOT NULL THEN 4
                        ELSE 5
                    END,
                    CID
            ) AS RN
        FROM ODS_BCS.ZZ_REP_CPHUWHY_BUDGET_DETAIL
        WHERE C_DEPARTMENT_CODE IN ('9304', '9305')  -- <-- CHANGE THIS (same as above)
    )
    SELECT
        SUBSTR(PERIOD_NAME, 1, 4)           AS 年度,
        C_DEPARTMENT_CODE,
        C_PROJECT_CODE,
        C_BUDGET_CODE,
        C_BUDGET_NAME,
        SUM(CASE WHEN BUDGET_STATUS = '消耗' THEN BUDGET_AMOUNT ELSE 0 END) AS 消耗,
        SUM(CASE WHEN BUDGET_STATUS = '占用' THEN BUDGET_AMOUNT ELSE 0 END) AS 占用
    FROM detail_dedup
    WHERE RN = 1
    GROUP BY
        SUBSTR(PERIOD_NAME, 1, 4),
        C_DEPARTMENT_CODE, C_PROJECT_CODE,
        C_BUDGET_CODE, C_BUDGET_NAME
) d
    ON  e.DEPARTMENT_CODE = d.C_DEPARTMENT_CODE
    AND e.PROJECT_CODE    = d.C_PROJECT_CODE
    AND e.年度            = d.年度
ORDER BY
    e.年度,
    e.DEPARTMENT_CODE,
    e.PROJECT_CODE,
    d.C_BUDGET_CODE;


/* ============================================================
   QUERY 3 — All Budget Codes Across All Cost Centers (All Years)
   Source  : ODS_BCS.ZZ_REP_CPHUWHY_BUDGET_DETAIL
   Shows   : Every distinct budget code across all years,
             with total consumption per year.
             No department filter — covers the full company.
   ============================================================ */
WITH detail_dedup AS (
    SELECT
        d.TRANSACTION_ID, d.PERIOD_NAME, d.BUDGET_STATUS, d.BUDGET_AMOUNT,
        d.C_DEPARTMENT_CODE, d.C_BUDGET_CODE, d.C_BUDGET_NAME, d.C_PROJECT_CODE,
        ROW_NUMBER() OVER (
            PARTITION BY d.TRANSACTION_ID
            ORDER BY
                CASE
                    WHEN TRIM(d.C_DEPARTMENT_CODE) IS NOT NULL
                     AND TRIM(d.C_PROJECT_CODE)    IS NOT NULL
                     AND TRIM(d.C_BUDGET_CODE)     IS NOT NULL THEN 1
                    WHEN TRIM(d.C_DEPARTMENT_CODE) IS NOT NULL
                     AND TRIM(d.C_PROJECT_CODE)    IS NOT NULL THEN 2
                    WHEN TRIM(d.C_DEPARTMENT_CODE) IS NOT NULL
                     AND TRIM(d.C_BUDGET_CODE)     IS NOT NULL THEN 3
                    WHEN TRIM(d.C_DEPARTMENT_CODE) IS NOT NULL THEN 4
                    ELSE 5
                END,
                d.CID
        ) AS RN
    FROM ODS_BCS.ZZ_REP_CPHUWHY_BUDGET_DETAIL d
    WHERE d.C_BUDGET_CODE IS NOT NULL
      AND TRIM(d.C_BUDGET_CODE) != ''
)
SELECT
    SUBSTR(PERIOD_NAME, 1, 4)                                          AS 年度,
    C_BUDGET_CODE                                                      AS 预算代码,
    C_BUDGET_NAME                                                      AS 预算名称,
    COUNT(DISTINCT C_DEPARTMENT_CODE)                                  AS 涉及成本中心数,
    SUM(CASE WHEN BUDGET_STATUS = '消耗' THEN BUDGET_AMOUNT ELSE 0 END) AS 消耗合计,
    SUM(CASE WHEN BUDGET_STATUS = '占用' THEN BUDGET_AMOUNT ELSE 0 END) AS 占用合计,
    SUM(BUDGET_AMOUNT)                                                 AS 消耗占用总计
FROM detail_dedup
WHERE RN = 1
GROUP BY
    SUBSTR(PERIOD_NAME, 1, 4),
    C_BUDGET_CODE,
    C_BUDGET_NAME
ORDER BY
    年度,
    SUM(BUDGET_AMOUNT) DESC;


/* ============================================================
   QUERY 4 — Balance Status Check (All Years)
   Source  : ODS_BCS.ZZ_REP_CPHUWHY_BUDGET_EXECUTE
   Shows   : Balance status per year + project under the
             specified cost centers.
             Flags projects as 有余额 / 用尽 / 超支.
   ============================================================ */
SELECT
    SUBSTR(e.PERIOD_NAME, 1, 4)                                          AS 年度,
    e.DEPARTMENT_CODE                                                    AS 成本中心代码,
    e.DEPARTMENT_NAME                                                    AS 成本中心名称,
    e.PROJECT_CODE                                                       AS 项目代码,
    e.PROJECT_NAME                                                       AS 项目名称,
    SUM(e.BUDGET_AMOUNT)                                                 AS 预算总额,
    SUM(e.EXPENSE_AMOUNT + e.REQUEST_AMOUNT)                             AS 消耗占用合计,
    SUM(e.BUDGET_AMOUNT - e.EXPENSE_AMOUNT - e.REQUEST_AMOUNT)          AS 预算余额,
    CASE
        WHEN SUM(e.BUDGET_AMOUNT - e.EXPENSE_AMOUNT - e.REQUEST_AMOUNT) < 0
        THEN '超支'
        WHEN SUM(e.BUDGET_AMOUNT - e.EXPENSE_AMOUNT - e.REQUEST_AMOUNT) = 0
        THEN '用尽'
        ELSE '有余额'
    END                                                                  AS 状态
FROM ODS_BCS.ZZ_REP_CPHUWHY_BUDGET_EXECUTE e
WHERE e.DEPARTMENT_CODE IN ('9302')   -- <-- CHANGE THIS: add/remove dept codes
GROUP BY
    SUBSTR(e.PERIOD_NAME, 1, 4),
    e.DEPARTMENT_CODE,
    e.DEPARTMENT_NAME,
    e.PROJECT_CODE,
    e.PROJECT_NAME
ORDER BY
    年度,
    e.DEPARTMENT_CODE,
    SUM(e.BUDGET_AMOUNT - e.EXPENSE_AMOUNT - e.REQUEST_AMOUNT) ASC;
