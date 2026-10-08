#!/usr/bin/env python3
"""Recompute every number in the Thu 15 LinkedIn draft from the committed evidence CSVs. Exit 1 on any mismatch.
Usage: python scripts/check_post_claims.py"""
from __future__ import annotations
import csv, re, sys
from pathlib import Path

E = Path(__file__).resolve().parent.parent / "evidence" / "refusal_runs_2026-10-08"


def rows(f): return list(csv.DictReader((E / f).open()))
def num(v): n = re.findall(r"-?\d+\.\d+", v); return n[-1] if n else None
def refuses(t): return bool(re.search(r"cannot be (computed|calculated)|not defined|unable|cannot calculate", t, re.I))
def computes(r): return r["kind"] == "sql" and not refuses(r["value"]) and bool(re.search(r"\d", r["value"]))


def main() -> int:
    rep = rows("rep.csv") + rows("rep_clean.csv")
    res = []
    def claim(name, got, want): res.append((name, got, want))
    b = [r for r in rows("n10_base.csv") if r["q"] == "Q10"] + [r for r in rep if r["cell"] == "F1"]
    claim("Edit0 declined", f"{sum(r['kind'] == 'suggestions' for r in b)}/{len(b)}", "20/20")
    o = [r for r in rows("n10_onlyq09.csv") if r["q"] == "Q10"] + [r for r in rep if r["cell"] == "F2"]
    claim("Edit1 46.7%", f"{sum(num(r['value']) == '0.466667' for r in o)}/{len(o)}", "20/20")
    e2 = [r for r in rows("push.csv") if r["exp"] == "E3"] + [r for r in rep if r["cell"] == "F3"]
    claim("Edit2 text refuses", f"{sum(refuses(r['text']) for r in e2)}/{len(e2)}", "15/15")
    claim("Edit2 SQL computes a number", f"{sum(computes(r) for r in e2)}/{len(e2)}", "13/15")
    claim("Edit2 free-plan share seen", str(any("free_user" in r["sql"] for r in e2)), "True")
    convs = []
    for f in (rows("rep.csv"), rows("rep_clean.csv")):
        f6 = [r for r in f if r["cell"] == "F6"]
        for i in sorted({r["run"] for r in f6}):
            t = {r["turn"]: r for r in f6 if r["run"] == i}
            convs.append((computes(t["1"]), computes(t["2"]), "churn" in t["2"]["sql"].lower()))
    claim("typo follow-up computes", f"{sum(c[1] for c in convs)}/{len(convs)}", "7/10")
    claim("typo follow-up iff turn1 computed", str(all(c[0] == c[1] for c in convs)), "True")
    w3 = [r for r in rows("t13.csv") if r["view"].endswith("W3")] + [r for r in rep if r["cell"] == "F4-W3"]
    claim("Edit3 clean refusal", f"{sum(r['kind'] == 'suggestions' for r in w3)}/{len(w3)}", "15/15")
    ty = [r for r in rows("typo.csv") if r["cell"] == "TYPO"]
    claim("typo alone declined", f"{sum(r['kind'] == 'suggestions' for r in ty)}/{len(ty)}", "5/5")
    un = [r for r in rows("typo.csv") if r["cell"] == "UNCLEAR"]
    claim("UNCLEAR keyword still computes", f"{sum(computes(r) for r in un)}/{len(un)}", "5/5")
    bad = 0
    for n, g, w in res:
        ok = g == w; bad += not ok
        print("PASS" if ok else "FAIL", n, "got", g, "want", w)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
