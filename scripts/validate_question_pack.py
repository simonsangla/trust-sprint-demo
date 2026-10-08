#!/usr/bin/env python3
"""Run the question pack through bricks/snowflake-cortex-agent-eval/validate.py (rules V1-V6) rather than re-implementing them.

Exports seeds/question_pack.csv to the brick's ground-truth JSON shape in a temp file, then calls the brick.
Override the brick location with TRUST_EVAL_BRICK. Exit code is the brick's: 0 accepted, 1 refused.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRICK = Path(os.environ.get("TRUST_EVAL_BRICK", Path.home() / "projects/mission-os/bricks/snowflake-cortex-agent-eval/validate.py"))

if not BRICK.exists():
    sys.exit(f"brick not found: {BRICK} (set TRUST_EVAL_BRICK)")

rows = []
for r in csv.DictReader((ROOT / "seeds" / "question_pack.csv").open()):
    refuse = r["expect_refusal"] == "true"
    out = ("The data cannot answer this question; the correct response is a refusal." if refuse
           else f"{r['expected_answer']}")
    rows.append({
        "input_query": r["question"],
        "ground_truth": {"ground_truth_output": out,
                         "ground_truth_invocations": [] if refuse else [{"tool_name": "analyst", "tool_input": ""}]},
        "owner": r["owner"], "rederived_by": r["rederived_by"],
        "as_of": r["as_of"] or None, "set_name": r["set_name"], "expect_refusal": refuse,
    })
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
    json.dump(rows, f)
sys.exit(subprocess.call([sys.executable, str(BRICK), "--metrics", "answer_correctness", f.name]))
