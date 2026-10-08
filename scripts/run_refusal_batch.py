#!/usr/bin/env python3
"""Fresh uniform batch for the Cortex refusal finding (mission-os #1362).
Direct Cortex Analyst REST API, one semantic view per edit, every returned SQL executed, every row appended to the CSV
as soon as it exists (a crash loses nothing; rerunning the same command resumes and skips rows already present).
  python scripts/run_refusal_batch.py <out.csv> [--n 20] [--n-control 5] [--batch-id ID] [--script-sha SHA]
Cells: churn x n on Edits 0-3; typo follow-up ("churn rate" then "chrun rate") x n conversations on Edit 2;
control question that must be answered (Q02, expected 6983.0) x n-control on every edit view.
Calls: 4n + 2n + 4*n_control (n=20, n_control=5 -> 140)."""
from __future__ import annotations
import argparse, csv, datetime as dt, json, subprocess, sys, urllib.error, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf import connect  # noqa: E402

P = "MISSION_OS_DB.TRUST_DEMO_DEV."
EDITS = [("E0", "TRUST_DEMO_SV"), ("E1", "TRUST_DEMO_SV_ONLYQ09"), ("E2", "TRUST_DEMO_SV_ONLYQ09_RULE"), ("E3", "TRUST_DEMO_SV_ONLYQ09_W3")]
CHURN, TYPO, CONTROL = "What is our customer churn rate?", "chrun rate", "What was total revenue in Q1 2026?"
COLS = ["batch_id", "script_sha", "ts", "cell", "edit", "view", "run", "turn", "q", "http", "kind", "value", "text", "sql", "request_id"]


def ask(host, token, view, messages):
    body = json.dumps({"messages": messages, "semantic_view": P + view}).encode()
    req = urllib.request.Request(f"https://{host}/api/v2/cortex/analyst/message", data=body, method="POST",
                                 headers={"Authorization": f'Snowflake Token="{token}"', "Content-Type": "application/json",
                                          "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}


def parse(cur, resp):
    content = (resp.get("message") or {}).get("content") or []
    text = " ".join(" ".join(c.get("text", "") for c in content if c.get("type") == "text").split())
    sql = next((c.get("statement", "") for c in content if c.get("type") == "sql"), "")
    val = ""
    if sql:
        try:
            cur.execute(sql); r = cur.fetchall(); val = str(r[0]) if r else "EMPTY"
        except Exception as e:  # kept as evidence
            val = "ERR " + str(e)[:80]
    kind = "sql" if sql else ("suggestions" if any(c.get("type") == "suggestions" for c in content) else "text_only")
    return content, kind, val, text, " ".join(sql.split())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--n", type=int, default=20); ap.add_argument("--n-control", type=int, default=5)
    ap.add_argument("--batch-id", default=dt.date.today().isoformat())
    ap.add_argument("--script-sha", default="", help="commit of this script when run from an export without .git")
    a = ap.parse_args()
    sha = subprocess.run(["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True).stdout.strip() or a.script_sha or "uncommitted"
    out = Path(a.out); done = set()
    if out.exists():
        done = {(r["cell"], r["edit"], r["run"], r["turn"]) for r in csv.DictReader(out.open())}
    fh = out.open("a", newline=""); w = csv.DictWriter(fh, fieldnames=COLS)
    if not done:
        w.writeheader()
    conn = connect(); cur = conn.cursor(); cur.execute("USE WAREHOUSE MISSION_OS_WH")
    plan = [("churn", e, v, i) for e, v in EDITS for i in range(1, a.n + 1)]
    plan += [("control", e, v, i) for e, v in EDITS for i in range(1, a.n_control + 1)]
    plan += [("typo_followup", "E2", "TRUST_DEMO_SV_ONLYQ09_RULE", i) for i in range(1, a.n + 1)]
    calls = 0
    for cell, edit, view, i in plan:
        q1 = CONTROL if cell == "control" else CHURN
        turns = [(1, q1)] + ([(2, TYPO)] if cell == "typo_followup" else [])
        if all((cell, edit, str(i), str(t)) in done for t, _ in turns):
            continue
        msgs = []
        for t, q in turns:
            msgs.append({"role": "user", "content": [{"type": "text", "text": q}]})
            st, resp = ask(conn.host, conn.rest.token, view, msgs); calls += 1
            if st in (401, 403):
                print("auth refused", st); return 2
            content, kind, val, text, sql = parse(cur, resp)
            msgs.append({"role": "analyst", "content": content})
            if (cell, edit, str(i), str(t)) not in done:
                w.writerow(dict(batch_id=a.batch_id, script_sha=sha, ts=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                                cell=cell, edit=edit, view=view, run=i, turn=t, q=q, http=st, kind=kind, value=val,
                                text=text[:800], sql=sql[:800], request_id=resp.get("request_id", "")))
                fh.flush()
            print(cell, edit, i, t, kind, val[:40], flush=True)
    fh.close()
    print("calls", calls)
    return 0


if __name__ == "__main__":
    sys.exit(main())
