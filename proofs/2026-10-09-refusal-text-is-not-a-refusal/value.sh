#!/usr/bin/env bash
# Read-only value check for the LinkedIn gates: every number passed as an argument must appear in
# this proof's check.sh output. Nothing is hard-coded; the numbers come from the caller.
# PROOF_OUT = a saved copy of check.sh output (set by the gate); without it, check.sh is run here.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
[ "$#" -gt 0 ] || { echo "usage: value.sh NUMBER..." >&2; exit 2; }
if [ -n "${PROOF_OUT:-}" ] && [ -f "$PROOF_OUT" ]; then out="$(cat "$PROOF_OUT")"; else out="$(bash "$HERE/check.sh" 2>&1)"; fi
fail=0
for n in "$@"; do
  re="$(printf '%s' "$n" | sed 's/[.]/[.]/g')"
  line="$(printf '%s\n' "$out" | grep -E "(^|[^0-9.,])${re}([^0-9]|[.,][^0-9]|$)" | head -1)"
  if [ -n "$line" ]; then echo "FOUND $n in: $line"; else echo "MISSING $n in check.sh output"; fail=1; fi
done
exit "$fail"
