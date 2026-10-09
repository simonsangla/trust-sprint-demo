"""Post-process `dbt docs generate --static` output into site/index.html.

Usage (from the repo root, after `dbt docs generate --static`):
    python3 scripts/sanitize_docs.py

- replaces the absolute build path (root_path) with a neutral label
- rewrites the <head> share tags (og/twitter), favicon and title
- re-injects the "Built by" pill before </body>
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "target", "static_index.html")
DST = os.path.join(ROOT, "site", "index.html")
NEUTRAL = "trust-sprint-demo"
SITE = "https://trustsprint.simonsangla.com"
TITLE = "Cortex Analyst said 85%. The right answer was 8%."
DESC = "Fictional data, real Cortex Analyst run, 8 Oct 2026: 10 business questions checked against expected answers. 5 pass, 3 warning, 2 fail."
FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect width='32' height='32' rx='6' fill='%231C2321'/%3E"
    "%3Crect x='6' y='14' width='5' height='12' fill='%23F7F8F4'/%3E"
    "%3Crect x='13' y='8' width='5' height='6' fill='%231F7A64'/%3E"
    "%3Crect x='20' y='12' width='5' height='14' fill='%23A44F1B'/%3E%3C/svg%3E"
)
# Return strip (mission-os#1283, #1394): every demo links back and to the attributed
# Cal booking page, so demo traffic can reach a booking and be counted.
PILL = (
    '<div id="built-by-simon" style="position:fixed;left:12px;bottom:12px;z-index:2147483647;'
    "display:flex;align-items:center;gap:10px;background:#101c2b;color:#fff;"
    "font:13px/1.2 'IBM Plex Sans',system-ui,sans-serif;padding:6px 6px 6px 12px;border-radius:6px;"
    'box-shadow:0 2px 8px rgba(0,0,0,.3)">'
    '<a href="https://simonsangla.com/?ref=trust-demo" target="_blank" rel="noopener" '
    'style="color:#fff;text-decoration:none">Built by Simon Sangla</a>'
    '<a href="https://cal.com/simon-sangla/trust-sprint-scoping-call?ref=demo" target="_blank" rel="noopener" '
    'style="background:#fff;color:#101c2b;padding:6px 10px;border-radius:4px;text-decoration:none;font-weight:500">'
    "Book the scoping call &#8599;</a></div>"
)

# 0. ledger theme (mission-os#1282): simonsangla.com tokens + IBM Plex, from scripts/site_theme.css
THEME = (
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500'
    '&family=IBM+Plex+Sans:wght@400;500&display=swap">'
    "<style>" + open(os.path.join(ROOT, "scripts", "site_theme.css"), encoding="utf-8").read() + "</style>"
)

html = open(SRC, encoding="utf-8").read()

# 1. neutral path: the real root, its realpath, and macOS /private variants
paths = {ROOT, os.path.realpath(ROOT), os.getcwd(), os.path.realpath(os.getcwd())}
for p in sorted(paths, key=len, reverse=True):
    for variant in {p, p.replace("/private", "", 1) if p.startswith("/private/") else p}:
        html = html.replace(variant, NEUTRAL)
    html = html.replace(p.replace("/", "\\/"), NEUTRAL)

# 2. head tags
def sub(pattern, repl):
    global html
    new, n = re.subn(pattern, lambda m: repl, html, count=1)
    if n != 1:
        sys.exit("sanitize_docs: head pattern not found: " + pattern)
    html = new

sub(r"<title>[^<]*</title>", f"<title>{TITLE}</title>{THEME}")
sub(r'<meta name="description" content="[^"]*"/>', f'<meta name="description" content="{DESC}"/>')
sub(r'<link rel="shortcut icon" href="[^"]*"/>', f'<link rel="icon" href="{FAVICON}"/>')
sub(r'<meta property="og:title" content="[^"]*"/>', f'<meta property="og:title" content="{TITLE}"/>')
sub(r'<meta property="og:description" content="[^"]*"/>',
    f'<meta property="og:description" content="{DESC}"/>'
    f'<meta property="og:url" content="{SITE}"/>'
    f'<meta property="og:image" content="{SITE}/og.png"/>'
    '<meta property="og:image:width" content="1200"/><meta property="og:image:height" content="627"/>')
# LinkedIn Post Inspector warnings "No author found" / "Publish date not found" (#1236): author meta + article date
AUTHOR_META = '<meta name="author" content="Simon Sangla"/><meta property="article:published_time" content="2026-10-09"/>'
sub(r'<meta property="og:site_name" content="[^"]*"/>', f'<meta property="og:site_name" content="Simon Sangla"/>{AUTHOR_META}')
sub(r'<meta name="twitter:title" content="[^"]*"/>',
    '<meta name="twitter:card" content="summary_large_image"/>'
    f'<meta name="twitter:title" content="{TITLE}"/>')
sub(r'<meta name="twitter:description" content="[^"]*"/>',
    f'<meta name="twitter:description" content="{DESC}"/>'
    f'<meta name="twitter:image" content="{SITE}/og.png"/>')

# 3. pill
html = re.sub(r'<div id="built-by-simon".*?</div>|<a id="built-by-simon".*?</a>', "", html, flags=re.S)
if "</body>" not in html:
    sys.exit("sanitize_docs: </body> not found")
html = html.replace("</body>", PILL + "</body>", 1)

# 4. guard
for bad in ("/private/", "/Users/", "/tmp/"):
    if bad in html:
        i = html.index(bad)
        sys.exit(f"sanitize_docs: leaked path {bad!r}: ...{html[max(0,i-60):i+80]!r}")

open(DST, "w", encoding="utf-8").write(html)
print("wrote", DST, len(html), "bytes")
