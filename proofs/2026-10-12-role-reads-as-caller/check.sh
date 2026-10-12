#!/usr/bin/env bash
# Proof: an AI analytics assistant reads data as the role that calls it. The same assistant SQL
# (question.sql.j2) runs twice on the same data, once as ANALYST_FULL and once as ANALYST_RESTRICTED. The only
# thing that protects the email column is the masking policy (policy.sql.j2), evaluated against the caller's
# role; the SQL itself is identical. Then a copy of the tree has the mask removed (the policy returns the raw
# value for every role) and the restricted role must go RED (emails exposed).
# Offline: DuckDB + dbt. Snowflake masking policies are EMULATED with a CASE on a dbt var standing in for
# CURRENT_ROLE(). Nothing here calls Snowflake or Cortex. REF=<rev> checks another commit than HEAD.
# Final line: NUMBERS: <exposed emails as ANALYST_FULL> <exposed emails as ANALYST_RESTRICTED>
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; DBT="${DBT:-dbt}"
D=proofs/2026-10-12-role-reads-as-caller
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
plain(){ sed 's/\x1b\[[0-9;]*m//g'; }
for d in clean mutated; do mkdir -p "$W/$d"; git -C "$ROOT" archive "${REF:-HEAD}" | tar -x -C "$W/$d"; done
[ -f "$W/clean/$D/policy.sql.j2" ] || { echo "FAIL: $D/policy.sql.j2 not in the archived tree"; exit 1; }
# the mutation: the policy no longer masks anything
printf '%s\n' "VAL" > "$W/mutated/$D/policy.sql.j2"
cmp -s "$W/clean/$D/policy.sql.j2" "$W/mutated/$D/policy.sql.j2" && { echo "FAIL: mutation changed nothing"; exit 1; }

prep(){ (cd "$W/$1" && DBT_PROFILES_DIR=. $DBT seed --target-path "$W/$1/t" --select users >/dev/null 2>&1); }
# compose the assistant query: the policy body (comments dropped) applied to the email column
query(){ # $1 tree
  pol=$(grep -v '^ *--' "$W/$1/$D/policy.sql.j2" | tr '\n' ' ' | sed 's/VAL/email/g')
  grep -v '^ *--' "$W/$1/$D/question.sql.j2" | tr '\n' ' ' | awk -v p="$pol" '{gsub(/MASKED_EMAIL/, p); print}'; }
# one line per run: "<rows> <exposed>"; exposed = a returned email that still contains an @
run(){ # $1 tree $2 role
  q=$(query "$1")
  (cd "$W/$1" && DBT_PROFILES_DIR=. $DBT show --target-path "$W/$1/t" --vars "{role: $2}" \
     --inline "select count(*) as n_rows, count(case when email like '%@%' then 1 end) as exposed from ($q) a" 2>&1 \
   | plain | grep -E '^\| *[0-9]' | tr -d '|' | awk '{print $1, $2}' | head -1); }
sample(){ # $1 tree $2 role : first 3 rows the assistant would show
  q=$(query "$1")
  (cd "$W/$1" && DBT_PROFILES_DIR=. $DBT show --target-path "$W/$1/t" --limit 3 --vars "{role: $2}" --inline "$q" 2>&1 \
   | plain | grep -E '^\| *U[0-9]' | sed 's/^/    /'); }

prep clean || { echo "FAIL: clean tree did not build"; exit 1; }
prep mutated || { echo "FAIL: mutated tree did not build"; exit 1; }
fail=0
read -r ra ea <<EOF2
$(run clean ANALYST_FULL)
EOF2
read -r rb eb <<EOF2
$(run clean ANALYST_RESTRICTED)
EOF2
read -r rm em <<EOF2
$(run mutated ANALYST_RESTRICTED)
EOF2
echo "same assistant SQL, role ANALYST_FULL: ${ra:-?} rows, ${ea:-?} emails exposed"; sample clean ANALYST_FULL
echo "same assistant SQL, role ANALYST_RESTRICTED: ${rb:-?} rows, ${eb:-?} emails exposed"; sample clean ANALYST_RESTRICTED
echo "mask removed (mutated copy), role ANALYST_RESTRICTED: ${rm:-?} rows, ${em:-?} emails exposed"
case "${ra:-x}${rb:-x}${ea:-x}${eb:-x}${em:-x}" in *[!0-9]*) echo "FAIL: could not read a count from dbt"; exit 1;; esac
[ "$ra" -gt 0 ] || { echo "FAIL: the question returned no rows; nothing was tested"; fail=1; }
[ "$ra" = "$rb" ] || { echo "FAIL: the two roles saw different row counts"; fail=1; }
[ "$ea" = "$ra" ] || { echo "FAIL: the broad role did not see every email"; fail=1; }
[ "$eb" = 0 ] || { echo "FAIL: the restricted role saw $eb emails"; fail=1; }
if [ "$em" -gt 0 ]; then echo "mutation: mask removed -> restricted role RED ($em emails exposed)"
else echo "FAIL: restricted role stayed green with the mask removed"; fail=1; fi
[ "$fail" = 0 ] || exit 1
echo "PASS: identical assistant SQL returned $ea emails as ANALYST_FULL and $eb as ANALYST_RESTRICTED; only the role-evaluated mask differs, and removing it exposes $em"
echo "NUMBERS: $ea $eb"
