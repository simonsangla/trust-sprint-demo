#!/usr/bin/env python3
"""Recompute every number in the Wed 21 Oct LinkedIn post ("Cost vs Correctness") and render the post.
Exit 1 on any mismatch with the post text passed to --post, or with the frozen run.
  python scripts/check_post_claims_cost.py [--post POST.txt] [--render OUT.txt] [--proof-out SAVED_CHECK_OUTPUT]

Where each number comes from (none is typed in this file):
  10 questions, the date 8 Oct 2026, 85%      seeds/cortex_answers.csv (frozen run; Q04 answer_value, run_ts)
  8.09% (the "8%")                            recomputed here from seeds/sessions.csv and seeds/bookings.csv
                                              (session-date filter only, confirmed bookings) and required to equal
                                              the owner value in seeds/question_pack.csv
  5 pass / 3 warning / 2 fail                 the "Verdicts:" line of proofs/2026-10-09-semantic-view-still-wrong/check.sh
                                              (dbt on DuckDB, which also checks it against the page table)
The first two lines quote an outside article (Medium recap of a Snowflake User Group talk); they are fixed text here and are
verified against the article by the R3 reviewer, not by this script."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROOF = ROOT / "proofs" / "2026-10-09-semantic-view-still-wrong" / "check.sh"

POST = """\"A dashboard runs the same query every morning. An agent takes a different path every run.\"
That is from a Medium recap of a Snowflake User Group Netherlands talk. It says one prompt becomes spend in Cortex inference, Cortex Search, AI functions and the warehouses that run the SQL, and that Snowflake still has no single view of what that interaction cost.
Fair. But before the cost question, I'd ask: was the answer right? I tested that on fictional data, in my own demo (Trust Sprint).
I ran {n} business questions through a real Cortex Analyst. {n_pass} passed, {n_warn} gave warnings, {n_fail} failed.
On a governed semantic view, the June conversion rate came back as {got_pct}%. The right answer was {true_pct}% ({true_2dp}% recomputed from demo seeds in DuckDB, not on Snowflake).
(One run on {run_date}. Not a client result, and one run says nothing about how often this happens.)
So I'd check answers against known results before building cost attribution on top of them.
How do you check your agents' answers today?
#Snowflake #Cortex #DataQuality #AnalyticsEngineering
Media: trustsprint-85-vs-8.png - Screenshot of the page title \"Cortex Analyst said {got_pct}%. The right answer was {true_pct}%.\"
"""

def rows(name):
    with (ROOT / "seeds" / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def month_ratio(sessions, bookings, start, end):
    """Confirmed bookings / sessions, session-date filter only (the owner's definition)."""
    ids = {s["session_id"] for s in sessions if start <= s["session_date"] <= end}
    done = {b["booking_id"] for b in bookings if b["session_id"] in ids and b["status"] == "confirmed"}
    return len(done) / len(ids)


def verdicts(proof_out):
    out = Path(proof_out).read_text() if proof_out else subprocess.run(
        ["bash", str(PROOF)], capture_output=True, text=True, cwd=ROOT).stdout
    m = re.search(r"^Verdicts: (\d+) questions, (\d+) pass, (\d+) warning, (\d+) fail \(page table: (\d+) pass, (\d+) warning, (\d+) fail\)", out, re.M)
    if not m:
        raise SystemExit("FAIL: no 'Verdicts:' line in the proof output (did check.sh pass?)")
    n, p, w, f, pp, pw, pf = map(int, m.groups())
    if (p, w, f) != (pp, pw, pf):
        raise SystemExit("FAIL: dbt tally differs from the page table")
    if "PASS:" not in out.splitlines()[-1]:
        raise SystemExit("FAIL: proof check.sh did not end in PASS")
    return n, p, w, f


def compute(proof_out):
    answers = {r["question_id"]: r for r in rows("cortex_answers.csv")}
    pack = {r["question_id"]: r for r in rows("question_pack.csv")}
    got = float(answers["Q04"]["answer_value"])
    owner = float(pack["Q04"]["expected_answer"])
    true = month_ratio(rows("sessions.csv"), rows("bookings.csv"), "2026-06-01", "2026-06-30")
    if abs(true - owner) > float(pack["Q04"]["tolerance"] or 0) + 5e-4:
        raise SystemExit(f"FAIL: recomputed June conversion {true:.6f} != owner value {owner}")
    n, p, w, f = verdicts(proof_out)
    run_ts = {r["run_ts"][:10] for r in answers.values()}
    if len(run_ts) != 1 or len(answers) != n:
        raise SystemExit("FAIL: the frozen run is not one day / one row per question")
    d = dt.date.fromisoformat(run_ts.pop())
    return {"n": n, "n_pass": p, "n_warn": w, "n_fail": f,
            "got_pct": f"{round(got * 100)}", "true_pct": f"{round(true * 100)}", "true_2dp": f"{true * 100:.2f}",
            "run_date": f"{d.day} {d.strftime('%b %Y')}"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--post"); ap.add_argument("--render"); ap.add_argument("--proof-out")
    a = ap.parse_args()
    vals = compute(a.proof_out)
    text = POST.format(**vals)
    for k, v in vals.items():
        print("VALUE", k, v)
    bad = 0
    if a.post:
        want = text.splitlines(); have = Path(a.post).read_text(encoding="utf-8").splitlines()
        if len(want) != len(have):
            print(f"FAIL: post has {len(have)} lines, rendered {len(want)}"); bad = 1
        for i, (w, h) in enumerate(zip(want, have)):
            if w != h:
                print(f"FAIL: line {i + 1} differs\n  rendered: {w}\n  post:     {h}"); bad = 1
        print("PASS: post equals the text rendered from the frozen run" if not bad else "FAIL: post differs from the rendered text")
    if a.render and not bad:
        Path(a.render).write_text(text, encoding="utf-8"); print("rendered", a.render)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
