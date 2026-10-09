#!/usr/bin/env bash
# Proof: a governed Snowflake semantic view can still return a wrong number. The frozen Cortex Analyst run
# (2026-10-08) answered Q04 0.852632 and Q05 0.907692; the data owner's numbers are 0.0809 and 0.0879.
# This script (1) rebuilds HEAD offline on DuckDB, (2) re-derives both ratios from the sessions and bookings
# seeds with its own SQL, once with the session-date filter alone and once with BOTH the session-date and
# booking-date filters the analyst generated, (3) runs the pinned dbt test, and (4) runs that test again on a
# copy where the owner's Q04 number is corrupted (0.0809 -> 0.8526) and requires it to go RED.
# (5) recomputes the pass / warning / fail tally with dbt and requires it to equal the table on the page.
# Nothing here calls Snowflake: the live run is frozen in seeds/cortex_answers.csv, the owner values in
# seeds/question_pack.csv. Exit 0 only if every step holds. REF=<rev> checks another commit than HEAD.
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; DBT="${DBT:-dbt}"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
plain(){ sed 's/\x1b\[[0-9;]*m//g'; }
T=assert_conversion_double_filter_mechanism
for d in clean mutated; do mkdir -p "$W/$d"; git -C "$ROOT" archive "${REF:-HEAD}" | tar -x -C "$W/$d"; done
# the mutation: the owner's Q04 number replaced by the analyst's wrong one
sed -i.bak 's/^\(Q04,.*,conversion_rate,[^,]*,[^,]*,[^,]*,\)0\.0809,/\10.8526,/' "$W/mutated/seeds/question_pack.csv"
rm -f "$W/mutated/seeds/question_pack.csv.bak"
grep -q '^Q04,.*,0\.8526,' "$W/mutated/seeds/question_pack.csv" || { echo "FAIL: mutation not applied"; exit 1; }
cmp -s "$W/clean/seeds/question_pack.csv" "$W/mutated/seeds/question_pack.csv" && { echo "FAIL: mutation changed nothing"; exit 1; }

prep(){ (cd "$W/$1" && export DBT_PROFILES_DIR=. && $DBT seed --target-path "$W/$1/t" >/dev/null 2>&1 && $DBT run --target-path "$W/$1/t" >/dev/null 2>&1); }
pinned(){ (cd "$W/$1" && DBT_PROFILES_DIR=. $DBT test --target-path "$W/$1/t" --select "$T" 2>&1 | plain); }
# one row: "<session-date filter only> <both date filters>", straight from the seeds, confirmed bookings only
ratios(){ # $1 date_from $2 date_to $3 channel clause ('' or "and s.channel = 'organic'")
  (cd "$W/clean" && DBT_PROFILES_DIR=. $DBT show --target-path "$W/clean/t" --inline "
    with j as (select s.session_id, b.booking_id, b.status, b.booking_date
               from {{ ref('sessions') }} s left join {{ ref('bookings') }} b on b.session_id = s.session_id
               where s.session_date between date '$1' and date '$2' $3)
    select cast(round(count(case when status = 'confirmed' then booking_id end) * 1.0 / count(distinct session_id), 6) as varchar) as session_only,
           cast(round(count(case when status = 'confirmed' and booking_date between date '$1' and date '$2' then booking_id end) * 1.0
                      / count(distinct case when booking_date between date '$1' and date '$2' then session_id end), 6) as varchar) as both_filters from j" 2>&1 \
    | plain | grep -E '^\| *[0-9]' | tr -d '|' | awk '{print $1, $2}' | head -1); }
# expected values come from the seeds, not from this script
seedval(){ python3 -I -c '
import csv, sys
f, q, col = sys.argv[1:4]
print([r for r in csv.DictReader(open(f)) if r["question_id"] == q][0][col])' "$@"; }
QP="$W/clean/seeds/question_pack.csv"; CA="$W/clean/seeds/cortex_answers.csv"
near(){ awk -v a="$1" -v b="$2" -v t="$3" 'BEGIN{d=a-b; if(d<0)d=-d; exit !(a!="" && b!="" && d<=t)}'; }

prep clean || { echo "FAIL: clean tree did not build"; exit 1; }
fail=0
chk(){ # $1 question $2 date_from $3 date_to $4 channel clause
  read -r so bf <<EOF2
$(ratios "$2" "$3" "$4")
EOF2
  exp=$(seedval "$QP" "$1" expected_answer); got=$(seedval "$CA" "$1" answer_value); rid=$(seedval "$CA" "$1" request_id)
  echo "$1 owner $exp | session filter only $so | both filters $bf | analyst shown $got | request $rid"
  pct(){ awk -v x="$1" 'BEGIN{printf "%.2f%%", x*100}'; }
  echo "$1 as percentages: owner $(pct "$exp") | session filter only $(pct "$so") | both filters $(pct "$bf") | analyst shown $(pct "$got")"
  near "$so" "$exp" 0.0005 || { echo "FAIL: $1 session-filter-only ratio is not the owner's number"; fail=1; }
  near "$bf" "$got" 0.000001 || { echo "FAIL: $1 both-filters ratio is not what the analyst returned"; fail=1; }
  near "$so" "$got" 0.1 && { echo "FAIL: $1 analyst number is close to the right one; the claim does not hold"; fail=1; }
}
chk Q04 2026-06-01 2026-06-30 ""
chk Q05 2026-01-01 2026-06-30 "and s.channel = 'organic'"

out=$(pinned clean)
printf '%s\n' "$out" | grep -q 'PASS=1 ' || { echo "FAIL: pinned test $T did not pass on the clean tree"; printf '%s\n' "$out" | tail -n 5; fail=1; }
prep mutated || { echo "FAIL: mutated tree did not build"; exit 1; }
mout=$(pinned mutated)
printf '%s\n' "$mout" | grep -q "FAIL 1 $T" || { echo "FAIL: pinned test stayed green with the owner's Q04 number corrupted"; fail=1; }
echo "pinned test: clean PASS; owner's Q04 corrupted to 0.8526 -> $(printf '%s\n' "$mout" | grep -q "FAIL 1 $T" && echo RED || echo STILL GREEN)"
# the page's own verdict tally (models/overview.md: "| Pass | 5 |" ...) must equal the tally dbt computes from the seeds
vcount(){ (cd "$W/clean" && DBT_PROFILES_DIR=. $DBT show --target-path "$W/clean/t" --inline "
    select count(*) from {{ ref('fct_question_verdicts') }} where verdict = '$1'" 2>&1 | plain | grep -E '^\| *[0-9]' | tr -d '| ' | head -1); }
ptally(){ awk -F'|' -v k="$1" '$2 ~ "^ *" k " *$" {gsub(/ /,"",$3); print $3; exit}' "$W/clean/models/overview.md"; }
tp=$(vcount pass); tw=$(vcount trust_warning); tf=$(vcount fail); pp=$(ptally Pass); pw=$(ptally Warning); pf=$(ptally Fail)
total=$(( ${tp:-0} + ${tw:-0} + ${tf:-0} ))
echo "Verdicts: $total questions, $tp pass, $tw warning, $tf fail (page table: $pp pass, $pw warning, $pf fail)"
[ "$total" = 10 ] || { echo "FAIL: expected 10 verdicts, dbt built $total"; fail=1; }
{ [ -n "$tp" ] && [ "$tp" = "$pp" ] && [ "$tw" = "$pw" ] && [ "$tf" = "$pf" ]; } || { echo "FAIL: verdict tally from the seeds differs from the page table"; fail=1; }
[ "$fail" = 0 ] || exit 1
echo "PASS: Q04 0.0809 vs 0.852632 and Q05 0.0879 vs 0.907692 re-derived from the seeds; the double date filter explains both; the pinned test passes and goes red when the owner's number is wrong"
