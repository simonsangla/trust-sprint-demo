#!/usr/bin/env python3
"""Create TRUST_DEMO_SV_ZG: the demo semantic view with ONE change, a zero-guard on conversion_rate
(bookings / NULLIF(session_count, 0)). DEV only, CREATE OR REPLACE. mission-os #1377.
    python scripts/make_zero_guard_view.py [--print]"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

OLD = "bookings.bookings / sessions.session_count"
NEW = "bookings.bookings / NULLIF(sessions.session_count, 0)"


def guarded(ddl: str, loc: str) -> str:
    """Rename the view and guard the ratio; refuse unless each replacement matches exactly once."""
    if ddl.count(OLD) != 1:
        raise ValueError("expected exactly one unguarded ratio, found %d" % ddl.count(OLD))
    head = f"{loc}.TRUST_DEMO_SV\n"
    if ddl.count(head) != 1:
        raise ValueError("expected exactly one view name line, found %d" % ddl.count(head))
    out = ddl.replace(head, f"{loc}.TRUST_DEMO_SV_ZG\n", 1).replace(OLD, NEW, 1)
    return out.replace("CREATE SEMANTIC VIEW IF NOT EXISTS", "CREATE OR REPLACE SEMANTIC VIEW", 1)


def main() -> int:
    from sf import connect, fq, run, semantic_view_sql
    schema = "TRUST_DEMO_DEV"
    ddl = guarded(semantic_view_sql(schema), fq(schema))
    if "--print" in sys.argv:
        print(ddl); return 0
    cur = connect().cursor()
    for s in ("USE WAREHOUSE MISSION_OS_WH", "USE DATABASE MISSION_OS_DB", f"USE SCHEMA {schema}"):
        run(cur, s)
    run(cur, ddl); print("TRUST_DEMO_SV_ZG ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
