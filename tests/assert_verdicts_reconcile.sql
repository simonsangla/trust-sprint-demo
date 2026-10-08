-- Fails if the verdict summary does not add up to the number of questions.
select (select sum(n_questions) from {{ ref('fct_verdict_summary') }}) as in_summary,
       (select count(*) from {{ ref('stg_question_pack') }}) as in_pack
where (select sum(n_questions) from {{ ref('fct_verdict_summary') }}) <> (select count(*) from {{ ref('stg_question_pack') }})
