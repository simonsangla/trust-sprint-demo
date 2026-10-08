#!/usr/bin/env python3
"""Zero-guard evidence run (mission-os #1377): the same zero-denominator question on the demo view (unguarded
conversion_rate) and on TRUST_DEMO_SV_ZG (NULLIF guard). Appends every row as it lands and resumes on rerun.
    python scripts/run_zero_guard.py <out.csv> [--n 20] [--n-control 5] [--batch-id ID] [--script-sha SHA]
Cells per view: probe P1 (no dimension) / P2 (by channel) / P3 (components) as direct SQL, Cortex Q06 x n,
control (Q1 revenue, expected 6983) x n_control. Calls: 2 * (n + n_control) Cortex + 6 SQL probes."""
from __future__ import annotations
import argparse, csv, datetime as dt, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf import connect  # noqa: E402
from run_refusal_batch import ask, parse  # noqa: E402  (same Analyst REST call and SQL execution as the refusal batch)

VIEWS = [("BASE", "TRUST_DEMO_SV"), ("GUARDED", "TRUST_DEMO_SV_ZG")]
P = "MISSION_OS_DB.TRUST_DEMO_DEV."
W = ("sessions.channel = 'partner' AND sessions.session_date >= '2026-01-01' "
     "AND sessions.session_date <= '2026-01-31'")
PROBES = [("P1", "METRICS conversion_rate WHERE " + W),
          ("P2", "DIMENSIONS sessions.channel METRICS conversion_rate WHERE " + W),
          ("P3", "METRICS bookings.bookings, sessions.session_count WHERE " + W)]
Q06 = "What was the booking conversion rate for the partner channel in January 2026?"
CONTROL = "What was total revenue in Q1 2026?"
COLS = ["batch_id", "script_sha", "ts", "cell", "view", "run", "q", "http", "kind", "value", "text", "sql", "request_id"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--n", type=int, default=20); ap.add_argument("--n-control", type=int, default=5)
    ap.add_argument("--batch-id", default=dt.date.today().isoformat()); ap.add_argument("--script-sha", default="uncommitted")
    a = ap.parse_args()
    out = Path(a.out); done = set()
    if out.exists():
        done = {(r["cell"], r["view"], r["run"]) for r in csv.DictReader(out.open())}
    fh = out.open("a", newline=""); w = csv.DictWriter(fh, fieldnames=COLS)
    if not done:
        w.writeheader()
    conn = connect(); cur = conn.cursor(); cur.execute("USE WAREHOUSE MISSION_OS_WH")
    now = lambda: dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    base = dict(batch_id=a.batch_id, script_sha=a.script_sha)
    for vk, view in VIEWS:
        for name, clause in PROBES:
            if (name, vk, "1") in done:
                continue
            sql = f"SELECT * FROM SEMANTIC_VIEW({P}{view} {clause})"
            try:
                cur.execute(sql); r = cur.fetchall(); val = str(r[0]) if r else "EMPTY"
            except Exception as e:  # the error is the evidence
                val = "ERR " + str(e).replace("\n", " ")[:120]
            w.writerow({**base, "ts": now(), "cell": name, "view": vk, "run": 1, "q": "direct SQL", "http": "", "kind": "sql",
                        "value": val, "text": "", "sql": sql, "request_id": ""}); fh.flush()
            print(name, vk, val[:60], flush=True)
        for cell, q, n in (("q06", Q06, a.n), ("control", CONTROL, a.n_control)):
            for i in range(1, n + 1):
                if (cell, vk, str(i)) in done:
                    continue
                st, resp = ask(conn.host, conn.rest.token, view, [{"role": "user", "content": [{"type": "text", "text": q}]}])
                if st in (401, 403):
                    print("auth refused", st); return 2
                _, kind, val, text, sql = parse(cur, resp)
                w.writerow({**base, "ts": now(), "cell": cell, "view": vk, "run": i, "q": q, "http": st, "kind": kind,
                            "value": val, "text": text[:800], "sql": sql[:800], "request_id": resp.get("request_id", "")}); fh.flush()
                print(cell, vk, i, kind, val[:50], flush=True)
    fh.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
