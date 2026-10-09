## What and why

<!-- One or two sentences. Link the issue. -->

## Checklist

Run `bash scripts/pre-pr.sh` before opening the PR. It is the same script CI runs, so green here means green there.

- [ ] `bash scripts/pre-pr.sh` exits 0 (pre-commit, `dbt build`, `proofs/run_all.sh`, docs regenerate + sanitize, `check_site_proofs.py`)
- [ ] If models, seeds or proofs changed: regenerated `site/index.html` is committed (`check_site_proofs.py` also guards the self-hosted Snowflake icon and the non-affiliation line)
- [ ] A new claim has `proofs/<date>-<slug>/{CLAIM.md,check.sh}` and an entry in `models/proofs/_proofs.yml`
- [ ] Optional: `bash scripts/pre-pr.sh --links` if the site's external links changed
- [ ] No secrets, no real client data (all data in this demo is fictional)
