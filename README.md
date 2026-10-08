# Trust Sprint demo - does the analyst deserve your trust?

A real Snowflake Cortex Analyst was asked 10 business questions against a semantic view. Each answer was
frozen to a seed, then checked by dbt against the number the data owner expects: **pass**, **fail** or
**trust_warning**, with a reason. All data is fictional (generated seeds, seed 42). No client data.

```
seeds (users, sessions, bookings)               -> Snowflake MISSION_OS_DB.TRUST_DEMO_DEV (+ _PROD) + semantic view
seeds/question_pack.csv   10 questions, expected answer, owner, independent re-derivation
        |  scripts/run_cortex.py  (ONE live Cortex Analyst run, then frozen)
seeds/cortex_answers.csv  generated SQL, returned value, request id, run timestamp
  -> staging: stg_* (views)
  -> marts:   fct_metric_truth, fct_question_verdicts, fct_verdict_summary (tables)
```

## Result of the frozen run (2026-10-08)

| Verdict | Count | Questions |
|---|---|---|
| pass | 5 | Q01 bookings, Q02 revenue, Q03 active users, Q07 top channel, Q10 churn (correct refusal) |
| trust_warning | 2 | Q06 (empty result, undefined slice), Q08 (right number, metric not in the view) |
| fail | 3 | Q04 and Q05 (conversion rate ~10x too high), Q09 (no answer, asked for clarification) |

- The semantic view defines `bookings`, `revenue`, `active_users`, `session_count`, `conversion_rate`. There is **no churn
  metric** on purpose: asking for churn must end in a refusal, and it did.
- `conversion_rate = bookings / session_count` has **no zero-guard on purpose**. The analyst's Q04/Q05 SQL filtered both
  `sessions.session_date` and `bookings.booking_date`; that drops sessions without a booking and inflates the ratio
  (0.85 vs 0.08). With the session filter alone the same view returns the right 0.0809.
- A `fail` or `trust_warning` is a finding about the analyst, not a build error: `dbt build` stays green and the
  verdict column carries the bad news.

## Run it (no credentials)

```
cd trust-sprint-demo && DBT_PROFILES_DIR=. uvx --with dbt-duckdb --from dbt-core dbt build
```

58 nodes: 6 seeds, 9 models, 43 tests. The build is fully offline: it reads the frozen
`cortex_answers.csv`, never Snowflake. `dbt docs generate --static` produces `site/index.html`.

## Re-running the live part (needs Simon's Snowflake connection `mission_os_dogfood`)

```
cd trust-sprint-demo/scripts
export SNOWFLAKE_DEFAULT_CONNECTION_NAME=mission_os_dogfood
uv run --with 'snowflake-connector-python[secure-local-storage]' python snowflake_setup.py   # DEV schema, tables, semantic view
uv run --with 'snowflake-connector-python[secure-local-storage]' python run_cortex.py        # refuses to overwrite the frozen answers
uv run --with 'snowflake-connector-python[secure-local-storage]' python promote.py           # DEV -> PROD, never drops
python3 validate_question_pack.py                                                            # brick validator, rules V1-V6
```

Objects live only in `MISSION_OS_DB.TRUST_DEMO_DEV` and `MISSION_OS_DB.TRUST_DEMO_PROD`. No script drops or replaces
anything (`sf.py` refuses such statements). `profiles.snowflake.example.yml` is a template; the published build runs on DuckDB.

Reused from mission-os bricks: the `CREATE SEMANTIC VIEW IF NOT EXISTS` shape of `snowflake-cortex-semantic-view`, and the
V1-V6 question-set rules of `snowflake-cortex-agent-eval` (`validate_question_pack.py` calls that brick unchanged).
