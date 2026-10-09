#!/usr/bin/env bash
# pre-pr: the ONE definition of "green" for this repo. CI (.github/workflows/dbt.yml)
# calls this exact script, so a local pass and a CI pass cannot drift apart.
#
#   bash scripts/pre-pr.sh            all steps (what CI runs)
#   bash scripts/pre-pr.sh --links    also check the external links in site/index.html
#
# Needs: uv (uvx), python3, git. Run from anywhere; it cd's to the repo root.
# Note: step 3 regenerates site/index.html in place (the README-prescribed
# regeneration); commit the regenerated file if you changed models or proofs.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

links=0
for a in "$@"; do
  case "$a" in
    --links) links=1 ;;
    *) echo "usage: scripts/pre-pr.sh [--links]" >&2; exit 2 ;;
  esac
done

export DBT_PROFILES_DIR=.
export DBT="uvx --with dbt-duckdb --from dbt-core dbt"

step() { printf '\n== %s\n' "$1"; }
run() { "$@" || { echo "pre-pr FAIL: $*" >&2; exit 1; }; }

step "0/5 pre-commit (lint, yaml, whitespace, secrets, dbt parse)"
run uvx pre-commit run --all-files

step "1/5 dbt build (DuckDB)"
run $DBT build

step "2/5 proofs (claims re-tested against this demo)"
run bash proofs/run_all.sh

step "3/5 docs site: regenerate and sanitize"
run $DBT docs generate --static
run python3 scripts/sanitize_docs.py

step "4/5 docs site carries every proof (regenerated, then committed site/)"
run python3 scripts/check_site_proofs.py site/index.html
run python3 scripts/check_site_proofs.py

if [ "$links" = 1 ]; then
  step "5/5 external links in site/index.html (optional, needs network)"
  run bash scripts/check_links.sh site/index.html
else
  step "5/5 external links: skipped (pass --links to run)"
fi

printf '\npre-pr: ALL GREEN\n'
