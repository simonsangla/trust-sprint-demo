-- Counts per verdict, plus the list of question ids behind each count.
select
    verdict,
    count(*)                                        as n_questions,
    string_agg(question_id, ', ' order by question_id) as question_ids
from {{ ref('fct_question_verdicts') }}
group by verdict
