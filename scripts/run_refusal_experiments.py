"""E1/E2/E3 refusal experiments (mission-os#1362). DEV schema, new views only."""
import csv, sys, collections
sys.path.insert(0, "/Users/simonsangla/projects/trust-sprint-demo/scripts")
sys.path.insert(0, "/private/tmp/claude-501/-Users-simonsangla-projects/27d6e16f-e4ca-41ad-83e8-ed58cbd50749/scratchpad/t1")
from sf import connect, run
import run_cortex as rc
import make_refusal_views as mv
OUT = sys.argv[1]; N = 5
pack = {r["question_id"]: r for r in csv.DictReader(open("/Users/simonsangla/projects/trust-sprint-demo/seeds/question_pack.csv"))}
P = "MISSION_OS_DB.TRUST_DEMO_DEV."
CHURN = "What is our customer churn rate?"
UNDEF = {"LTV": "What is our customer lifetime value?", "NPS": "What is our NPS?", "RET": "What is our 90-day retention rate?"}
views = {f"TRUST_DEMO_SV_ONLY{q}": ([q], "") for q in ["Q04", "Q05", "Q06", "Q07", "Q08"]}
views["TRUST_DEMO_SV_ONLYQ09_RULE"] = (["Q09"], mv.RULE)
conn = connect(); cur = conn.cursor()
for s in ("USE WAREHOUSE MISSION_OS_WH", "USE DATABASE MISSION_OS_DB", f"USE SCHEMA {mv.SCHEMA}"):
    run(cur, s)
for name, (ids, rules) in views.items():
    run(cur, mv.build(name, ids, pack, rules)); print("built", name, flush=True)
plan = [("E1", v, "CHURN", CHURN) for v in views if v != "TRUST_DEMO_SV_ONLYQ09_RULE"]
plan += [("E2", v, k, q) for v in ("TRUST_DEMO_SV", "TRUST_DEMO_SV_ONLYQ09") for k, q in UNDEF.items()]
plan += [("E3", "TRUST_DEMO_SV_ONLYQ09_RULE", "CHURN", CHURN)]
rows = []
for exp, v, k, q in plan:
    rc.SV = P + v
    for i in range(N):
        st, resp = rc.ask(conn.host, conn.rest.token, q)
        if st in (401, 403): print("auth", st); sys.exit(2)
        content = (resp.get("message") or {}).get("content") or []
        text = " ".join(c.get("text", "") for c in content if c.get("type") == "text").strip()
        sql = next((c.get("statement", "") for c in content if c.get("type") == "sql"), "")
        val = ""
        if sql:
            try:
                cur.execute(sql); r = cur.fetchall(); val = str(r[0]) if r else "EMPTY"
            except Exception as e: val = "ERR " + str(e)[:60]
        kind = "sql" if sql else ("suggestions" if any(c.get("type") == "suggestions" for c in content) else "text_only")
        rows.append(dict(exp=exp, view=v, q=k, run=i + 1, http=st, kind=kind, value=val,
                         text=" ".join(text.split())[:400], sql=" ".join(sql.split())[:600], request_id=resp.get("request_id", "")))
        print(exp, v, k, i + 1, kind, val[:40], flush=True)
with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
c = collections.Counter((r["exp"], r["view"], r["q"], r["kind"]) for r in rows)
for k, n in sorted(c.items()): print(n, *k)
