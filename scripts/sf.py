"""Shared Snowflake helpers. Connection `mission_os_dogfood` from ~/.snowflake/connections.toml; no credential is read or printed here."""
from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = "MISSION_OS_DB"
ALLOWED = {"TRUST_DEMO_DEV", "TRUST_DEMO_PROD"}

TABLES = {
    "USERS": "user_id VARCHAR, signup_date DATE, country VARCHAR, plan VARCHAR",
    "SESSIONS": "session_id VARCHAR, user_id VARCHAR, session_date DATE, channel VARCHAR",
    "BOOKINGS": "booking_id VARCHAR, user_id VARCHAR, session_id VARCHAR, booking_date DATE, amount NUMBER(12,2), status VARCHAR",
}

# Statements this repo may run. Anything that could drop or replace is refused before it reaches Snowflake.
FORBIDDEN = re.compile(r"\b(drop|truncate|or\s+replace|undrop)\b", re.IGNORECASE)


def connect():
    import snowflake.connector as sc
    return sc.connect(connection_name="mission_os_dogfood")


def fq(schema: str) -> str:
    if schema not in ALLOWED:
        raise SystemExit(f"refused: schema {schema} is outside {sorted(ALLOWED)}")
    return f"{DB}.{schema}"


def run(cur, sql: str, params=None):
    if FORBIDDEN.search(re.sub(r"--[^\n]*", "", sql)):
        raise SystemExit(f"refused destructive statement: {sql[:60]}")
    cur.execute(sql, params)
    return cur


def semantic_view_sql(schema: str) -> str:
    return (ROOT / "snowflake" / "semantic_view.sql").read_text().replace("{{SCHEMA}}", fq(schema))


def seed_rows(name: str):
    with (ROOT / "seeds" / f"{name}.csv").open() as f:
        r = csv.reader(f)
        next(r)
        return [tuple(None if v == "" else v for v in row) for row in r]
