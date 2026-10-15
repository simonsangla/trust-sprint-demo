# Proofs

Each folder tests one claim from the public dbt / Snowflake conversation against this demo, with a
re-runnable `check.sh` and a `CLAIM.md` (claim paraphrased, what was tested, result). Fictional data only;
the poster is never named. `bash proofs/run_all.sh` runs them all; CI runs them on every push.
Convention: `proofs/<date>-<slug>/{CLAIM.md,check.sh}`, same as dbt-revenue-variance-demo.

| Date | Topic | Result | Proof |
|---|---|---|---|
| 2026-10-09 | A semantic view makes the analyst trustworthy | Q04 0.0809 and Q05 0.0879 came back as 0.852632 and 0.907692 on a governed view; a double date filter explains both | [CLAIM](2026-10-09-semantic-view-still-wrong/CLAIM.md) · [check.sh](2026-10-09-semantic-view-still-wrong/check.sh) |
| 2026-10-09 | When the analyst says it cannot compute a metric, it has refused | After one unrelated verified query the answer was 46.7% in 20 of 20; after one instruction every answer said churn cannot be computed (20 of 20) and the SQL under it computed a number in 11 of 20; 140 Cortex calls in the batch (`value.sh` checks any cited number) | [CLAIM](2026-10-09-refusal-text-is-not-a-refusal/CLAIM.md) · [check.sh](2026-10-09-refusal-text-is-not-a-refusal/check.sh) |
| 2026-10-12 | Snowflake's native evaluation replaces your own test pack | The native evaluation grades SQL against verified queries (question + expected SQL): 9 of 10 questions can enter the set; Q10 churn, whose right answer is a refusal, cannot | [CLAIM](2026-10-12-native-eval-cannot-grade-refusal/CLAIM.md) · [check.sh](2026-10-12-native-eval-cannot-grade-refusal/check.sh) |
| 2026-10-12 | An AI assistant is more careful than the role that calls it | The same assistant SQL returned 164 customer emails as a broad role and 0 as a restricted role; removing the (emulated) masking policy gave the restricted role all 164 | [CLAIM](2026-10-12-role-reads-as-caller/CLAIM.md) · [check.sh](2026-10-12-role-reads-as-caller/check.sh) |
| 2026-10-15 | A semantic view edit is safe if it still deploys | Every view-defined question (Q01-Q06) is replayed offline from the view's own metric expressions against its frozen answer; redefining the conversion denominator moves exactly Q04 0.0809 -> 0.3389 and Q05 0.0879 -> 0.2489, coalescing it to 0 moves exactly Q06 UNDEFINED -> 0.0, and a renamed metric fails too | [CLAIM](2026-10-15-semantic-view-change-gate/CLAIM.md) · [check.sh](2026-10-15-semantic-view-change-gate/check.sh) |
