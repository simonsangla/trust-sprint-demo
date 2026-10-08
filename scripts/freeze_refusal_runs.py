#!/usr/bin/env python3
"""Freeze the refusal-regression runs into seeds/refusal_runs.csv.

Input: one CSV per Cortex Analyst semantic view, written by the run script (columns q, run, http, kind, value,
text, request_id). Output: one row per Cortex message with a normalised outcome. No Snowflake call, no spend.
Refuses to overwrite an existing seed (--force to rebuild).

Usage: python scripts/freeze_refusal_runs.py <runs_dir>
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "seeds" / "refusal_runs.csv"
COLS = ["view_key", "question_id", "run", "outcome", "shown", "request_id"]
VIEWS = {  # file stem -> view key
    "n10_base": "base", "n10_eval": "eval", "n10_rule": "rule",
    "n10_noq09": "noq09", "n10_onlyq09": "onlyq09", "CTRL_n5": "ctrl",
}
NUM = re.compile(r"-?\d+(?:\.\d+)?")


def shown(kind: str, value: str) -> str:
    if kind != "sql":
        return ""
    if value.startswith("EMPTY") or value.startswith("(None"):
        return "empty"
    if "cannot be" in value:
        return "text"
    nums = NUM.findall(value)
    return nums[-1] if nums else value[:20]


def outcome(q: str, kind: str, value: str) -> str:
    if kind == "suggestions":
        return "asked"
    if shown(kind, value) == "empty":
        return "empty"
    if shown(kind, value) == "text":
        return "refused_in_sql"
    return "answered"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    if OUT.exists() and "--force" not in sys.argv:
        print(f"{OUT.name} already exists: frozen (--force to rebuild)")
        return 1
    src = Path(sys.argv[1])
    rows = []
    for stem, key in VIEWS.items():
        with (src / f"{stem}.csv").open(newline="") as fh:
            for r in csv.DictReader(fh):
                rows.append({"view_key": key, "question_id": r["q"], "run": r["run"],
                             "outcome": outcome(r["q"], r["kind"], r["value"]),
                             "shown": shown(r["kind"], r["value"]), "request_id": r["request_id"]})
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT} {len(rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
