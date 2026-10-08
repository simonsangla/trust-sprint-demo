#!/usr/bin/env python3
"""Send every question in seeds/question_pack.csv to the Cortex Analyst REST API ONCE and freeze the result.

Writes seeds/cortex_answers.csv (question, generated_sql, answer_value, request_id, run_ts + context columns).
The semantic view is MISSION_OS_DB.TRUST_DEMO_DEV.TRUST_DEMO_SV. The generated SQL is executed read-only
to read the answer value. One request per question, no retry. Refuses to overwrite an existing results file
(use --force to re-spend). Auth is the connector session token; it is never printed or written.

Usage: SNOWFLAKE_DEFAULT_CONNECTION_NAME=mission_os_dogfood uv run --with 'snowflake-connector-python[secure-local-storage]' python scripts/run_cortex.py
"""
from __future__ import annotations

import csv
import datetime as dt
import decimal
import json
import sys
import urllib.error
import urllib.request

from sf import ROOT, connect, fq

SV = fq("TRUST_DEMO_DEV") + ".TRUST_DEMO_SV"
OUT = ROOT / "seeds" / "cortex_answers.csv"
COLS = ["question_id", "question", "generated_sql", "answer_value", "request_id", "run_ts",
        "analyst_text", "execution_error", "row_count"]


def ask(host: str, token: str, question: str):
    body = json.dumps({"messages": [{"role": "user", "content": [{"type": "text", "text": question}]}],
                       "semantic_view": SV}).encode()
    req = urllib.request.Request(
        f"https://{host}/api/v2/cortex/analyst/message", data=body, method="POST",
        headers={"Authorization": f'Snowflake Token="{token}"', "Content-Type": "application/json",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def pick(row, numeric: bool):
    cells = [c for c in row if c is not None]
    want = [c for c in cells if isinstance(c, (int, float, decimal.Decimal)) == numeric]
    if not want:
        return ""
    return want[0] if not numeric else want[-1]


def main() -> int:
    force = "--force" in sys.argv
    if OUT.exists() and not force:
        print(f"{OUT.name} already exists: frozen. Refusing to spend again (--force to override).")
        return 1
    with (ROOT / "seeds" / "question_pack.csv").open() as f:
        pack = list(csv.DictReader(f))
    conn = connect()
    cur = conn.cursor()
    cur.execute("USE WAREHOUSE MISSION_OS_WH")
    rows = []
    for i, q in enumerate(pack):
        status, resp = ask(conn.host, conn.rest.token, q["question"])
        run_ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if status in (401, 403) and i == 0:
            print(f"auth refused on first call (HTTP {status}); nothing recorded, nothing spent.")
            return 2
        content = (resp.get("message") or {}).get("content") or []
        text = " ".join(c.get("text", "") for c in content if c.get("type") == "text").strip()
        sql = next((c.get("statement", "") for c in content if c.get("type") == "sql"), "")
        if status != 200:
            text = f"HTTP {status}: {resp.get('message', '')} {resp.get('code', '')}".strip()
        err, value, n = "", "", 0
        if sql:
            try:
                cur.execute(sql)
                res = cur.fetchall()
                n = len(res)
                numeric = q["expected_answer"].replace(".", "", 1).lstrip("-").isdigit()
                if res:
                    value = pick(res[0], numeric)
            except Exception as e:  # recorded, not hidden: the failure is the evidence
                err = " ".join(str(e).split())[:300]
        rows.append({"question_id": q["question_id"], "question": q["question"], "generated_sql": " ".join(sql.split()),
                     "answer_value": value, "request_id": resp.get("request_id", ""), "run_ts": run_ts,
                     "analyst_text": " ".join(text.split()), "execution_error": err, "row_count": n})
        print(q["question_id"], "http", status, "sql" if sql else "no-sql", "err" if err else "ok", flush=True)
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print("wrote", OUT, len(rows), "rows;", sum(1 for r in rows if r["request_id"]), "request ids")
    return 0


if __name__ == "__main__":
    sys.exit(main())
