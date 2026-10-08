-- Fails if a frozen answer was recorded for different question text than the pack now holds (stale freeze).
select p.question_id
from {{ ref('stg_question_pack') }} p
join {{ ref('stg_cortex_answers') }} a on a.question_id = p.question_id
where p.question <> a.question
