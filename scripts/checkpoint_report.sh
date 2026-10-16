#!/usr/bin/env bash
# checkpoint_report: run only the dbt-checkpoint hooks and write their result as
# plain text, so a reviewer (human or a Cortex Agent over a search index) can read
# which hook failed on which model without parsing pre-commit's coloured output.
#
#   bash scripts/checkpoint_report.sh          writes target/checkpoint_report.txt
#   bash scripts/checkpoint_report.sh OUT.txt  writes OUT.txt
#
# Exit code = pre-commit's: 0 every dbt-checkpoint hook passed, non-zero otherwise.
# Needs: uv (uvx), git. Run from anywhere; it cd's to the repo root.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

out="${1:-target/checkpoint_report.txt}"
mkdir -p "$(dirname "$out")"

# The hook ids, read from .pre-commit-config.yaml so this list cannot drift from the gate.
ids="$(awk '/repo: https:\/\/github.com\/dbt-checkpoint\/dbt-checkpoint/{on=1; next}
            /^  - repo:/{on=0}
            on && /- id:/{print $3}' .pre-commit-config.yaml)"
if [ -z "$ids" ]; then
  echo "checkpoint_report FAIL: no dbt-checkpoint hooks found in .pre-commit-config.yaml" >&2
  exit 2
fi

# dbt-checkpoint reads target/manifest.json; write it first.
DBT_PROFILES_DIR=. uvx --with dbt-duckdb --from dbt-core dbt parse --quiet || {
  echo "checkpoint_report FAIL: dbt parse" >&2; exit 1; }

rc=0
{
  echo "dbt-checkpoint report"
  echo "commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
} > "$out"
for id in $ids; do
  log="$(uvx pre-commit run "$id" --all-files --color never 2>&1)"
  hrc=$?
  if [ "$hrc" -eq 0 ]; then
    echo "PASS $id" >> "$out"
  else
    rc=1
    { echo "FAIL $id"; printf '%s\n' "$log" | sed -n '/^- exit code:/,$p' | sed '1d;/^$/d;s/^/  /'; } >> "$out"
  fi
done
echo >> "$out"
if [ "$rc" -eq 0 ]; then echo "RESULT: all dbt-checkpoint hooks passed" >> "$out"
else echo "RESULT: at least one dbt-checkpoint hook failed (see FAIL lines)" >> "$out"; fi

cat "$out"
exit "$rc"
