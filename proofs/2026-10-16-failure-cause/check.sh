#!/usr/bin/env bash
# Proof: every non-pass verdict of the frozen Cortex Analyst run (2026-10-08) carries a failure_cause derived
# from the generated SQL and the metric registry, not typed by hand. This script (1) rebuilds REF offline on
# DuckDB, (2) prints the cause per question and the tally per cause, (3) requires the README reading:
# Q04/Q05 filter (both date filters), Q06/Q08/Q09 definition, passes none, (4) requires the accepted_values
# test on failure_cause to pass, and (5) rebuilds a copy where Q04's SQL loses its bookings.booking_date
# filter and requires Q04's cause to stop being 'filter', so the tag cannot be a constant.
# Nothing here calls Snowflake. Exit 0 only if every step holds. REF=<rev> checks another commit than HEAD.
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; DBT="${DBT:-dbt}"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
plain(){ sed 's/\x1b\[[0-9;]*m//g'; }
for d in clean mutated; do mkdir -p "$W/$d"; git -C "$ROOT" archive "${REF:-HEAD}" | tar -x -C "$W/$d"; done
# the mutation: Q04 keeps only its session-date filter
sed -i.bak "/^Q04,/s/ AND bookings\.booking_date >= '2026-06-01' AND bookings\.booking_date < '2026-07-01'//" "$W/mutated/seeds/cortex_answers.csv"
rm -f "$W/mutated/seeds/cortex_answers.csv.bak"
cmp -s "$W/clean/seeds/cortex_answers.csv" "$W/mutated/seeds/cortex_answers.csv" && { echo "FAIL: mutation changed nothing"; exit 1; }

prep(){ (cd "$W/$1" && export DBT_PROFILES_DIR=. && $DBT seed --target-path "$W/$1/t" >/dev/null 2>&1 && $DBT run --target-path "$W/$1/t" >/dev/null 2>&1); }
causes(){ (cd "$W/$1" && DBT_PROFILES_DIR=. $DBT show --target-path "$W/$1/t" --limit 50 --inline "
    select question_id, verdict, failure_cause from {{ ref('fct_question_verdicts') }} order by question_id" 2>&1 \
    | plain | grep -E '^\| *Q[0-9]' | tr -d '|' | awk '{print $1, $2, $3}'); }
fail=0
prep clean || { echo "FAIL: clean tree did not build"; exit 1; }
out=$(causes clean)
printf '%s\n' "$out" | sed 's/^/cause: /'
want="Q01 none
Q02 none
Q03 none
Q04 filter
Q05 filter
Q06 definition
Q07 none
Q08 definition
Q09 definition
Q10 none"
[ "$(printf '%s\n' "$out" | awk '{print $1, $3}')" = "$want" ] || { echo "FAIL: causes differ from the README reading"; fail=1; }
printf '%s\n' "$out" | awk '($2 == "pass") != ($3 == "none") {bad=1} END {exit bad}' || { echo "FAIL: a pass without cause none, or a non-pass with none"; fail=1; }
n(){ printf '%s\n' "$out" | awk -v c="$1" '$3 == c' | wc -l | tr -d ' '; }
total=$(printf '%s\n' "$out" | wc -l | tr -d ' ')
echo "Causes: $total questions, $(n none) none, $(n definition) definition, $(n filter) filter, $(n join) join, $(n model) model"
[ "$total" = 10 ] || { echo "FAIL: expected 10 questions, got $total"; fail=1; }
tout=$( (cd "$W/clean" && DBT_PROFILES_DIR=. $DBT test --target-path "$W/clean/t" --select fct_question_verdicts fct_failure_cause_summary 2>&1 | plain) )
printf '%s\n' "$tout" | grep -qE 'ERROR=0 ' && printf '%s\n' "$tout" | grep -qE 'PASS=[1-9]' \
  || { echo "FAIL: failure_cause tests did not pass"; printf '%s\n' "$tout" | tail -n 5; fail=1; }
echo "failure_cause tests: $(printf '%s\n' "$tout" | grep -oE 'PASS=[0-9]+' | tail -1)"
prep mutated || { echo "FAIL: mutated tree did not build"; exit 1; }
m4=$(causes mutated | awk '$1 == "Q04" {print $3}')
echo "mutation: Q04 SQL without the bookings.booking_date filter -> cause $m4"
[ -n "$m4" ] && [ "$m4" != filter ] || { echo "FAIL: Q04 stayed 'filter' after its booking-date filter was removed"; fail=1; }
[ "$fail" = 0 ] || exit 1
echo "PASS: 5 non-pass verdicts tagged from the SQL (2 filter, 3 definition), passes tagged none; the tag follows the SQL"
