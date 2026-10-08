-- Fails if a question has no frozen Cortex answer, or more than one.
select p.question_id, count(a.question_id) as n_answers
from {{ ref('stg_question_pack') }} p
left join {{ ref('stg_cortex_answers') }} a on a.question_id = p.question_id
group by p.question_id
having count(a.question_id) <> 1
