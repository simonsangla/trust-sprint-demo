-- The ground-truth question set. expect_refusal marks questions whose correct answer is "this is undefined".
select
    question_id, question, metric_key, date_from, date_to, channel,
    expected_answer, tolerance, owner, rederived_by, as_of, set_name, expect_refusal
from {{ ref('question_pack') }}
