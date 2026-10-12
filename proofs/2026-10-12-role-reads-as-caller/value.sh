#!/usr/bin/env bash
# Read-only value check: each cited number (args) must be a line of the stored check.sh output ($PROOF_OUT).
# Written without numeric literals, because the gate rejects a value.sh that contains a cited number.
set -uo pipefail
[ -n "${PROOF_OUT:-}" ] && [ -f "$PROOF_OUT" ] || { echo "FAIL: PROOF_OUT missing"; exit 1; }
[ "$#" -ge 1 ] || { echo "FAIL: no numbers given"; exit 1; }
ok=yes
for n in "$@"; do
  line=$(grep -wF -- "$n" "$PROOF_OUT" | grep -v '^\$' | head -n 1)
  if [ -n "$line" ]; then echo "$n: $line"; else echo "FAIL: $n not in proof output"; ok=no; fi
done
[ "$ok" = yes ]
