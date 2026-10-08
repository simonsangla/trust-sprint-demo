#!/usr/bin/env python3
"""Ask Cortex Analyst the refusal-regression questions N times on one semantic view.

Usage: python scripts/run_refusal_runs.py <DB.SCHEMA.VIEW> <N> <out.csv> [Q04,Q06,Q09,Q10]
Output columns: q, run, http, kind, value, text, request_id (input of freeze_refusal_runs.py).
kind = sql | suggestions | text_only. Each Cortex call costs credits; N=10 on 4 questions = 40 calls.
Needs SNOWFLAKE_DEFAULT_CONNECTION_NAME (e.g. mission_os_dogfood).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf import connect  # noqa: E402
import run_cortex as rc  # noqa: E402

QS_ALL = {
    "Q04": "What was the booking conversion rate in June 2026?",
    "Q06": "What was the booking conversion rate for the partner channel in January 2026?",
    "Q09": "How many paying customers do we have?",
    "Q10": "What is our customer churn rate?",
}


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    sv, n, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    keep = sys.argv[4].split(",") if len(sys.argv) > 4 else list(QS_ALL)
    conn = connect()
    cur = conn.cursor()
    cur.execute("USE WAREHOUSE MISSION_OS_WH")
    rc.SV = sv
    rows = []
    for k, q in QS_ALL.items():
        if k not in keep:
            continue
        for i in range(n):
            st, resp = rc.ask(conn.host, conn.rest.token, q)
            if st in (401, 403):
                print("auth refused", st)
                return 2
            content = (resp.get("message") or {}).get("content") or []
            text = " ".join(c.get("text", "") for c in content if c.get("type") == "text").strip()
            sql = next((c.get("statement", "") for c in content if c.get("type") == "sql"), "")
            val = ""
            if sql:
                try:
                    cur.execute(sql)
                    r = cur.fetchall()
                    val = str(r[0]) if r else "EMPTY"
                except Exception as e:  # keep the error as evidence, do not stop the batch
                    val = "ERR " + str(e)[:60]
            if sql:
                kind = "sql"
            elif any(c.get("type") == "suggestions" for c in content):
                kind = "suggestions"
            else:
                kind = "text_only"
            rows.append(dict(q=k, run=i + 1, http=st, kind=kind, value=val,
                             text=" ".join(text.split())[:140], request_id=resp.get("request_id", "")))
            print(k, i + 1, st, kind, val[:50], flush=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
