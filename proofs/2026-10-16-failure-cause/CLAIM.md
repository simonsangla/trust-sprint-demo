# Every analyst miss has a nameable cause (2026-10-16)

## Claim discussed

When an AI analyst gets a business question wrong, you cannot say why without reading each answer by hand.

## What I tested

The frozen Cortex Analyst run (2026-10-08, `seeds/cortex_answers.csv`). `fct_question_verdicts.failure_cause` is
derived, not typed: from the generated SQL and `seeds/metric_registry.csv`, first match wins.

| Cause | Rule | Questions |
|---|---|---|
| filter | the SQL filters both `sessions.session_date` and `bookings.booking_date` (sessions without a booking drop out of the denominator) | Q04, Q05 |
| definition | the metric is `not_in_view` in the registry, or the question has no defined answer for its slice | Q06 (empty result, undefined slice), Q08 (metric not in view), Q09 (metric not in view) |
| join | the SQL joins tables itself instead of using the view's relationship | none in this run |
| model | any other non-pass | none in this run |
| none | verdict is pass | Q01, Q02, Q03, Q07, Q10 |

`check.sh` rebuilds the tree offline on DuckDB, prints each question's cause and the tally, requires the table
above, runs the `accepted_values` tests on `failure_cause`, then rebuilds a copy where Q04's SQL loses its
`bookings.booking_date` filter and requires Q04's cause to stop being `filter`, so the tag cannot be a constant.

## Result

Holds for this run. `check.sh` prints `Causes: 10 questions, 5 none, 3 definition, 2 filter, 0 join, 0 model`;
with the second date filter removed from Q04's SQL its cause becomes `model`. Chart: `causes.png`
(`bash check.sh | uvx --with matplotlib python chart.py causes.png`).

Run it: `bash proofs/2026-10-16-failure-cause/check.sh` (override with `DBT="uvx --with dbt-duckdb --from dbt-core dbt"`). Fictional data only.
