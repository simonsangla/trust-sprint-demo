"""Gate for the static demo: page numbers must equal the data.

Run: cd <repo> && uvx --with duckdb pytest tests/test_build_app.py -q
(needs trust_sprint_demo.duckdb from `dbt build`).
"""
import csv
import re
import struct
import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_app  # noqa: E402

APP = ROOT / "app"
PAGE = (APP / "index.html").read_text(encoding="utf-8")


def rows(name):
    with open(ROOT / "seeds" / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(ROOT / "trust_sprint_demo.duckdb"), read_only=True)
    yield c
    c.close()


def test_page_is_fresh():
    assert PAGE == build_app.build_page(build_app.load()), "app/index.html is stale: rerun build_app.py"


def test_verdict_counts_match_dbt(con):
    got = dict(con.execute("select verdict, count(*) from fct_question_verdicts group by 1").fetchall())
    for key, css in [("pass", "pass"), ("trust_warning", "trust_warning"), ("fail", "fail")]:
        m = re.search(rf'<div class="tile {css}"><b>(\d+)</b>', PAGE)
        assert m and int(m.group(1)) == got.get(key, 0), key
    assert (got["pass"], got["trust_warning"], got["fail"]) == (5, 3, 2)
    assert f'Of {sum(got.values())} questions' in PAGE


def test_question_cards_match_pack_and_verdicts(con):
    verdicts = dict(con.execute("select question_id, verdict from fct_question_verdicts").fetchall())
    pack = rows("question_pack.csv")
    assert len(re.findall(r'<article class="q ', PAGE)) == len(pack) == 10
    for r in pack:
        qid = r["question_id"]
        m = re.search(rf'<article class="q (\w+)" id="{qid.lower()}" data-verdict="(\w+)">', PAGE)
        assert m, qid
        assert m.group(1) == m.group(2) == verdicts[qid], qid
        assert build_app.esc(r["question"]) in PAGE, qid


def test_q04_values_equal_data():
    ans = {r["question_id"]: r for r in rows("cortex_answers.csv")}["Q04"]
    exp = {r["question_id"]: r for r in rows("question_pack.csv")}["Q04"]
    got_pct = f"{float(ans['answer_value']) * 100:.2f}%"
    exp_pct = f"{float(exp['expected_answer']) * 100:.2f}%"
    assert (got_pct, exp_pct) == ("85.26%", "8.09%")
    m = re.search(r'<div class="bad"><dt>Cortex answered</dt><dd>([^<]+)</dd>', PAGE)
    n = re.search(r'<div class="good"><dt>Expected</dt><dd>([^<]+)</dd>', PAGE)
    assert m.group(1) == got_pct and n.group(1) == exp_pct
    hero = re.search(r"<h1>(.*?)</h1>", PAGE).group(1)
    assert hero == (f"On a fictional dataset, I asked Cortex Analyst for the June conversion rate. "
                    f"It said {round(float(ans['answer_value']) * 100)}%. "
                    f"The right answer was {round(float(exp['expected_answer']) * 100)}%.")
    assert "Fictional data &middot; real Cortex Analyst run &middot; 8 Oct 2026" in PAGE


def test_q04_sql_has_double_filter_and_fix_removes_it():
    sql = {r["question_id"]: r for r in rows("cortex_answers.csv")}["Q04"]["generated_sql"]
    assert "sessions.session_date" in sql and "bookings.booking_date" in sql
    assert len(re.findall(r'<mark class="bad">bookings\.booking_date', PAGE)) == 2  # both bounds
    assert "booking_date" not in build_app.fixed_sql(sql)
    assert "session_date" in build_app.fixed_sql(sql)


def test_q04_decomposition_from_staging(con):
    dec = build_app.june_decomposition(con, {r["question_id"]: r for r in rows("question_pack.csv")}["Q04"])
    assert f"{dec['num']:,} confirmed bookings" in PAGE
    assert f"{dec['sess_booked']:,} sessions that have a June booking" in PAGE
    assert f"all {dec['sess_all']:,} June sessions" in PAGE
    assert round(dec["num"] / dec["sess_all"], 4) == 0.0809


def test_every_request_id_present_in_full():
    ids = [r["request_id"] for r in rows("cortex_answers.csv")]
    assert len(ids) == 10 and len(set(ids)) == 10
    for rid in ids:
        assert f'data-full="{rid}"' in PAGE, rid


def test_no_dbt_logo_or_docs_look():
    for f in APP.rglob("*"):
        assert "dbt" not in f.name.lower(), f
    assert not re.search(r'<(img|svg|link|source)[^>]*dbt', PAGE, re.I)
    assert not re.search(r'(src|href)="[^"]*dbt[^"]*"', PAGE, re.I)
    assert "<img" not in PAGE  # no raster brand marks at all
    assert "docs.getdbt.com" not in PAGE and "dbt-docs" not in PAGE


def test_cta_footer_and_og():
    assert 'href="https://cal.com/simon-sangla/trust-sprint-scoping-call?ref=demo"' in PAGE
    assert "5 days, fixed scope, from EUR 4,500" in PAGE
    assert "Simon Sangla &middot; simonsangla.com" in PAGE
    for tag in ("og:title", "og:description", "og:image", "og:url", "twitter:card"):
        assert tag in PAGE, tag
    png = (APP / "og.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    w, h = struct.unpack(">II", png[16:24])
    assert (w, h) == (1200, 630)
