# A semantic view does not make the analyst's answer right (2026-10-09)

**Claim discussed (paraphrased):** put your metrics in a governed semantic view and an AI analyst on top of it
will give trustworthy numbers.

**What I tested:** a real Snowflake Cortex Analyst run (2026-10-08, one run, then frozen) on a semantic view
`TRUST_DEMO_SV` with `conversion_rate = bookings / session_count`. Ten business questions, each checked against
the number its owner expects. Two conversion-rate questions came back about ten times too high. Everything below
is recomputed offline from the seeds in DuckDB; the frozen answers are in `seeds/cortex_answers.csv`.

| Question | Owner's number | Session filter only (recomputed) | Both date filters (recomputed) | Analyst returned | Snowflake request ID |
|---|---|---|---|---|---|
| Q04 conversion rate, June 2026 | 0.0809 | 0.080919 | 0.852632 | 0.852632 | `2f271fe5-3db1-4e17-8784-cd9be4d2d4f6` |
| Q05 conversion rate, organic, H1 2026 | 0.0879 | 0.087928 | 0.907692 | 0.907692 | `23675ca8-411c-4a3a-8849-193b65812e8e` |

**Why:** the generated SQL filtered `sessions.session_date` AND `bookings.booking_date`. A session without a booking
has no booking date, so the second filter drops it from the denominator while every booking stays in the numerator.
With the session-date filter alone the same view gives the owner's number. The view is governed; the question
was still answered wrongly, and `dbt build` has no complaint about it unless a known-answer test exists.

**The 8.09% is recomputed, not re-run:** this proof does not call Snowflake. The "session filter only" column is
re-derived from the `sessions` and `bookings` seeds in DuckDB; the analyst's numbers are the frozen run.

**What the script checks (`check.sh`):**
1. both ratios per question re-derived from the seeds with its own SQL (no reuse of the test's SQL);
2. the owner's number equals the session-filter-only ratio (tolerance 0.0005) and the analyst's number equals the both-filters ratio (1e-6);
3. the pinned test `tests/assert_conversion_double_filter_mechanism.sql` passes;
4. the same test goes RED on a copy where the owner's Q04 number is corrupted (0.0809 -> 0.8526), so it cannot pass vacuously.

**Result:** holds. A governed view plus a real analyst still returned 85.26% where the right answer is 8.09%.

**Run it:** `bash proofs/2026-10-09-semantic-view-still-wrong/check.sh` (needs `uv`/`dbt-duckdb`; override with `DBT="uvx --with dbt-duckdb --from dbt-core dbt"`). Fictional data only.
