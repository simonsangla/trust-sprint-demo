#!/usr/bin/env bash
# Fail when a third-party `uses:` in .github/workflows is not pinned to a 40-hex commit SHA.
# Local actions (./path) and docker:// are exempt. Usage: bash scripts/check_actions_pinned.sh [DIR]
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
dir="${1:-.github/workflows}"
files=$(ls "$dir"/*.yml "$dir"/*.yaml 2>/dev/null) || true
[ -n "$files" ] || { echo "check_actions_pinned FAIL: no workflow files under $dir" >&2; exit 1; }
bad=0; seen=0
for f in $files; do
  while IFS= read -r line; do
    seen=$((seen + 1))
    ref=$(printf '%s' "$line" | sed -E 's/^[[:space:]]*-?[[:space:]]*uses:[[:space:]]*//; s/[[:space:]]*#.*$//')
    case "$ref" in ./*|docker://*) continue ;; esac
    if ! printf '%s' "$ref" | grep -qE '^[A-Za-z0-9._-]+/[A-Za-z0-9._/-]+@[0-9a-f]{40}$'; then
      echo "FAIL $f: not pinned by SHA: $ref"; bad=1
    fi
  done < <(grep -E '^[[:space:]]*-?[[:space:]]*uses:' "$f")
done
[ "$seen" -gt 0 ] || { echo "check_actions_pinned FAIL: no 'uses:' lines found (selector matched nothing)" >&2; exit 1; }
[ "$bad" = 0 ] || exit 1
echo "check_actions_pinned: $seen action reference(s), all pinned by SHA"
