#!/usr/bin/env bash
# Run every proofs/*/check.sh. Exit 1 if any proof no longer holds (a dbt upgrade can change a past result),
# or if there is no proof at all (an empty glob must not read as success).
set -uo pipefail
cd "$(dirname "$0")"; fail=0; n=0
for c in */check.sh; do
  [ -f "$c" ] || { echo "FAIL: no proofs/*/check.sh found"; exit 1; }
  n=$((n+1)); echo "== ${c%/check.sh}"; bash "$c" || fail=1
done
[ "$n" -gt 0 ] || { echo "FAIL: no proofs found"; exit 1; }
exit "$fail"
