#!/usr/bin/env python3
"""Build the instruction-wording variants of ONLYQ09 (DEV, CREATE OR REPLACE):
  TRUST_DEMO_SV_ONLYQ09_W2       AI_SQL_GENERATION only: do not write SQL, say the metric is not defined
  TRUST_DEMO_SV_ONLYQ09_W3       AI_QUESTION_CATEGORIZATION only: unanswerable, reject
  TRUST_DEMO_SV_ONLYQ09_UNCLEAR  AI_QUESTION_CATEGORIZATION only, documented state keyword UNCLEAR
(ONLYQ09_RULE is built by run_refusal_experiments.py.)"""
from __future__ import annotations
import csv, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf import connect, run  # noqa: E402
import make_refusal_views as mv  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
W = {
    "TRUST_DEMO_SV_ONLYQ09_W2": "\n  AI_SQL_GENERATION 'If the user asks for a metric that is not defined in this semantic view, for example churn, lifetime value or retention, do not write any SQL. Reply that the metric is not defined and ask the user for its definition.'",
    "TRUST_DEMO_SV_ONLYQ09_W3": "\n  AI_QUESTION_CATEGORIZATION 'Questions about metrics that are not defined in this semantic view, for example churn, lifetime value or retention, are unanswerable. Reject them and ask the user to define the metric.'",
    "TRUST_DEMO_SV_ONLYQ09_UNCLEAR": "\n  AI_QUESTION_CATEGORIZATION 'If a question asks for a metric that is not defined in this semantic view, for example churn, lifetime value or retention, consider this question UNCLEAR and ask the user to define the metric.'",
}


def main() -> int:
    pack = {r["question_id"]: r for r in csv.DictReader((ROOT / "seeds" / "question_pack.csv").open())}
    conn = connect(); cur = conn.cursor()
    for s in ("USE WAREHOUSE MISSION_OS_WH", "USE DATABASE MISSION_OS_DB", f"USE SCHEMA {mv.SCHEMA}"):
        run(cur, s)
    for name, rule in W.items():
        run(cur, mv.build(name, ["Q09"], pack, rule)); print(name, "ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
