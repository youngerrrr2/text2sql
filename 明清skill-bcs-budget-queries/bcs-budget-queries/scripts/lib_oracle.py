"""Shared Oracle execution primitives for the bcs-budget-queries scripts.

No budget-specific knowledge lives here — only connect / bind / fetch / output.
Import what you need when writing a new query script; see SKILL.md's
"Writing a new query" section.
"""
import csv
import os

import oracledb


def split_list(raw: str) -> list[str]:
    if not raw:
        return []
    return [v.strip() for v in raw.split(",") if v.strip()]


def in_clause(column: str, values: list[str], prefix: str, binds: dict) -> str:
    """Build a safe `column IN (:p0, :p1, ...)` clause, binding each value by
    name. Returns `1 = 1` (no filter) when `values` is empty."""
    if not values:
        return "1 = 1"
    placeholders = []
    for i, value in enumerate(values):
        name = f"{prefix}{i}"
        binds[name] = value
        placeholders.append(f":{name}")
    return f"{column} IN ({', '.join(placeholders)})"


def connect() -> oracledb.Connection:
    dsn = "{host}:{port}/{service}".format(
        host=os.environ["BIPROD_HOST"],
        port=os.environ["BIPROD_PORT"],
        service=os.environ["BIPROD_SERVICE"],
    )
    return oracledb.connect(
        user=os.environ["BIPROD_USER"],
        password=os.environ["BIPROD_PASSWORD"],
        dsn=dsn,
    )


def stream_query_to_csv(
    connection: oracledb.Connection,
    sql: str,
    binds: dict,
    csv_path: str,
    arraysize: int = 1000,
    preview_limit: int = 50,
) -> tuple[list[str], list[tuple], int]:
    """Fetch in `arraysize`-sized batches and write straight to CSV so a
    large BI result set never has to sit fully in memory. Returns
    `(columns, preview_rows, total_row_count)`."""
    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
    with connection.cursor() as cursor:
        cursor.arraysize = arraysize
        cursor.execute(sql, binds)
        columns = [col[0] for col in cursor.description]
        preview_rows: list[tuple] = []
        total = 0
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            while True:
                batch = cursor.fetchmany()  # batch size = cursor.arraysize
                if not batch:
                    break
                writer.writerows(batch)
                if len(preview_rows) < preview_limit:
                    preview_rows.extend(batch[: preview_limit - len(preview_rows)])
                total += len(batch)
    return columns, preview_rows, total


def print_text_preview(columns: list[str], preview_rows: list[tuple], total: int) -> None:
    if not preview_rows:
        print("无匹配结果。")
        return
    widths = [len(c) for c in columns]
    for row in preview_rows:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len(str(value)))
    header = " | ".join(c.ljust(widths[i]) for i, c in enumerate(columns))
    print(header)
    print("-+-".join("-" * w for w in widths))
    for row in preview_rows:
        print(" | ".join(str(v).ljust(widths[i]) for i, v in enumerate(row)))
    if total > len(preview_rows):
        print(f"... 仅预览前 {len(preview_rows)} 行,共 {total} 行,完整结果见 CSV。")
