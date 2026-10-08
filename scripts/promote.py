#!/usr/bin/env python3
"""Promote TRUST_DEMO_DEV to TRUST_DEMO_PROD: schema, table clones, semantic view. Idempotent, never drops or replaces.

Existing PROD objects are left exactly as they are (IF NOT EXISTS everywhere). A PROD table that differs from DEV
is reported, not overwritten: change it deliberately, outside this script.

Usage: SNOWFLAKE_DEFAULT_CONNECTION_NAME=mission_os_dogfood uv run --with 'snowflake-connector-python[secure-local-storage]' python scripts/promote.py
"""
from __future__ import annotations

import sys

from sf import TABLES, connect, fq, run, semantic_view_sql

DEV, PROD = "TRUST_DEMO_DEV", "TRUST_DEMO_PROD"


def main() -> int:
    conn = connect()
    cur = conn.cursor()
    run(cur, "USE WAREHOUSE MISSION_OS_WH")
    run(cur, f"CREATE SCHEMA IF NOT EXISTS {fq(PROD)}")
    for table in TABLES:
        run(cur, f"CREATE TABLE IF NOT EXISTS {fq(PROD)}.{table} CLONE {fq(DEV)}.{table}")
        d = run(cur, f"SELECT COUNT(*) FROM {fq(DEV)}.{table}").fetchone()[0]
        p = run(cur, f"SELECT COUNT(*) FROM {fq(PROD)}.{table}").fetchone()[0]
        print(f"{table}: dev={d} prod={p}" + ("" if d == p else "  DIFFERS, left alone"))
    run(cur, semantic_view_sql(PROD))
    print("semantic view ready:", fq(PROD) + ".TRUST_DEMO_SV")
    return 0


if __name__ == "__main__":
    sys.exit(main())
