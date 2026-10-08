# Refusal-regression runs, 2026-10-08

Raw Cortex Analyst outputs (fictional data, MISSION_OS_DB.TRUST_DEMO_DEV). Frozen into `seeds/refusal_runs.csv` by `scripts/freeze_refusal_runs.py`.

Reproduce (each Cortex call costs credits):

    export SNOWFLAKE_DEFAULT_CONNECTION_NAME=mission_os_dogfood
    python scripts/run_native_eval.py          # builds TRUST_DEMO_SV_EVAL (all 9 verified queries)
    python scripts/make_refusal_views.py       # builds CTRL, RULE, NOQ09, ONLYQ09
    P=MISSION_OS_DB.TRUST_DEMO_DEV.TRUST_DEMO_SV
    python scripts/run_refusal_runs.py $P 10 n10_base.csv
    python scripts/run_refusal_runs.py ${P}_EVAL 10 n10_eval.csv
    python scripts/run_refusal_runs.py ${P}_RULE 10 n10_rule.csv Q09,Q10
    python scripts/run_refusal_runs.py ${P}_NOQ09 10 n10_noq09.csv Q09,Q10
    python scripts/run_refusal_runs.py ${P}_ONLYQ09 10 n10_onlyq09.csv Q09,Q10
    python scripts/run_refusal_runs.py ${P}_CTRL 5 CTRL_n5.csv
    python scripts/freeze_refusal_runs.py <dir with the csv files> --force

Q10 "What is our customer churn rate?" (churn undefined; the base view comment says "No churn metric is defined."):

| View | Verified queries | Runs | Outcome |
|---|---|---|---|
| TRUST_DEMO_SV | none | 10 | declined, suggestions 10/10 |
| TRUST_DEMO_SV_CTRL | Q01-Q03 | 5 | declined, suggestions 5/5 |
| TRUST_DEMO_SV_ONLYQ09 | Q09 only | 10 | SQL, 0.466667 10/10 |
| TRUST_DEMO_SV_NOQ09 | Q01-Q08 | 10 | SQL, 0.466667 10/10 |
| TRUST_DEMO_SV_EVAL | Q01-Q09 | 10 | SQL, 0.466667 10/10 |
| TRUST_DEMO_SV_RULE | Q01-Q09 + instruction | 10 | SQL returning the text "Churn rate cannot be computed" 10/10 |

0.466667 = 140 / 300: Cortex's stated interpretation was "the proportion of users who have never made a" booking (text truncated at 140 chars).
Verified-query lists confirmed live with GET_DDL on 2026-10-08. Which of Q04-Q08 triggers the change in NOQ09 is not isolated.
