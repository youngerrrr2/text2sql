"""Oracle 数仓连接与只读查询执行。"""
from __future__ import annotations

import re
from pathlib import Path

import oracledb


def load_env(path: Path | None = None) -> dict[str, str]:
    """极简 .env 解析:KEY=VALUE 原样取整行值。

    不剥引号、不识别行内注释(密码可能含 #)。
    """
    target = path or Path(__file__).parent / ".env"
    env: dict[str, str] = {}
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


ENV = load_env()


def connect() -> oracledb.Connection:
    dsn = f"{ENV['DB_HOST']}:{ENV['DB_PORT']}/{ENV['DB_SERVICE']}"
    return oracledb.connect(user=ENV["DB_USER"], password=ENV["DB_PASS"], dsn=dsn)


def run_readonly_sql(sql: str, max_rows: int = 100) -> tuple[list[str], list[tuple]]:
    """只允许 SELECT / WITH,返回 (列名, 行元组列表),超过 max_rows 截断。"""
    stripped = sql.strip().lstrip("( \n\t")
    first_word = stripped.split(None, 1)[0].upper() if stripped.split(None, 1) else ""
    if first_word not in {"SELECT", "WITH"}:
        raise ValueError(f"拒绝执行非查询语句(首词 {first_word!r})")
    if re.search(r"\bfor\s+update\b", sql, re.I):
        raise ValueError("拒绝执行 FOR UPDATE")

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchmany(max_rows)
            return cols, list(rows)
