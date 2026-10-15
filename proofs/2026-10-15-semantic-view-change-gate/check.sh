#!/usr/bin/env bash
# Pre-merge gate: a semantic view edit must not change a known answer. Every question of seeds/question_pack.csv
# whose metric is defined in snowflake/semantic_view.sql is recomputed from the view's OWN metric expressions
# (parsed by svsql.py) over the frozen seeds on DuckDB, and compared with the owner's frozen expected_answer
# (within its tolerance; UNDEFINED must stay NULL). Then the same run on a copy where conversion_rate's
# denominator is redefined (sessions -> active users) must go RED. No Snowflake call, no spend.
# REF=<rev> checks another commit than HEAD.
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; HERE="$(cd "$(dirname "$0")" && pwd)"; DBT="${DBT:-dbt}"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
plain(){ sed 's/\x1b\[[0-9;]*m//g'; }
for d in clean mutated; do mkdir -p "$W/$d"; git -C "$ROOT" archive "${REF:-HEAD}" | tar -x -C "$W/$d"; done
# the planted regression: conversion_rate divided by active users instead of sessions
sed -i.bak 's|conversion_rate AS bookings.bookings / sessions.session_count|conversion_rate AS bookings.bookings / sessions.active_users|' "$W/mutated/snowflake/semantic_view.sql"
rm -f "$W/mutated/snowflake/semantic_view.sql.bak"
cmp -s "$W/clean/snowflake/semantic_view.sql" "$W/mutated/snowflake/semantic_view.sql" && { echo "FAIL: mutation changed nothing"; exit 1; }

gate(){ # $1 tree -> prints one line per question, exit 1 if any answer moved
  local t="$W/$1" ids sql="" q s n=0
  ids=$(python3 -I -c 'import csv,sys; print(" ".join(r["question_id"] for r in csv.DictReader(open(sys.argv[1]))))' "$t/seeds/question_pack.csv")
  for q in $ids; do
    s=$(python3 -I "$HERE/svsql.py" "$t" "$q"); rc=$?
    [ "$rc" = 3 ] && continue
    [ "$rc" = 0 ] || { echo "FAIL: svsql.py $q exited $rc: $s"; return 1; }
    n=$((n+1)); sql="$sql${sql:+ union all }select '$q' as q, coalesce(($s), 'NULL') as v"
  done
  [ "$n" -gt 0 ] || { echo "FAIL: no question maps to a semantic-view metric"; return 1; }
  (cd "$t" && export DBT_PROFILES_DIR=. && $DBT seed --target-path "$t/t" >/dev/null 2>&1) || { echo "FAIL: dbt seed ($1)"; return 1; }
  (cd "$t" && DBT_PROFILES_DIR=. $DBT show --limit 100 --target-path "$t/t" --inline "$sql order by q" 2>&1) | plain \
    | grep -E '^\| *Q[0-9]' | tr -d '|' | awk '{print $1, $2}' > "$W/$1.got"
  [ "$(wc -l < "$W/$1.got" | tr -d ' ')" = "$n" ] || { echo "FAIL: expected $n answers, got $(wc -l < "$W/$1.got")"; return 1; }
  python3 -I -c '
import csv, math, sys
pack = {r["question_id"]: r for r in csv.DictReader(open(sys.argv[1]))}
bad = 0
for line in open(sys.argv[2]):
    q, v = line.split()
    exp, tol = pack[q]["expected_answer"], float(pack[q]["tolerance"] or 0)
    if exp == "UNDEFINED":
        ok = v in ("NULL", "nan", "inf", "-inf")
    else:
        ok = v not in ("NULL", "nan", "inf", "-inf") and abs(float(v) - float(exp)) <= tol + 1e-9
    print("%s %s expected %s got %s" % ("ok  " if ok else "MOVED", q, exp, v)); bad += not ok
sys.exit(1 if bad else 0)' "$t/seeds/question_pack.csv" "$W/$1.got"; }

fail=0
echo "-- current definition"
gate clean || { echo "FAIL: the current semantic view changes a frozen answer"; fail=1; }
echo "-- planted regression: conversion_rate = bookings / active_users"
if gate mutated; then echo "FAIL: gate stayed GREEN on a redefined conversion denominator"; fail=1; else echo "planted regression -> RED (as required)"; fi
[ "$fail" = 0 ] || exit 1
echo "PASS: every semantic-view question matches its frozen answer; redefining the conversion denominator goes RED"
