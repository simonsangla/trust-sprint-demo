-- Fails if a "pass" verdict was given to a metric the semantic view does not govern, or to an unguarded ratio.
select v.question_id, v.metric_key
from {{ ref('fct_question_verdicts') }} v
join {{ ref('stg_metric_registry') }} r on r.metric_key = v.metric_key
where v.verdict = 'pass'
  and not (r.status = 'governed' and r.has_zero_guard <> 'false' or r.status = 'undefined')
