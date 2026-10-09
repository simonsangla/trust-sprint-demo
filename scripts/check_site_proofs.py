"""Fail when a proof id in models/proofs/_proofs.yml, or a Cortex request id in
seeds/cortex_answers.csv, is missing from site/index.html. Also fails when the page lacks the self-hosted
Snowflake icon (referenced, and present as a real <svg> file next to it) or the non-affiliation line, or still
shows the dbt logo (mission-os#1404).

Usage: python3 scripts/check_site_proofs.py [HTML_PATH ...]
Default HTML_PATH is the committed site/index.html (read via `git show HEAD:`),
so a CI step that regenerates site/ first still judges what is committed.
A byte diff is not used: dbt docs embed generated_at and invocation_id.
"""
import csv
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROOFS = os.path.join(ROOT, "models", "proofs", "_proofs.yml")
ANSWERS = os.path.join(ROOT, "seeds", "cortex_answers.csv")


def proof_ids():
    with open(PROOFS, encoding="utf-8") as f:
        ids = re.findall(r"^  - name: ([A-Za-z0-9_]+)\s*$", f.read(), re.M)
    if not ids:
        sys.exit("FAIL: no proof ids parsed from models/proofs/_proofs.yml")
    return ids


def request_ids():
    """Every Snowflake request id of the frozen run: the site must let a reader find the exact Cortex call."""
    with open(ANSWERS, encoding="utf-8", newline="") as f:
        ids = [r["request_id"] for r in csv.DictReader(f) if r.get("request_id")]
    if len(ids) != 10:
        sys.exit(f"FAIL: expected 10 request ids in seeds/cortex_answers.csv, parsed {len(ids)}")
    return ids


DISCLAIMER = "Independent demo, not affiliated with or endorsed by Snowflake"
LOGO_REF = 'src="snowflake.svg"'


def logo_problems(html, svg):
    """svg is the text of site/snowflake.svg, or None when the file is absent."""
    out = []
    if DISCLAIMER not in html:
        out.append("non-affiliation line missing: " + DISCLAIMER)
    if LOGO_REF not in html:
        out.append("page does not reference the self-hosted Snowflake icon: " + LOGO_REF)
    if "dbt logo" in html:
        out.append("page still shows the dbt logo")
    if svg is None or "<svg" not in svg or "<path" not in svg:
        out.append("site/snowflake.svg is missing or is not an SVG with a path")
    return out


def disk_svg():
    p = os.path.join(ROOT, "site", "snowflake.svg")
    return open(p, encoding="utf-8").read() if os.path.exists(p) else None


def committed_svg():
    out = subprocess.run(["git", "-C", ROOT, "show", "HEAD:site/snowflake.svg"], capture_output=True, text=True)
    return out.stdout if out.returncode == 0 else None


def committed_site():
    out = subprocess.run(["git", "-C", ROOT, "show", "HEAD:site/index.html"],
                         capture_output=True, text=True, check=True)
    return "committed site/index.html", out.stdout


def main(paths):
    ids = proof_ids() + request_ids()
    sources = [(p, open(p, encoding="utf-8").read(), disk_svg()) for p in paths]
    if not sources:
        label, html = committed_site()
        sources = [(label, html, committed_svg())]
    bad = 0
    for label, html, svg in sources:
        for prob in logo_problems(html, svg):
            print(f"FAIL: {label}: {prob}")
            bad += 1
        missing = [i for i in ids if i not in html]
        for i in missing:
            print(f"FAIL: {label} lacks id {i}; regenerate site/ (see README)")
        bad += len(missing)
        if not missing and not logo_problems(html, svg):
            print(f"OK: {label} carries all {len(ids)} ids (proofs + request ids), the Snowflake icon and the non-affiliation line")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
