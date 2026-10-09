#!/usr/bin/env bash
# Fail when a link WE OWN (simonsangla.com hosts, cal.com, github.com/simonsangla) in the HTML does not answer 2xx/3xx.
# Third-party links bundled by dbt docs (angular, jquery, issue trackers) are out of scope: they rot without our change.
# Usage: bash scripts/check_links.sh [HTML]   (default site/index.html). Needs network.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
html="${1:-site/index.html}"
[ -f "$html" ] || { echo "check_links FAIL: no such file: $html" >&2; exit 1; }
bad=0
urls=$(grep -oE 'https?://[A-Za-z0-9._~:/?#@!$&*+,;=%-]+' "$html" | sed 's/[.,;)]*$//' | sort -u | grep -E '^https?://([a-z0-9-]+\.)*simonsangla\.com|^https://cal\.com/|^https://github\.com/simonsangla/') || true
[ -n "$urls" ] || { echo "check_links FAIL: no owned links found in $html (selector matched nothing)" >&2; exit 1; }
for u in $urls; do
  code=$(curl -sS -o /dev/null -L --max-time 15 -w '%{http_code}' "$u" 2>/dev/null || true)
  case "$code" in
    2??|3??) echo "ok   $code $u" ;;
    *) echo "FAIL $code $u"; bad=1 ;;
  esac
done
[ "$bad" = 0 ] || { echo "check_links FAIL: broken external link" >&2; exit 1; }
echo "check_links: all external links answer"
