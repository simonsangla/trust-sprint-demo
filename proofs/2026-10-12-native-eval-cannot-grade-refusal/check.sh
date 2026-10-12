#!/usr/bin/env bash
# Proof: Snowflake's native Cortex Analyst evaluation grades the analyst's SQL against verified queries
# (a question paired with its expected SQL). A question whose right answer is a refusal has no expected SQL,
# so it cannot be in the evaluation set. This script, fully offline:
# (1) extracts HEAD into a temp dir (git archive), (2) reads seeds/question_pack.csv, seeds/metric_registry.csv
# and the EXPECTED verified-query table in scripts/run_native_eval.py, (3) counts the questions that can be
# graded (have an expected SQL) and the refusal questions left out, (4) requires that no question on an
# undefined metric carries an expected SQL, and (5) gives Q10 (churn) a fake expected SQL and value on a copy
# and requires the check to go RED. No Snowflake call. REF=<rev> checks another commit than HEAD.
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
for d in clean mutated; do mkdir -p "$W/$d"; git -C "$ROOT" archive "${REF:-HEAD}" | tar -x -C "$W/$d"; done

judge(){ python3 -I - "$1" <<'PY'
import csv, re, sys
root = sys.argv[1]
pack = list(csv.DictReader(open(root + "/seeds/question_pack.csv")))
reg = {r["metric_key"]: r["status"] for r in csv.DictReader(open(root + "/seeds/metric_registry.csv"))}
src = open(root + "/scripts/run_native_eval.py").read()
m = re.search(r"^EXPECTED = \{(.*?)^\}", src, re.S | re.M)
if not m:
    print("FAIL: EXPECTED table not found in scripts/run_native_eval.py"); sys.exit(2)
vq = set(re.findall(r'^\s+"(Q\d\d)": \(', m.group(1), re.M))
if len(pack) != 10 or not vq:
    print("FAIL: expected 10 questions and a non-empty EXPECTED table"); sys.exit(2)
ids = {r["question_id"] for r in pack}
refusal = [r["question_id"] for r in pack if r["expect_refusal"] == "true"]
undefined = [r["question_id"] for r in pack if reg.get(r["metric_key"]) == "undefined"]
gradable = sorted(vq & ids)
excluded = sorted(ids - vq)
print("verified queries (question + expected SQL): %s" % " ".join(gradable))
print("refusal questions in the pack: %s; on an undefined metric: %s" % (" ".join(refusal), " ".join(undefined)))
print("gradable %d of %d; refusal questions excluded %d (%s)" % (len(gradable), len(pack), len(excluded), " ".join(excluded)))
bad = 0
for q in undefined:
    if q in vq:
        print("FAIL: %s is on an undefined metric but carries an expected SQL" % q); bad = 1
for q in excluded:
    if q not in refusal:
        print("FAIL: %s is excluded but is not a refusal question" % q); bad = 1
if not undefined:
    print("FAIL: no undefined-metric question; nothing to test"); bad = 1
print("COUNTS %d %d %d %d" % (len(gradable), len(pack), len(excluded), len(refusal)))
sys.exit(bad)
PY
}

fail=0
out=$(judge "$W/clean"); rc=$?; printf '%s\n' "$out" | grep -v '^COUNTS'
[ "$rc" = 0 ] || { echo "FAIL: clean tree does not hold"; fail=1; }
read -r G N X R <<EOF2
$(printf '%s\n' "$out" | awk '/^COUNTS/{print $2, $3, $4, $5}')
EOF2
{ [ "${G:-}" = 9 ] && [ "${X:-}" = 1 ]; } || { echo "FAIL: expected 9 gradable and 1 excluded, got ${G:-?} and ${X:-?}"; fail=1; }

# mutation: Q10 gets a fake verified query (expected SQL + value), as if churn were gradable
python3 -I - "$W/mutated/scripts/run_native_eval.py" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
anchor = '    "Q09": ('
if anchor not in s:
    sys.exit("anchor missing")
s = s.replace(anchor, '    "Q10": ("churn_rate", 0.12,\n            f"SELECT 0.12 AS churn_rate"),\n' + anchor, 1)
open(p, "w").write(s)
PY
cmp -s "$W/clean/scripts/run_native_eval.py" "$W/mutated/scripts/run_native_eval.py" && { echo "FAIL: mutation changed nothing"; exit 1; }
mout=$(judge "$W/mutated"); mrc=$?
if [ "$mrc" = 0 ]; then echo "FAIL: check stayed green with a fake expected SQL for Q10"; fail=1; verdict="STILL GREEN"; else verdict=RED; fi
echo "mutation: Q10 given fake expected SQL 'SELECT 0.12' -> $verdict ($(printf '%s\n' "$mout" | grep '^FAIL' | head -1))"
[ "$fail" = 0 ] || exit 1
echo "PASS: the native evaluation can grade $G of $N questions; $X refusal question (Q10 churn) cannot be expressed as a verified query"
echo "NUMBERS: gradable=$G of $N; refusal_excluded=$X; refusal_questions=$R; mutation=RED"
