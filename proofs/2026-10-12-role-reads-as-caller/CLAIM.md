# An AI assistant reads data as the role that calls it (2026-10-12)

**Claim discussed (paraphrased):** an AI analytics assistant reads data as the role that calls it: it will
not be more careful than its role. Whatever protects a personal column has to live in the data platform, on the
caller's role, not in the assistant.

**What I tested:** one "assistant question" ("list the customers who signed up in 2026, with their email, so I
can contact them"), written once as SQL (`question.sql.j2`) and run unchanged under two roles on the same
fictional data:

| Role | Rows returned | Emails exposed | What the email column shows |
|---|---|---|---|
| `ANALYST_FULL` (broad) | 164 | 164 | `u0001@example.test` ... |
| `ANALYST_RESTRICTED` | 164 | 0 | `***MASKED***` |
| `ANALYST_RESTRICTED`, mask removed (mutated copy) | 164 | 164 | `u0001@example.test` ... (RED) |

The SQL is byte-identical in every run. The only thing between the restricted caller and the emails is the
masking policy (`policy.sql.j2`) evaluated against the caller's role. Remove it and the same assistant, asked
the same question, hands the restricted role every address: it was never "being careful", the role was.

**Honest limits: this is an emulation, not Snowflake.** DuckDB has no roles and no masking policies. The policy
is a `CASE` on a dbt var `role` that stands in for `CURRENT_ROLE()`, mirroring the shape of a Snowflake policy
`create masking policy email_mask as (val string) returns string -> case when current_role() in ('ANALYST_FULL')
then val else '***MASKED***' end;`. No Snowflake or Cortex call was made. The emails are fictional, derived from
the fictional user ids (`lower(user_id) || '@example.test'`); `seeds/users.csv` has no email column and no seed
was added. Real Snowflake adds details this does not model (policy on the view vs base table, ownership,
secondary roles, `IS_ROLE_IN_SESSION`).

**Snowflake semantics emulated (official docs, fetched 2026-10-12):**
[Understanding Column-level Security](https://docs.snowflake.com/en/user-guide/security-column-intro):
"... users with the custom ANALYST role) can only view the last four digits of a phone number and none of the social
security number, while customer support representatives (... users with the custom SUPPORT role) can view the
entire phone number and social security number for customer verification use cases." [Dynamic Data Masking](https://docs.snowflake.com/en/user-guide/security-column-ddm-intro):
"At query runtime, the masking policy is applied to the column at every location where the column appears."

**What the script checks (`check.sh`):**
1. `git archive HEAD` into a temp dir; the `users` seed is loaded in DuckDB;
2. the composed assistant query runs as `ANALYST_FULL` and as `ANALYST_RESTRICTED`; rows and exposed emails
   (values containing `@`) are counted, and three sample rows per role are printed;
3. both roles see the same row count; the broad role sees every email; the restricted role sees none;
4. on a copy where the policy returns the raw value for every role, the restricted role must go RED (emails > 0),
   so the restricted result cannot be a vacuous zero;
5. last line `NUMBERS: <exposed as ANALYST_FULL> <exposed as ANALYST_RESTRICTED>` (currently `NUMBERS: 164 0`).

**Result:** holds. Same assistant SQL: 164 emails as the broad role, 0 as the restricted role, 164 again for the
restricted role once the mask is removed.

**Run it:** `bash proofs/2026-10-12-role-reads-as-caller/check.sh` (needs `dbt-duckdb`; override with
`DBT="uvx --with dbt-duckdb --from dbt-core dbt"`). Fictional data only.
