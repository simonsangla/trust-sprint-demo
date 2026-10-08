"""Replication loop for the refusal findings (mission-os#1362). Existing DEV views, N=5 per cell.
Usage: python replicate.py <out.csv>"""
import csv, json, sys, collections, urllib.request, urllib.error
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf import connect
N = 5
P = "MISSION_OS_DB.TRUST_DEMO_DEV.TRUST_DEMO_SV"
CH = "What is our customer churn rate?"
CELLS = [("F1", "", CH), ("F2", "_ONLYQ09", CH), ("F2-ctrl", "_ONLYQ04", CH), ("F2-alt", "_ONLYQ08", CH),
         ("F2-LTV", "_ONLYQ09", "What is our customer lifetime value?"),
         ("F2-RET", "_ONLYQ09", "What is our 90-day retention rate?"),
         ("F3", "_ONLYQ09_RULE", CH), ("F4-W2", "_ONLYQ09_W2", CH), ("F4-W3", "_ONLYQ09_W3", CH)]

def ask(host, token, sv, messages):
    body = json.dumps({"messages": messages, "semantic_view": sv}).encode()
    req = urllib.request.Request(f"https://{host}/api/v2/cortex/analyst/message", data=body, method="POST",
        headers={"Authorization": f'Snowflake Token="{token}"', "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r: return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except Exception: return e.code, {}

def parse(cur, resp):
    content = (resp.get("message") or {}).get("content") or []
    text = " ".join(c.get("text", "") for c in content if c.get("type") == "text").strip()
    sql = next((c.get("statement", "") for c in content if c.get("type") == "sql"), "")
    val = ""
    if sql:
        try: cur.execute(sql); r = cur.fetchall(); val = str(r[0]) if r else "EMPTY"
        except Exception as e: val = "ERR " + str(e)[:60]
    kind = "sql" if sql else ("suggestions" if any(c.get("type") == "suggestions" for c in content) else "text_only")
    return content, kind, val, " ".join(text.split()), " ".join(sql.split())

conn = connect(); cur = conn.cursor(); cur.execute("USE WAREHOUSE MISSION_OS_WH")
rows = []
def rec(cell, sv, q, i, turn, st, kind, val, text, sql, rid):
    rows.append(dict(cell=cell, view=sv.split(".")[-1], q=q, run=i, turn=turn, http=st, kind=kind, value=val,
                     text=text[:600], sql=sql[:600], request_id=rid))
    print(cell, i, turn, kind, val[:40], "|", text[:70], flush=True)
for cell, suf, q in CELLS:
    for i in range(1, N + 1):
        st, resp = ask(conn.host, conn.rest.token, P + suf, [{"role": "user", "content": [{"type": "text", "text": q}]}])
        if st in (401, 403): sys.exit("auth refused")
        _, kind, val, text, sql = parse(cur, resp)
        rec(cell, P + suf, q, i, 1, st, kind, val, text, sql, resp.get("request_id", ""))
# F6: two turns
for i in range(1, N + 1):
    m = [{"role": "user", "content": [{"type": "text", "text": CH}]}]
    st, r1 = ask(conn.host, conn.rest.token, P + "_ONLYQ09_RULE", m)
    c1, kind, val, text, sql = parse(cur, r1)
    rec("F6", P + "_ONLYQ09_RULE", CH, i, 1, st, kind, val, text, sql, r1.get("request_id", ""))
    m += [{"role": "analyst", "content": c1}, {"role": "user", "content": [{"type": "text", "text": "chrun rate"}]}]
    st, r2 = ask(conn.host, conn.rest.token, P + "_ONLYQ09_RULE", m)
    _, kind, val, text, sql = parse(cur, r2)
    rec("F6", P + "_ONLYQ09_RULE", "chrun rate", i, 2, st, kind, val, text, sql, r2.get("request_id", ""))
with open(sys.argv[1], "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
for k, n in sorted(collections.Counter((r["cell"], r["turn"], r["kind"]) for r in rows).items()): print(n, *k)
