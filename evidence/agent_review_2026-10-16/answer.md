# REPO_REVIEW_AGENT on MISSION_OS_DB.TRUST_DEMO_DEV

**Question:** What is wrong with this repo?

**Tools called:** repo_search, repo_search

**Answer:**

One check fails. The dbt-checkpoint report (`evidence/checkpoint_2026-10-16/report.txt`) shows the **check-model-has-tests-by-name** hook failed on **fct_verdict_summary**. The model has 0 `unique` tests, and the hook requires at least 1.

The cause is in `models/marts/_marts.yml`. The model's `verdict` column is listed there, but it has no tests at all: no `unique`, no `not_null`. Similar summary models in the same file do have them.

**What could go wrong:** the summary could repeat a verdict, for example "fail" twice, or contain an empty verdict, and nothing would flag it. Dashboards could then double-count or misreport pass/fail totals. The one other check on this model, `tests/assert_verdicts_reconcile.sql`, only checks that the total number of questions adds up.

All other hooks passed.
