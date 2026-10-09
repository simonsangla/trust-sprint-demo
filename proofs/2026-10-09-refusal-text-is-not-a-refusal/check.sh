#!/usr/bin/env bash
# Proof: an analyst that SAYS it cannot compute a metric has not necessarily refused. In the frozen 20-run batch
# (evidence/refusal_runs_2026-10-08/batch20.csv, 2026-10-08) the churn question was asked after four edits of the
# semantic view. This script (1) re-derives, with its own code, how many of the 20 runs per edit said "cannot be
# computed" and how many returned SQL whose result is a number, (2) checks the Q10 refusal of the original frozen run
# in seeds/cortex_answers.csv, (3) runs the pinned scripts/check_post_claims.py, and (4) repeats step 1 on a copy where
# the E2 numeric results are replaced by refusal text, and requires it to go RED.
# It also prints the two figures the public post cites (46.7%, 140 calls) and checks /refusal/ shows them with this proof id.
# Nothing here calls Snowflake; every number is read from committed, frozen files. REF=<rev> checks another commit.
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
for d in clean mutated; do mkdir -p "$W/$d"; git -C "$ROOT" archive "${REF:-HEAD}" | tar -x -C "$W/$d"; done
B=evidence/refusal_runs_2026-10-08/batch20.csv

# the mutation: every E2 churn run whose SQL returned a number now returns a refusal message instead
python3 -I - "$W/mutated/$B" <<'PY' || { echo "FAIL: mutation not applied"; exit 1; }
import csv, re, sys
p = sys.argv[1]
rows = list(csv.DictReader(open(p, newline="")))
cols = list(rows[0].keys()); n = 0
for r in rows:
    if r["cell"] == "churn" and r["edit"] == "E2" and r["kind"] == "sql" and re.match(r"^\(-?\d", r["value"]):
        r["value"] = "('Churn rate cannot be computed: no churn event.',)"; n += 1
if n == 0:
    sys.exit(1)
w = csv.DictWriter(open(p, "w", newline=""), fieldnames=cols); w.writeheader(); w.writerows(rows)
PY
cmp -s "$W/clean/$B" "$W/mutated/$B" && { echo "FAIL: mutation changed nothing"; exit 1; }

cat > "$W/derive.py" <<'PY'
# Independent of scripts/refusal_outcome.py: its own rules, from the raw columns only.
import csv, re, sys
SAYS_NO = re.compile(r"cannot be (?:\w+ )?(?:computed|calculated)|unable to|not a metric", re.I)
# a SQL result that is a number starts "(" then a digit; a refusal message starts "('"
IS_NUMBER = re.compile(r"^\(-?\d")
# what the public claims say (Thu 15 post and /refusal): (said no in words, SQL returned a number), of 20, per edit
CLAIM = {"E0": (20, 0), "E1": (0, 20), "E2": (20, 11), "E3": (None, 0)}  # E3 declines in other words: its wording is not counted, only that no SQL number came back
rows = list(csv.DictReader(open(sys.argv[1], newline="")))
bad = 0
for e, (said, num) in CLAIM.items():
    rs = [r for r in rows if r["cell"] == "churn" and r["edit"] == e]
    n = len(rs)
    got_said = sum(bool(SAYS_NO.search(r["text"])) for r in rs)
    got_num = sum(r["kind"] == "sql" and bool(IS_NUMBER.match(r["value"])) for r in rs)
    ok = n == 20 and (said is None or got_said == said) and got_num == num
    print("%s %s runs=%d said_no=%d sql_number=%d (claim %s / %d)" % ("ok  " if ok else "FAIL", e, n, got_said, got_num, "any" if said is None else said, num))
    bad += not ok
# the gap a text-only grader cannot see: E2 says no in 20 of 20 and still computes a number in 11
e2 = [r for r in rows if r["cell"] == "churn" and r["edit"] == "E2"]
gap = sum(bool(SAYS_NO.search(r["text"])) and r["kind"] == "sql" and bool(IS_NUMBER.match(r["value"])) for r in e2)
print("%s E2 said no AND computed a number in the same run: %d of %d" % ("ok  " if gap == 11 else "FAIL", gap, len(e2)))
bad += gap != 11
# 46.7%: the answer after the one unrelated verified query (E1), parsed from the SQL result itself (last decimal of the tuple)
e1 = [r for r in rows if r["cell"] == "churn" and r["edit"] == "E1" and r["kind"] == "sql" and IS_NUMBER.match(r["value"])]
vals = {re.findall(r"-?\d+\.\d+", r["value"])[-1] for r in e1}
pct = "%.1f%%" % (100 * float(next(iter(vals)))) if len(vals) == 1 else "mixed"
ok = len(e1) == 20 and pct == "46.7%"
print("%s E1 answer %s in %d of 20 runs (one distinct SQL result: %s)" % ("ok  " if ok else "FAIL", pct, len(e1), ", ".join(sorted(vals))))
bad += not ok
# 140: every row of the batch is one Cortex call with its own Snowflake request id
ids = {r["request_id"] for r in rows}
by = {c: sum(r["cell"] == c for r in rows) for c in ("churn", "control", "typo_followup")}
ok = len(rows) == 140 and len(ids) == 140 and all(r["http"] == "200" for r in rows) and by == {"churn": 80, "control": 20, "typo_followup": 40}
print("%s batch: %d Cortex calls, %d distinct request ids, HTTP 200 on all (churn %d, control %d, follow-up chat %d)" % ("ok  " if ok else "FAIL", len(rows), len(ids), by["churn"], by["control"], by["typo_followup"]))
bad += not ok
sys.exit(1 if bad else 0)
PY

fail=0
echo "== clean tree"
python3 -I "$W/derive.py" "$W/clean/$B" || { echo "FAIL: the 20-run counts do not match the claims"; fail=1; }

# Q10 in the original frozen run: refused, no SQL, no rows. Read straight from the seed.
python3 -I - "$W/clean/seeds/cortex_answers.csv" <<'PY' || { echo "FAIL: Q10 of the original run is not a clean refusal"; fail=1; }
import csv, sys
r = [x for x in csv.DictReader(open(sys.argv[1], newline="")) if x["question_id"] == "Q10"][0]
ok = r["generated_sql"] == "" and r["answer_value"] == "" and r["row_count"] == "0" and "unable to calculate" in r["analyst_text"]
print("%s Q10 original run: no SQL, no rows, text says unable to calculate; request %s" % ("ok  " if ok else "FAIL", r["request_id"]))
sys.exit(0 if ok else 1)
PY

(cd "$W/clean" && python3 scripts/check_post_claims.py >"$W/post.out" 2>&1) || { echo "FAIL: scripts/check_post_claims.py"; tail -n 5 "$W/post.out"; fail=1; }

echo "== mutated tree (E2 numeric results replaced by refusal text): must go RED"
if python3 -I "$W/derive.py" "$W/mutated/$B" >"$W/mut.out" 2>&1; then
  echo "FAIL: the check stayed green on the mutated batch"; fail=1
else
  echo "ok   mutated batch rejected: $(grep -c '^FAIL' "$W/mut.out") failing lines"
fi
# The public page carries this proof's id and the two figures (the committed page of the checked revision).
PID=proof_2026_10_09_refusal_text_is_not_a_refusal
pagecheck(){ grep -q "$PID" "$1" && grep -q '46\.7%' "$1" && grep -q '140 Cortex calls' "$1"; }
git -C "$ROOT" show "${REF:-HEAD}:site/refusal/index.html" > "$W/page.html" 2>/dev/null
if pagecheck "$W/page.html"; then echo "ok   site/refusal/ shows $PID, 46.7% and 140 Cortex calls"
else echo "FAIL: site/refusal/index.html lacks the proof id, 46.7% or 140 Cortex calls"; fail=1; fi
sed "s/$PID/proof_removed/g" "$W/page.html" > "$W/page_mut.html"
if pagecheck "$W/page_mut.html"; then echo "FAIL: the page check stayed green with the proof id removed"; fail=1
else echo "ok   page check rejects a page without the proof id"; fi
[ "$fail" = 0 ] || exit 1
echo "PASS: E0 0/20 number; E1 20/20 number; E2 said no 20/20 and computed a number 11/20; E3 0/20 number; E1 answer 46.7% in 20 of 20; 140 Cortex calls in the batch; /refusal/ shows the proof id; Q10 of the original run is a clean refusal; the check goes red when the E2 results are replaced"
