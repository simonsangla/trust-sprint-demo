# When the analyst says it cannot compute a metric, it has refused (2026-10-09)

**Claim discussed (paraphrased):** if an AI analyst answers "this cannot be computed" to a question about a metric
that is not defined, it has refused, so grading the answer text is enough.

**What I tested:** the same question, "What is our customer churn rate?", on a semantic view where churn is not
defined. Twenty Cortex Analyst runs after each of four edits of the view, all on 2026-10-08, then frozen in
`evidence/refusal_runs_2026-10-08/batch20.csv`. Fictional data. Each run keeps its Snowflake request ID. Everything
below is recounted offline from that file; no Snowflake call.

| Edit to the view | Said "cannot be computed" in the answer | SQL result was a number |
|---|---|---|
| E0 no verified query | 20 of 20 | 0 of 20 (no SQL ran) |
| E1 one unrelated verified query (paying customers) | 0 of 20 | **20 of 20** (46.7%) |
| E2 instruction "do not approximate undefined metrics" | **20 of 20** | **11 of 20** (the other 9 returned a refusal message as SQL) |
| E3 same rule, moved to question categorization ("unanswerable, reject") | declined in other words | 0 of 20 (no SQL ran) |

**Result:** the claim fails. At E2 every answer said churn cannot be computed, and in 11 of those 20 runs the SQL under
the sentence computed a number anyway (for example 55.3%, the share of users on the free plan). A grader that reads
only the text scores E2 as 20 of 20 correct refusals; a grader that also reads the SQL result finds 11 failures. The
refusal also depended on the configuration: one verified query that never mentions churn took E0 from 0 of 20 to 20 of 20
numbers (E1).

**Q10 in the original run:** in the first frozen run (`seeds/cortex_answers.csv`, request
`45d17a06-d9c7-426e-b583-4f2b16cc38ea`) Q10 produced no SQL and no rows, and the text says it is unable to calculate
churn. That is the correct refusal and the reason Q10 is a pass in `fct_question_verdicts`; the proof above shows how
fragile that pass is after an edit.

**What the script checks (`check.sh`):**
1. per edit, the count of runs whose text says no and the count whose SQL result is a number, with its own rules (it does not import `scripts/refusal_outcome.py`), against the numbers in the table;
2. Q10 of the original run is a refusal with no SQL and no rows;
3. the pinned `scripts/check_post_claims.py` passes;
4. the same count on a copy where the E2 numeric results are replaced by refusal text goes RED, so it cannot pass vacuously.

**Run it:** `bash proofs/2026-10-09-refusal-text-is-not-a-refusal/check.sh` (needs only `python3`). Fictional data only.
