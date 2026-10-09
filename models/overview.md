{% docs __overview__ %}

# Cortex Analyst said 85%. The right answer was 8%.

A real Snowflake Cortex Analyst was asked the June conversion rate on a governed semantic view. Fictional data, one run, 8 Oct 2026.

## The answer, for the June 2026 conversion rate

| | Conversion rate |
|---|---|
| **Cortex Analyst said** | **85.26%** |
| The right answer | 8.09% |

**A governed metric did not make the answer right.** The view defines `conversion_rate`; the analyst still filtered the month twice and shrank the denominator.

> **Same view, one filter less.** Drop the extra date filter and the same semantic view returns **8.09%**, the number the data owner expects. Recomputed from the seeds in DuckDB (`proofs/`), not re-run live on Snowflake.

## What was tested

I created a Snowflake `SEMANTIC_VIEW` over three fictional tables (users, sessions, bookings) with five governed metrics, asked Cortex Analyst ten business questions once, and froze every answer. dbt then checks each answer against the number its owner expects and gives a verdict with a reason: pass, warning or fail. Every Cortex call keeps its Snowflake request ID, so the exact call can be found again.

| Verdict | Count | Questions |
|---|---|---|
| Pass | 5 | Q01, Q02, Q03, Q07, Q10 (a correct refusal) |
| Warning | 3 | Q06 (empty result), Q08 (right number, metric not in the view), Q09 (asked for clarification) |
| Fail | 2 | Q04 and Q05 (conversion rate about ten times too high) |

## The Q04 mechanism

Cortex Analyst generated this SQL (request `2f271fe5-3db1-4e17-8784-cd9be4d2d4f6`). The semantic view exposes two dates and does not say which one defines a month for this metric; it used both:

```sql
SELECT * FROM SEMANTIC_VIEW(
  MISSION_OS_DB.TRUST_DEMO_DEV.TRUST_DEMO_SV
  METRICS CONVERSION_RATE
  WHERE sessions.session_date >= '2026-06-01'
    AND sessions.session_date < '2026-07-01'
    AND bookings.booking_date >= '2026-06-01'   -- the extra filter
    AND bookings.booking_date < '2026-07-01'
)
```

The booking-date filter keeps only the sessions that have a June booking, so the denominator drops from 1,001 sessions to 95 (14 of them with a cancelled booking) while the 81 confirmed bookings stay: 81 / 95 = **85.26%**.

The same metric with the session-date filter alone:

```sql
SELECT * FROM SEMANTIC_VIEW(
  MISSION_OS_DB.TRUST_DEMO_DEV.TRUST_DEMO_SV
  METRICS CONVERSION_RATE
  WHERE sessions.session_date >= '2026-06-01'
    AND sessions.session_date < '2026-07-01'
)
```

81 / 1,001 = **8.09%**, which matches the owner's expected answer. This 8.09% is recomputed from the seeds in DuckDB by the proof, not re-run on Snowflake. Q05 follows the same pattern: Cortex answered 90.77%, the expected answer is 8.79%.

## All 10 questions

| Q | Question | Expected | Cortex answered | Verdict | Snowflake request ID |
|---|---|---|---|---|---|
| Q01 | How many bookings did we have in March 2026? | 22 | 22 | Pass | `f648d3b3-51d0-4750-98cd-c60cdc557f24` |
| Q02 | What was total revenue in Q1 2026? | 6,983 | 6,983 | Pass | `87f7008d-96f4-43e8-b65c-e1ce4246e31c` |
| Q03 | How many active users did we have in April 2026? | 196 | 196 | Pass | `228b9cb0-fd58-439d-8477-eb443d0ff8be` |
| Q04 | What was the booking conversion rate in June 2026? | 8.09% | 85.26% | FAIL | `2f271fe5-3db1-4e17-8784-cd9be4d2d4f6` |
| Q05 | What was the booking conversion rate for the organic channel in the first half of 2026? | 8.79% | 90.77% | FAIL | `23675ca8-411c-4a3a-8849-193b65812e8e` |
| Q06 | What was the booking conversion rate for the partner channel in January 2026? | Undefined | Empty result | Warning | `75b6843f-05d7-43af-9935-739f44675b92` |
| Q07 | Which acquisition channel generated the most revenue in the first half of 2026? | organic | organic | Pass | `f625cc27-db47-4702-8b69-00556c25890d` |
| Q08 | What was the average booking value in the first half of 2026? | 97 | 97 | Warning | `e4f60910-2242-47f8-acfd-d8af6a1fbecb` |
| Q09 | How many paying customers do we have? | 134 | Asked for clarification | Warning | `beeab2a5-531c-4113-9557-fd0f00ef678f` |
| Q10 | What is our customer churn rate? | Undefined | Refused | Pass | `45d17a06-d9c7-426e-b583-4f2b16cc38ea` |

Why the warnings: Q06 returned an empty result with no statement that the metric is undefined for that slice. Q08 is the right value but `avg_booking_value` is not defined in the view, so the analyst computed it ad hoc. Q09 asked for clarification because "paying customers" is not defined in the view. Q10 has no churn metric on purpose, and the refusal is the correct answer.

## Tested in public

The claim "a semantic view makes an AI analyst trustworthy" is re-run against this demo. It is a script in `proofs/` that CI re-runs on every push, and it appears in the lineage graph as an exposure.

| Date | Claim tested | Result |
|---|---|---|
| 2026-10-09 | A governed semantic view gives trustworthy analyst answers | **Holds.** On a governed view, Q04 and Q05 came back about ten times too high; the pinned test goes red when the owner's number is wrong. [Proof](#!/exposure/exposure.trust_sprint_demo.proof_2026_10_09_semantic_view_still_wrong) |

## Start here

Open the [fct_question_verdicts model](#!/model/model.trust_sprint_demo.fct_question_verdicts): one row per question, with the verdict and the reason.

Fictional data. The dbt build runs offline on DuckDB and reads the frozen run, never Snowflake.

Built by Simon Sangla — [simonsangla.com](https://simonsangla.com)

{% enddocs %}
