-- Fails if the expected_answer typed into question_pack disagrees with the value re-derived from the data.
select p.question_id, p.expected_answer, t.truth_value
from {{ ref('stg_question_pack') }} p
join {{ ref('fct_metric_truth') }} t on t.question_id = p.question_id
where case
        when try_cast(p.expected_answer as double) is not null and try_cast(t.truth_value as double) is not null
            then abs(try_cast(p.expected_answer as double) - try_cast(t.truth_value as double)) > p.tolerance
        else lower(p.expected_answer) <> lower(t.truth_value)
      end
