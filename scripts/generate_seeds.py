#!/usr/bin/env python3
"""Generate the fictional seeds (users, sessions, bookings) and question_pack.csv. Seed 42, stdlib only.

All data is invented. expected_answer values are computed here from the generated rows, then
re-derived independently by the dbt model fct_metric_truth (see tests/assert_question_pack_matches_data.sql).
"""
from __future__ import annotations

import csv
import datetime as dt
import random
from pathlib import Path

SEEDS = Path(__file__).resolve().parent.parent / "seeds"
rng = random.Random(42)

COUNTRIES = ["PT", "FR", "ES", "DE", "GB"]
PLANS = ["free", "pro", "team"]
PLAN_WEIGHTS = [0.55, 0.33, 0.12]
PLAN_PRICE = {"free": 29.0, "pro": 79.0, "team": 189.0}
CHANNELS = ["organic", "paid", "email", "referral"]
START, END = dt.date(2026, 1, 1), dt.date(2026, 6, 30)
PARTNER_START = dt.date(2026, 3, 1)  # partner channel has zero sessions before March, on purpose


def daterange(a: dt.date, b: dt.date):
    for i in range((b - a).days + 1):
        yield a + dt.timedelta(days=i)


users = []
for i in range(1, 301):
    signup = dt.date(2025, 7, 1) + dt.timedelta(days=rng.randrange(0, 365))
    users.append({
        "user_id": f"U{i:04d}", "signup_date": signup.isoformat(),
        "country": rng.choice(COUNTRIES), "plan": rng.choices(PLANS, PLAN_WEIGHTS)[0],
    })

sessions, bookings = [], []
for u in users:
    first = max(START, dt.date.fromisoformat(u["signup_date"]))
    n = rng.randrange(0, 21)
    for _ in range(n):
        d = first + dt.timedelta(days=rng.randrange(0, (END - first).days + 1))
        pool = CHANNELS + (["partner"] if d >= PARTNER_START else [])
        channel = rng.choice(pool)
        sid = f"S{len(sessions) + 1:05d}"
        sessions.append({"session_id": sid, "user_id": u["user_id"], "session_date": d.isoformat(), "channel": channel})
        if rng.random() < 0.09:
            amount = round(PLAN_PRICE[u["plan"]] * rng.choice([1, 1, 1, 2, 3]), 2)
            status = "cancelled" if rng.random() < 0.14 else "confirmed"
            bookings.append({"booking_id": f"B{len(bookings) + 1:05d}", "user_id": u["user_id"], "session_id": sid,
                             "booking_date": d.isoformat(), "amount": f"{amount:.2f}", "status": status})


def write(name: str, rows: list[dict]):
    with (SEEDS / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


write("users.csv", users)
write("sessions.csv", sessions)
write("bookings.csv", bookings)

# ---- ground truth, computed straight from the rows -------------------------------------------
sess_by_id = {s["session_id"]: s for s in sessions}
conf = [b for b in bookings if b["status"] == "confirmed"]


def in_range(d: str, a: str, b: str) -> bool:
    return a <= d <= b


def n_bookings(a, b):
    return sum(1 for x in conf if in_range(x["booking_date"], a, b))


def revenue(a, b, channel=None):
    return round(sum(float(x["amount"]) for x in conf if in_range(x["booking_date"], a, b)
                     and (channel is None or sess_by_id[x["session_id"]]["channel"] == channel)), 2)


def n_sessions(a, b, channel=None):
    return sum(1 for s in sessions if in_range(s["session_date"], a, b) and (channel is None or s["channel"] == channel))


def conv(a, b, channel=None):
    num = sum(1 for x in conf if in_range(x["booking_date"], a, b)
              and (channel is None or sess_by_id[x["session_id"]]["channel"] == channel))
    return round(num / n_sessions(a, b, channel), 4)


h1 = ("2026-01-01", "2026-06-30")
top_channel = max(CHANNELS + ["partner"], key=lambda c: revenue(*h1, channel=c))
active_apr = len({s["user_id"] for s in sessions if in_range(s["session_date"], "2026-04-01", "2026-04-30")})
avg_value = round(revenue(*h1) / n_bookings(*h1), 2)
paying = sum(1 for u in users if u["plan"] != "free")
assert n_sessions("2026-01-01", "2026-01-31", "partner") == 0

OWN = {"growth": "head_of_growth", "fin": "finance_lead", "prod": "product_lead"}
RED = "analytics_engineer"
# id, question, metric_key, date_from, date_to, channel, expected, tolerance, owner, refuse, set
Q = [
    ("Q01", "How many bookings did we have in March 2026?", "bookings", "2026-03-01", "2026-03-31", "", n_bookings("2026-03-01", "2026-03-31"), 0, OWN["growth"], False, "build"),
    ("Q02", "What was total revenue in Q1 2026?", "revenue", "2026-01-01", "2026-03-31", "", revenue("2026-01-01", "2026-03-31"), 0.01, OWN["fin"], False, "build"),
    ("Q03", "How many active users did we have in April 2026?", "active_users", "2026-04-01", "2026-04-30", "", active_apr, 0, OWN["prod"], False, "build"),
    ("Q04", "What was the booking conversion rate in June 2026?", "conversion_rate", "2026-06-01", "2026-06-30", "", conv("2026-06-01", "2026-06-30"), 0.0005, OWN["growth"], False, "build"),
    ("Q05", "What was the booking conversion rate for the organic channel in the first half of 2026?", "conversion_rate", h1[0], h1[1], "organic", conv(*h1, channel="organic"), 0.0005, OWN["growth"], False, "build"),
    ("Q06", "What was the booking conversion rate for the partner channel in January 2026?", "conversion_rate", "2026-01-01", "2026-01-31", "partner", "UNDEFINED", 0, OWN["growth"], True, "holdout"),
    ("Q07", "Which acquisition channel generated the most revenue in the first half of 2026?", "top_channel_by_revenue", h1[0], h1[1], "", top_channel, 0, OWN["fin"], False, "holdout"),
    ("Q08", "What was the average booking value in the first half of 2026?", "avg_booking_value", h1[0], h1[1], "", avg_value, 0.01, OWN["fin"], False, "build"),
    ("Q09", "How many paying customers do we have?", "paying_customers", "", "", "", paying, 0, OWN["prod"], False, "holdout"),
    ("Q10", "What is our customer churn rate?", "churn_rate", "", "", "", "UNDEFINED", 0, OWN["prod"], True, "build"),
]
with (SEEDS / "question_pack.csv").open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["question_id", "question", "metric_key", "date_from", "date_to", "channel", "expected_answer",
                "tolerance", "owner", "rederived_by", "as_of", "set_name", "expect_refusal"])
    for qid, q, mk, d1, d2, ch, exp, tol, owner, refuse, sn in Q:
        w.writerow([qid, q, mk, d1, d2, ch, exp, tol, owner, RED, "2026-06-30", sn, str(refuse).lower()])

print(f"users={len(users)} sessions={len(sessions)} bookings={len(bookings)} confirmed={len(conf)}")
for qid, q, mk, *_rest in Q:
    print(qid, mk, _rest[3])
