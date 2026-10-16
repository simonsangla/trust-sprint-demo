-- Counts per failure_cause, plus the list of question ids behind each count.
select
    failure_cause,
    count(*) as n_questions,
    string_agg(question_id, ', ' order by question_id) as question_ids
from {{ ref('fct_question_verdicts') }}
group by failure_cause
