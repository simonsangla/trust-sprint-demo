# Proofs

Each folder tests one claim from the public dbt / Snowflake conversation against this demo, with a
re-runnable `check.sh` and a `CLAIM.md` (claim paraphrased, what was tested, result). Fictional data only;
the poster is never named. `bash proofs/run_all.sh` runs them all; CI runs them on every push.
Convention: `proofs/<date>-<slug>/{CLAIM.md,check.sh}`, same as dbt-revenue-variance-demo.

| Date | Topic | Result | Proof |
|---|---|---|---|
| 2026-10-09 | A semantic view makes the analyst trustworthy | Q04 0.0809 and Q05 0.0879 came back as 0.852632 and 0.907692 on a governed view; a double date filter explains both | [CLAIM](2026-10-09-semantic-view-still-wrong/CLAIM.md) · [check.sh](2026-10-09-semantic-view-still-wrong/check.sh) |
| 2026-10-09 | When the analyst says it cannot compute a metric, it has refused | After one instruction every answer said churn cannot be computed (20 of 20) and the SQL under it computed a number in 11 of 20 | [CLAIM](2026-10-09-refusal-text-is-not-a-refusal/CLAIM.md) · [check.sh](2026-10-09-refusal-text-is-not-a-refusal/check.sh) |
