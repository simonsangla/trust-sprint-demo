#!/usr/bin/env bash
# Pre-merge gate: a semantic view edit must not change a known answer. Every question of seeds/question_pack.csv
# whose metric the MAIN branch's snowflake/semantic_view.sql defines (the pinned scope) is recomputed from the
# checked view's OWN metric expressions (parsed by svsql.py) over the frozen seeds on DuckDB, and compared with
# the owner's frozen expected_answer (within its tolerance; UNDEFINED must stay NULL). A question of the pinned
# scope that the checked view no longer resolves (metric renamed or removed) is a FAIL, as is a resolved
# question outside it. Two planted edits must then go RED on exactly the answers they break:
#   A: conversion_rate divided by active users instead of sessions -> MOVED = Q04 Q05, nothing else
#   B: conversion_rate coalesced to 0 when there are no sessions   -> MOVED = Q06, nothing else
# An infrastructure failure (dbt seed/show, svsql error) is a FAIL, never a "RED as required".
# No Snowflake call, no spend. REF=<rev> checks another commit than HEAD; BASE=<rev> sets the scope baseline
# (default origin/main, fetched shallow when absent).
# Final line: NUMBERS: in_scope=<n> clean_ok=<n> mutA_moved=<ids> mutB_moved=<ids>
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; HERE="$(cd "$(dirname "$0")" && pwd)"; DBT="${DBT:-dbt}"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
plain(){ sed 's/\x1b\[[0-9;]*m//g'; }
VIEW=snowflake/semantic_view.sql

BASE="${BASE:-origin/main}"
if ! git -C "$ROOT" rev-parse -q --verify "$BASE^{commit}" >/dev/null; then
  git -C "$ROOT" fetch -q --depth=1 origin main 2>/dev/null && BASE=FETCH_HEAD \
    || { echo "FAIL: scope baseline $BASE not found and origin main could not be fetched"; exit 1; }
fi
git -C "$ROOT" show "$BASE:$VIEW" > "$W/base_view.sql" || { echo "FAIL: cannot read $VIEW at $BASE"; exit 1; }

for d in clean mutA mutB; do mkdir -p "$W/$d"; git -C "$ROOT" archive "${REF:-HEAD}" | tar -x -C "$W/$d"; done
SCOPE=$(python3 -I "$HERE/svsql.py" --scope "$W/base_view.sql" "$W/clean/seeds/question_pack.csv") \
  || { echo "FAIL: scope from $BASE: $SCOPE"; exit 1; }
NSCOPE=$(echo $SCOPE | wc -w | tr -d ' ')
[ "$NSCOPE" -gt 0 ] || { echo "FAIL: no question maps to a metric of the $BASE view"; exit 1; }
echo "pinned scope (from the $BASE view): $SCOPE"

plant(){ # $1 tree, $2 sed expression; fail if the edit changed nothing
  sed -i.bak "$2" "$W/$1/$VIEW"; rm -f "$W/$1/$VIEW.bak"
  cmp -s "$W/clean/$VIEW" "$W/$1/$VIEW" && { echo "FAIL: mutation $1 changed nothing"; exit 1; }
}
plant mutA 's|conversion_rate AS bookings.bookings / sessions.session_count|conversion_rate AS bookings.bookings / sessions.active_users|'
plant mutB 's|conversion_rate AS bookings.bookings / sessions.session_count|conversion_rate AS COALESCE(bookings.bookings / NULLIF(sessions.session_count, 0), 0)|'

gate(){ # $1 tree -> one line per question; MOVED ids in $W/$1.moved. exit 0 all ok, 1 answers moved, 2 infra/scope
  local t="$W/$1" ids sql="" q s rc insc n=0
  : > "$W/$1.moved"
  ids=$(python3 -I -c 'import csv,sys; print(" ".join(r["question_id"] for r in csv.DictReader(open(sys.argv[1]))))' "$t/seeds/question_pack.csv")
  for q in $ids; do
    s=$(python3 -I "$HERE/svsql.py" "$t" "$q"); rc=$?
    case " $SCOPE " in *" $q "*) insc=1 ;; *) insc=0 ;; esac
    if [ "$rc" = 3 ]; then
      [ "$insc" = 1 ] && { echo "FAIL: $q is in the pinned scope but its metric is gone from the view (renamed or removed)"; return 2; }
      continue
    fi
    [ "$rc" = 0 ] || { echo "FAIL: svsql.py $q exited $rc: $s"; return 2; }
    [ "$insc" = 1 ] || { echo "FAIL: $q resolves but is outside the pinned scope; land the metric on main first"; return 2; }
    n=$((n+1)); sql="$sql${sql:+ union all }select '$q' as q, coalesce(($s), 'NULL') as v"
  done
  [ "$n" = "$NSCOPE" ] || { echo "FAIL: resolved $n questions, pinned scope has $NSCOPE"; return 2; }
  (cd "$t" && export DBT_PROFILES_DIR=. && $DBT seed --target-path "$t/t" >/dev/null 2>&1) || { echo "FAIL: dbt seed ($1)"; return 2; }
  (cd "$t" && DBT_PROFILES_DIR=. $DBT show --limit 100 --target-path "$t/t" --inline "$sql order by q" 2>&1) | plain \
    | grep -E '^\| *Q[0-9]' | tr -d '|' | awk '{print $1, $2}' > "$W/$1.got"
  [ "$(wc -l < "$W/$1.got" | tr -d ' ')" = "$n" ] || { echo "FAIL: dbt show ($1): expected $n answers, got $(wc -l < "$W/$1.got" | tr -d ' ')"; return 2; }
  python3 -I -c '
import csv, sys
pack = {r["question_id"]: r for r in csv.DictReader(open(sys.argv[1]))}
moved = []
for line in open(sys.argv[2]):
    q, v = line.split()
    exp, tol = pack[q]["expected_answer"], float(pack[q]["tolerance"] or 0)
    if exp == "UNDEFINED":
        ok = v in ("NULL", "nan", "inf", "-inf")
    else:
        ok = v not in ("NULL", "nan", "inf", "-inf") and abs(float(v) - float(exp)) <= tol + 1e-9
    print("%s %s expected %s got %s" % ("ok  " if ok else "MOVED", q, exp, v))
    if not ok: moved.append(q)
open(sys.argv[3], "w").write(" ".join(moved))
sys.exit(1 if moved else 0)' "$t/seeds/question_pack.csv" "$W/$1.got" "$W/$1.moved" || return 1
}

fail=0
echo "-- current definition"
gate clean; rc=$?
clean_ok=0
if [ "$rc" = 0 ]; then clean_ok=$(wc -l < "$W/clean.got" | tr -d ' ')
else echo "FAIL: the current semantic view does not pass the gate (exit $rc)"; fail=1; fi

expect_red(){ # $1 tree, $2 label, $3 exact MOVED ids required
  echo "-- planted regression $1: $2"
  gate "$1"; local rc=$? got; got=$(cat "$W/$1.moved")
  if [ "$rc" = 1 ] && [ "$got" = "$3" ]; then echo "planted regression $1 -> RED on exactly $got (as required)"
  elif [ "$rc" = 1 ]; then echo "FAIL: $1 moved [$got], required exactly [$3]"; fail=1
  elif [ "$rc" = 0 ]; then echo "FAIL: gate stayed GREEN on $1"; fail=1
  else echo "FAIL: $1 hit an infrastructure/scope error (exit $rc), not a RED verdict"; fail=1; fi
}
expect_red mutA "conversion_rate = bookings / active_users" "Q04 Q05"
expect_red mutB "conversion_rate = 0 when there are no sessions" "Q06"
[ "$fail" = 0 ] || exit 1
echo "PASS: every pinned-scope question matches its frozen answer; each planted edit goes RED on exactly the answers it breaks"
echo "NUMBERS: in_scope=$NSCOPE clean_ok=$clean_ok mutA_moved=$(tr ' ' , < "$W/mutA.moved") mutB_moved=$(tr ' ' , < "$W/mutB.moved")"
