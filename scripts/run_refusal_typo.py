#!/usr/bin/env python3
"""Single-turn checks, N runs each (default 5):
  TYPO     'chrun rate' with NO prior turn on ONLYQ09_RULE (does the typo alone bypass the rule?)
  UNCLEAR  churn on ONLYQ09_UNCLEAR (documented UNCLEAR keyword)
Usage: python scripts/run_refusal_typo.py <out.csv> [N]"""
from __future__ import annotations
import csv, json, sys, collections, urllib.request, urllib.error
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf import connect  # noqa: E402

P = "MISSION_OS_DB.TRUST_DEMO_DEV.TRUST_DEMO_SV"
CELLS = [("TYPO", "_ONLYQ09_RULE", "chrun rate"), ("UNCLEAR", "_ONLYQ09_UNCLEAR", "What is our customer churn rate?")]


def ask(host, token, sv, q):
    body = json.dumps({"messages": [{"role": "user", "content": [{"type": "text", "text": q}]}], "semantic_view": sv}).encode()
    req = urllib.request.Request(f"https://{host}/api/v2/cortex/analyst/message", data=body, method="POST",
                                 headers={"Authorization": f'Snowflake Token="{token}"', "Content-Type": "application/json",
                                          "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}


def main() -> int:
    out, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5
    conn = connect(); cur = conn.cursor(); cur.execute("USE WAREHOUSE MISSION_OS_WH")
    rows = []
    for cell, suf, q in CELLS:
        for i in range(1, n + 1):
            st, resp = ask(conn.host, conn.rest.token, P + suf, q)
            if st in (401, 403):
                print("auth refused", st); return 2
            content = (resp.get("message") or {}).get("content") or []
            text = " ".join(" ".join(c.get("text", "") for c in content if c.get("type") == "text").split())
            sql = next((c.get("statement", "") for c in content if c.get("type") == "sql"), "")
            val = ""
            if sql:
                try:
                    cur.execute(sql); r = cur.fetchall(); val = str(r[0]) if r else "EMPTY"
                except Exception as e:  # keep as evidence
                    val = "ERR " + str(e)[:60]
            kind = "sql" if sql else ("suggestions" if any(c.get("type") == "suggestions" for c in content) else "text_only")
            rows.append(dict(cell=cell, view=(P + suf).split(".")[-1], q=q, run=i, http=st, kind=kind, value=val,
                             text=text[:600], sql=" ".join(sql.split())[:600], request_id=resp.get("request_id", "")))
            print(cell, i, kind, val[:50], "|", text[:80], flush=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    for k, c in sorted(collections.Counter((r["cell"], r["kind"]) for r in rows).items()):
        print(c, *k)
    return 0


if __name__ == "__main__":
    sys.exit(main())
