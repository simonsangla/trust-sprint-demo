"""Fail when a proof id in models/proofs/_proofs.yml, or a Cortex request id in
seeds/cortex_answers.csv, is missing from site/index.html.

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


def committed_site():
    out = subprocess.run(["git", "-C", ROOT, "show", "HEAD:site/index.html"],
                         capture_output=True, text=True, check=True)
    return "committed site/index.html", out.stdout


def main(paths):
    ids = proof_ids() + request_ids()
    sources = [(p, open(p, encoding="utf-8").read()) for p in paths] or [committed_site()]
    bad = 0
    for label, html in sources:
        missing = [i for i in ids if i not in html]
        for i in missing:
            print(f"FAIL: {label} lacks id {i}; regenerate site/ (see README)")
        bad += len(missing)
        if not missing:
            print(f"OK: {label} carries all {len(ids)} ids (proofs + request ids)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
