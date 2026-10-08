#!/usr/bin/env python3
"""Create MISSION_OS_DB.TRUST_DEMO_DEV, load the three seeds, create the semantic view. Idempotent, never drops.

Usage: SNOWFLAKE_DEFAULT_CONNECTION_NAME=mission_os_dogfood uv run --with 'snowflake-connector-python[secure-local-storage]' python scripts/snowflake_setup.py
Tables load only when empty, so a re-run changes nothing.
"""
from __future__ import annotations

import sys

from sf import TABLES, connect, fq, run, seed_rows, semantic_view_sql

SCHEMA = "TRUST_DEMO_DEV"


def main() -> int:
    conn = connect()
    cur = conn.cursor()
    run(cur, "USE WAREHOUSE MISSION_OS_WH")
    run(cur, f"CREATE SCHEMA IF NOT EXISTS {fq(SCHEMA)}")
    for table, cols in TABLES.items():
        run(cur, f"CREATE TABLE IF NOT EXISTS {fq(SCHEMA)}.{table} ({cols})")
        n = run(cur, f"SELECT COUNT(*) FROM {fq(SCHEMA)}.{table}").fetchone()[0]
        if n == 0:
            rows = seed_rows(table.lower())
            marks = ",".join(["%s"] * len(rows[0]))
            cur.executemany(f"INSERT INTO {fq(SCHEMA)}.{table} VALUES ({marks})", rows)
            print(f"loaded {table}: {len(rows)} rows")
        else:
            print(f"{table}: already holds {n} rows, left alone")
    run(cur, semantic_view_sql(SCHEMA))
    print("semantic view ready:", fq(SCHEMA) + ".TRUST_DEMO_SV")
    return 0


if __name__ == "__main__":
    sys.exit(main())
