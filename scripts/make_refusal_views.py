#!/usr/bin/env python3
"""Create the refusal-regression variants of TRUST_DEMO_SV (DEV schema only, CREATE OR REPLACE).

Each variant = the base view definition + AI_VERIFIED_QUERIES for a subset of the question pack:
  TRUST_DEMO_SV_CTRL     Q01-Q03 (plain governed-metric queries)
  TRUST_DEMO_SV_RULE     all verified queries + an explicit "never invent a metric" instruction
  TRUST_DEMO_SV_NOQ09    all verified queries except Q09
  TRUST_DEMO_SV_ONLYQ09  only Q09 (paying customers, hand-written SQL on USERS)
TRUST_DEMO_SV_EVAL (all verified queries) is built by run_native_eval.py.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf import connect, run, semantic_view_sql  # noqa: E402
import run_native_eval as ne  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LOC, SCHEMA = ne.LOC, ne.SCHEMA
RULE = ("\n  AI_SQL_GENERATION 'Never invent a metric definition. Use only the governed metrics in this view.'"
        "\n  AI_QUESTION_CATEGORIZATION 'If a question asks for a metric that is not defined in this view, such as churn,"
        " do not infer or approximate it. Ask the user for the definition instead of writing SQL.'")


def build(name: str, ids: list[str], pack: dict, rules: str = "") -> str:
    vqs = ",\n    ".join(
        f"{n} AS (QUESTION '{pack[q]['question']}' VERIFIED_BY '(owner = {pack[q]['owner']})' "
        f"SQL '{s.replace(ne.SV, LOC + '.TRUST_DEMO_SV')}')"
        for q, (n, _, s) in ne.EXPECTED.items() if q in ids)
    d = semantic_view_sql(SCHEMA).rstrip().rstrip(";").replace(f"{LOC}.TRUST_DEMO_SV\n", f"{LOC}.{name}\n", 1)
    return d + rules + f"\n  AI_VERIFIED_QUERIES (\n    {vqs}\n  );"


def main() -> int:
    pack = {r["question_id"]: r for r in csv.DictReader((ROOT / "seeds" / "question_pack.csv").open())}
    allq = list(ne.EXPECTED)
    variants = {
        "TRUST_DEMO_SV_CTRL": (["Q01", "Q02", "Q03"], ""),
        "TRUST_DEMO_SV_RULE": (allq, RULE),
        "TRUST_DEMO_SV_NOQ09": ([q for q in allq if q != "Q09"], ""),
        "TRUST_DEMO_SV_ONLYQ09": (["Q09"], ""),
    }
    conn = connect()
    cur = conn.cursor()
    for s in ("USE WAREHOUSE MISSION_OS_WH", "USE DATABASE MISSION_OS_DB", f"USE SCHEMA {SCHEMA}"):
        run(cur, s)
    for name, (ids, rules) in variants.items():
        run(cur, build(name, ids, pack, rules))
        print(name, "ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
