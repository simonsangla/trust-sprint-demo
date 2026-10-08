# Refusal experiments E1-E3, 2026-10-08 (mission-os#1362)

Fictional data, DEV views, N=5 per cell, 70 Cortex Analyst calls. Raw: `push.csv` (text up to 400 chars, SQL up to 600 chars). Script: `push.py`.

**E1: which single verified query removes the churn refusal?**
| Only verified query | Churn |
|---|---|
| Q04 conversion June (governed metric) | declined 5/5 |
| Q05 conversion organic (governed metric) | declined 5/5 |
| Q06 partner conversion (hand-written ratio) | declined 5/5 |
| Q07 top channel by revenue (ORDER BY ... LIMIT 1) | 46.7% 5/5 |
| Q08 average booking value (hand-written ratio) | 46.7% 5/5 |
| Q09 paying customers (raw USERS table), earlier run | 46.7% 10/10 |
No simple rule explains it: Q06 and Q08 are both hand-written ratios, yet only Q08 flips.

**E2: other undefined metrics, base view vs ONLYQ09**
| Question | Base | ONLYQ09 |
|---|---|---|
| Customer lifetime value | declined 5/5 | 148.53 5/5 (own definition: revenue / users with a booking) |
| 90-day retention | declined 5/5 | 29% 2/5 and 72% 3/5 (two different self-made definitions) |
| NPS | declined 5/5 | declined 5/5 (no survey data at all) |

**E3: instruction "never invent a metric" + only Q09**
Churn: 5/5 runs **said in words that churn cannot be computed, and in the same runs returned SQL with a number**: 55.3% (free-plan share of users) 4/5, 11.2% (cancelled-booking share) 1/5.
With all 9 verified queries + the same instruction (earlier RULE run), the SQL returned the refusal text itself 10/10. The fix depends on the verified-query set.
