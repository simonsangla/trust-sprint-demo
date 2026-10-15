# A semantic view change only breaks answers you notice

**Claim (paraphrased):** editing a semantic view definition is safe to merge if it still deploys; broken answers show up later, in front of users.

**What was tested:** `check.sh` parses the METRICS block of `snowflake/semantic_view.sql` in the tree under test, recomputes every question of `seeds/question_pack.csv` whose metric the view defines (Q01-Q06) from those expressions over the frozen seeds on DuckDB, and compares each with the owner's frozen `expected_answer` (within `tolerance`; UNDEFINED must stay undefined). It then plants one edit, `conversion_rate` divided by `active_users` instead of `session_count`, and requires the gate to go RED. No Snowflake call, no spend. It runs on every PR through `proofs/run_all.sh` in `scripts/pre-pr.sh`.

**Result:** current definition: 6 of 6 answers match. Planted denominator edit: Q04 moves 0.0809 -> 0.3389 and Q05 0.0879 -> 0.2489, the gate exits 1. Bookings, revenue and active users are untouched, so the gate names exactly the answers the edit broke.

**Limit:** the gate replays the view's arithmetic, not Cortex Analyst's SQL generation; questions whose metric is not in the view (Q07-Q10) are out of its scope.
