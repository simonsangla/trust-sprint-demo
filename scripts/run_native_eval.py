#!/usr/bin/env python3
"""Run ONE native Cortex Analyst evaluation over the question pack and freeze the result.

Docs: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst-evaluations
  - eval set = verified queries (question + expected SQL) on a semantic view
  - run      = CALL EXECUTE_AI_EVALUATION('START', OBJECT_CONSTRUCT('run_name', ...), '@stage/config.yaml')
  - results  = SNOWFLAKE.LOCAL.GET_ANALYST_AI_EVALUATION_DATA(db, schema, view, 'SEMANTIC VIEW', run_name)

Never alters or replaces an existing object: the original TRUST_DEMO_SV is untouched. The verified queries live on a NEW
view, TRUST_DEMO_SV_EVAL (same definition + AI_VERIFIED_QUERIES), created IF NOT EXISTS. Only MISSION_OS_DB.TRUST_DEMO_DEV.
Each expected SQL is run against the data and must return the pack's expected value before anything is loaded.
Q10 (churn) has no expected SQL (the right answer is a refusal, which a verified query cannot express): not in the eval set.
Refuses to overwrite seeds/native_eval_results.csv (--force to re-spend).

Usage: SNOWFLAKE_DEFAULT_CONNECTION_NAME=mission_os_dogfood uv run --with 'snowflake-connector-python[secure-local-storage]' python scripts/run_native_eval.py
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

from sf import ROOT, connect, fq, run, semantic_view_sql

SCHEMA = "TRUST_DEMO_DEV"
LOC = fq(SCHEMA)
SV = f"{LOC}.TRUST_DEMO_SV_EVAL"
STAGE = f"{LOC}.NATIVE_EVAL_CFG"
FMT = f"{LOC}.NATIVE_EVAL_YAML_FMT"
METRIC_VERSION = "v3"
OUT = ROOT / "seeds" / "native_eval_results.csv"
COLS = ["question_id", "native_judgement", "native_score", "judge_version", "eval_run_id", "run_ts", "native_explanation"]

# Expected SQL per question, written against the semantic view. Conversion rate filters on the SESSION date only
# (the metric's denominator is sessions); that is what the owner-confirmed value 0.0809 / 0.0879 is.
def _w(col: str, a: str, b: str) -> str:
    return f"{col} >= ''{a}'' AND {col} <= ''{b}''"

EXPECTED = {
    "Q01": ("bookings_march_2026", 22,
            f"SELECT * FROM SEMANTIC_VIEW({SV} METRICS bookings.bookings WHERE {_w('bookings.booking_date','2026-03-01','2026-03-31')})"),
    "Q02": ("revenue_q1_2026", 6983.0,
            f"SELECT * FROM SEMANTIC_VIEW({SV} METRICS bookings.revenue WHERE {_w('bookings.booking_date','2026-01-01','2026-03-31')})"),
    "Q03": ("active_users_april_2026", 196,
            f"SELECT * FROM SEMANTIC_VIEW({SV} METRICS sessions.active_users WHERE {_w('sessions.session_date','2026-04-01','2026-04-30')})"),
    "Q04": ("conversion_rate_june_2026", 0.0809,
            f"SELECT * FROM SEMANTIC_VIEW({SV} METRICS conversion_rate WHERE {_w('sessions.session_date','2026-06-01','2026-06-30')})"),
    "Q05": ("conversion_rate_organic_h1_2026", 0.0879,
            f"SELECT * FROM SEMANTIC_VIEW({SV} METRICS conversion_rate WHERE sessions.channel = ''organic'' AND {_w('sessions.session_date','2026-01-01','2026-06-30')})"),
    "Q06": ("conversion_rate_partner_jan_2026", None,
            f"SELECT bookings / NULLIF(session_count, 0) AS conversion_rate FROM SEMANTIC_VIEW({SV} METRICS bookings.bookings, sessions.session_count WHERE sessions.channel = ''partner'' AND {_w('sessions.session_date','2026-01-01','2026-01-31')})"),
    "Q07": ("top_channel_by_revenue_h1_2026", "organic",
            f"SELECT channel FROM SEMANTIC_VIEW({SV} DIMENSIONS sessions.channel METRICS bookings.revenue WHERE {_w('bookings.booking_date','2026-01-01','2026-06-30')}) ORDER BY revenue DESC LIMIT 1"),
    "Q08": ("avg_booking_value_h1_2026", 97.0,
            f"SELECT revenue / NULLIF(bookings, 0) AS avg_booking_value FROM SEMANTIC_VIEW({SV} METRICS bookings.revenue, bookings.bookings WHERE {_w('bookings.booking_date','2026-01-01','2026-06-30')})"),
    "Q09": ("paying_customers", 134,
            f"SELECT COUNT(*) AS paying_customers FROM {LOC}.USERS WHERE plan <> ''free''"),
}


def sq(s: str) -> str:
    """SQL as written above doubles quotes for embedding in the DDL string; undo for direct execution."""
    return s.replace("''", "'")


def verify_expected(cur, pack):
    """Every expected SQL must reproduce the pack's expected value on the live data. Returns the list of failures."""
    bad = []
    for qid, (_, want, sql) in EXPECTED.items():
        cur.execute(sq(sql))
        row = cur.fetchall()
        got = row[0][0] if row else None
        tol = float(pack[qid]["tolerance"] or 0)
        if want is None:
            ok = got is None
        elif isinstance(want, str):
            ok = str(got).lower() == want
        else:
            ok = got is not None and abs(float(got) - float(want)) <= max(tol, 1e-9)
        print(f"  expected-sql {qid}: got {got!r} want {want!r} -> {'OK' if ok else 'MISMATCH'}", flush=True)
        if not ok:
            bad.append(qid)
    return bad


def main() -> int:
    force = "--force" in sys.argv
    if OUT.exists() and not force:
        print(f"{OUT.name} already exists: frozen. Refusing to spend again (--force to override).")
        return 1
    with (ROOT / "seeds" / "question_pack.csv").open() as f:
        pack = {r["question_id"]: r for r in csv.DictReader(f)}
    conn = connect()
    cur = conn.cursor()
    run(cur, "USE WAREHOUSE MISSION_OS_WH")
    run(cur, f"USE DATABASE MISSION_OS_DB")
    run(cur, f"USE SCHEMA {SCHEMA}")

    # 0. the expected SQL must hold against the original view's data BEFORE it is loaded anywhere.
    #    SV does not exist yet on a first run, so verify against the original view by name substitution.
    global_sv_orig = f"{LOC}.TRUST_DEMO_SV"
    probe = {k: (v[0], v[1], v[2].replace(SV, global_sv_orig)) for k, v in EXPECTED.items()}
    saved = dict(EXPECTED)
    EXPECTED.update(probe)
    bad = verify_expected(cur, pack)
    EXPECTED.update(saved)
    if bad:
        print("expected SQL disagrees with the pack for", bad, "- nothing loaded.")
        return 2

    # 1. NEW semantic view with the verified queries (IF NOT EXISTS; original untouched).
    ddl = semantic_view_sql(SCHEMA).rstrip().rstrip(";")
    ddl = ddl.replace(f"{LOC}.TRUST_DEMO_SV\n", f"{SV}\n", 1)
    vqs = ",\n    ".join(
        f"{name} AS (QUESTION '{pack[qid]['question']}' VERIFIED_BY '(owner = {pack[qid]['owner']})' SQL '{sql}')"
        for qid, (name, _, sql) in EXPECTED.items())
    ddl += f"\n  AI_VERIFIED_QUERIES (\n    {vqs}\n  );"
    run(cur, ddl)
    print("semantic view ready:", SV, flush=True)

    # 2. evaluation config on a stage
    run(cur, f"CREATE FILE FORMAT IF NOT EXISTS {FMT} TYPE='CSV' FIELD_DELIMITER=NONE RECORD_DELIMITER='\\n' SKIP_HEADER=0 "
             f"FIELD_OPTIONALLY_ENCLOSED_BY=NONE ESCAPE_UNENCLOSED_FIELD=NONE")
    run(cur, f"CREATE STAGE IF NOT EXISTS {STAGE} FILE_FORMAT = {FMT}")
    qlines = "\n".join(f'      - "{pack[q]["question"]}"' for q in EXPECTED)
    yaml_text = (f'evaluation:\n  analyst_params:\n    analyst_name: "{SV}"\n    analyst_type: "SEMANTIC VIEW"\n'
                 f'  source_metadata:\n    type: "verified_queries"\n    verified_queries:\n{qlines}\n'
                 f'metrics:\n  - name: "sql_correctness"\n    version: "{METRIC_VERSION}"\n')
    run_name = "trust_sprint_native_eval_" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "analyst_evaluation_config.yaml"
        p.write_text(yaml_text)
        run(cur, f"PUT file://{p} @{STAGE} AUTO_COMPRESS=FALSE OVERWRITE=TRUE")

    # 3. START one run, poll STATUS
    cfg = f"@{STAGE}/analyst_evaluation_config.yaml"
    cur.execute("CALL EXECUTE_AI_EVALUATION('START', OBJECT_CONSTRUCT('run_name', %s), %s)", (run_name, cfg))
    print("START:", cur.fetchall()[0][0][:300], flush=True)
    t0 = time.time()
    while time.time() - t0 < 900:
        time.sleep(20)
        cur.execute("CALL EXECUTE_AI_EVALUATION('STATUS', OBJECT_CONSTRUCT('run_name', %s), %s)", (run_name, cfg))
        st = str(cur.fetchall()[0][0])
        print("STATUS:", " ".join(st.split())[:200], flush=True)
        if any(w in st.upper() for w in ("COMPLETED", "FAILED", "CANCELLED", "ERROR")):
            break

    # 4. results
    cur.execute("SELECT * FROM TABLE(SNOWFLAKE.LOCAL.GET_ANALYST_AI_EVALUATION_DATA(%s, %s, %s, 'SEMANTIC VIEW', %s))",
                ("MISSION_OS_DB", SCHEMA, "TRUST_DEMO_SV_EVAL", run_name))
    names = [c[0] for c in cur.description]
    recs = [dict(zip(names, r)) for r in cur.fetchall()]
    raw = ROOT / "logs" / f"{run_name}_raw.json"
    raw.parent.mkdir(exist_ok=True)
    raw.write_text(json.dumps(recs, default=str, indent=1))
    by_q = {pack[q]["question"]: q for q in EXPECTED}
    rows = []
    for r in recs:
        qid = by_q.get(str(r["INPUT"]).strip())
        if not qid or r["METRIC_NAME"] is None:
            continue
        score = r["EVAL_AGG_SCORE"]
        score = float(score) if isinstance(score, Decimal) else score
        calls = r["METRIC_CALLS"]
        calls = json.loads(calls) if isinstance(calls, str) else (calls or [])
        expl = " ".join(str(c.get("explanation", "")) for c in calls if isinstance(c, dict))
        ts = r["TIMESTAMP"].astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows.append({"question_id": qid, "native_judgement": "correct" if score and score >= 0.5 else "incorrect",
                     "native_score": score, "judge_version": METRIC_VERSION, "eval_run_id": run_name, "run_ts": ts,
                     "native_explanation": " ".join(expl.split())[:600]})
    rows.sort(key=lambda x: x["question_id"])
    got = {r["question_id"] for r in rows}
    for q in pack:  # questions the native eval could not take are recorded, not dropped
        if q not in got:
            rows.append({"question_id": q, "native_judgement": "not_evaluated", "native_score": "",
                         "judge_version": METRIC_VERSION, "eval_run_id": run_name,
                         "run_ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "native_explanation": "No verified query: a refusal cannot be expressed as expected SQL." if q == "Q10" else "No result returned."})
    rows.sort(key=lambda x: x["question_id"])
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print("wrote", OUT, len(rows), "rows; run", run_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
