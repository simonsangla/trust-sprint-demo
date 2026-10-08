#!/usr/bin/env python3
"""Recompute every number in the Thu 15 LinkedIn post (version C) from the uniform 20-run batch, and render the post.
Exit 1 on any mismatch with the expected values below (they are what the post says).
  python scripts/check_post_claims.py [--render OUT.md]"""
from __future__ import annotations
import argparse, csv, re, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from refusal_outcome import REFUSE, outcome, gave_number  # noqa: E402

CSV = Path(__file__).resolve().parent.parent / "evidence" / "refusal_runs_2026-10-08" / "batch20.csv"
EXPECT = {"n": 20, "e0_nonum": 20, "e1_top": "46.7", "e2_said": 20, "e2_num": 11, "single_sha": True, "control_ok": 20}
POST = """One verified query about paying customers was enough for Cortex Analyst to make up a churn definition and answer a churn rate of {e1_top}%.
Churn was never defined. Fictional data, my own demo, {n} runs per edit.
Before that query: no number in {e0_nonum} of {n}.
After I told it not to approximate: the answer said churn cannot be computed in {e2_said} of {n}, and the SQL under it still computed a number in {e2_num}.
The sentence says no. The table under it is what ends up in a slide.
So for every question an assistant should decline, I test what the answer says and what the SQL computes, on every semantic view edit.
That is the AI Analytics Trust Sprint: 5 days, fixed scope, from EUR 4,500.
#Snowflake #CortexAnalyst #AnalyticsEngineering"""


def compute(rows):
    churn = lambda e: [r for r in rows if r["cell"] == "churn" and r["edit"] == e]
    e0, e1, e2 = churn("E0"), churn("E1"), churn("E2")
    vals = [re.findall(r"-?\d+\.\d+", r["value"])[-1] for r in e1 if gave_number(outcome(r)) and re.findall(r"-?\d+\.\d+", r["value"])]
    top = Counter(vals).most_common(1)[0][0] if vals else "0"
    ns = {len(churn(e)) for e in ("E0", "E1", "E2", "E3")}
    return {"n": ns.pop() if len(ns) == 1 else -1,
            "e0_nonum": sum(not gave_number(outcome(r)) for r in e0),
            "e1_top": "%.1f" % (100 * float(top)),
            "e2_said": sum(bool(REFUSE.search(r["text"])) for r in e2),
            "e2_num": sum(gave_number(outcome(r)) for r in e2),
            "single_sha": len({r["script_sha"] for r in rows}) == 1,
            "control_ok": sum(r["cell"] == "control" and "6983" in r["value"] for r in rows)}


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--render"); a = ap.parse_args()
    got = compute(list(csv.DictReader(CSV.open())))
    bad = 0
    for k, want in EXPECT.items():
        ok = got[k] == want; bad += not ok
        print("PASS" if ok else "FAIL", k, "got", got[k], "want", want)
    if a.render and not bad:
        Path(a.render).write_text(POST.format(**got) + "\n", encoding="utf-8"); print("rendered", a.render)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
