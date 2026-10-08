-- One verdict per business question: pass | fail | trust_warning, each with a reason.
--   pass          the answer matches the expected answer (or a refusal was the right answer) and the metric is safe
--   trust_warning the number may be right but the way it was produced should not be trusted;
--                 also an analyst clarification request on a metric the view does not define
--   fail          wrong value, no answer, an error, or an invented number for an undefined metric
with joined as (
    select
        q.question_id, q.question, q.metric_key, q.owner, q.set_name, q.expect_refusal,
        q.expected_answer, q.tolerance,
        t.truth_value,
        r.status as metric_status, r.has_zero_guard, r.note as registry_note,
        a.generated_sql, a.answer_value, a.request_id, a.run_ts, a.analyst_text, a.execution_error, a.row_count,
        try_cast(a.answer_value as double)  as got_num,
        try_cast(q.expected_answer as double) as exp_num
    from {{ ref('stg_question_pack') }} q
    left join {{ ref('stg_cortex_answers') }} a on a.question_id = q.question_id
    left join {{ ref('stg_metric_registry') }} r on r.metric_key = q.metric_key
    left join {{ ref('fct_metric_truth') }} t on t.question_id = q.question_id
),

judged as (
    select
        *,
        case
            when request_id is null then 'fail'
            when expect_refusal and generated_sql is null then 'pass'
            when expect_refusal and execution_error is not null then 'fail'
            when expect_refusal and answer_value is not null then 'fail'
            when expect_refusal then 'trust_warning'
            when generated_sql is null and execution_error is null and metric_status = 'not_in_view' then 'trust_warning'
            when generated_sql is null then 'fail'
            when execution_error is not null then 'fail'
            when answer_value is null then 'fail'
            when exp_num is not null and got_num is null then 'fail'
            when exp_num is not null and abs(got_num - exp_num) > tolerance then 'fail'
            when exp_num is null and lower(answer_value) <> lower(expected_answer) then 'fail'
            when metric_status = 'not_in_view' then 'trust_warning'
            when has_zero_guard = 'false' then 'trust_warning'
            else 'pass'
        end as verdict
    from joined
)

select
    question_id, question, metric_key, owner, set_name, expected_answer, answer_value, verdict,
    case
        when request_id is null then 'No Cortex answer recorded for this question.'
        when verdict = 'pass' and expect_refusal then 'Correct refusal: no SQL generated for a question the data cannot answer.'
        when verdict = 'pass' then 'Value matches the expected answer and the metric is governed by the semantic view.'
        when expect_refusal and execution_error is not null then 'Undefined question answered with SQL that errors: ' || execution_error
        when expect_refusal and answer_value is not null then 'Invented a value (' || answer_value || ') for a question the data cannot answer.'
        when expect_refusal then 'Empty result, with no statement that the metric is undefined for this slice.'
        when generated_sql is null and execution_error is null and metric_status = 'not_in_view'
            then 'Asked for clarification: ''' || replace(metric_key, '_', ' ') || ''' is not defined in the semantic view (expected '
                 || expected_answer || ' assumes ' || replace(split_part(split_part(registry_note, '; ', 2), ' is an', 1), '<>', chr(8800)) || ')'
        when generated_sql is null then 'No SQL generated, the analyst asked for clarification instead: ' || substr(analyst_text, 1, 160)
        when execution_error is not null then 'Generated SQL failed: ' || execution_error
        when answer_value is null then 'Generated SQL returned no rows.'
        when exp_num is not null and got_num is null then 'Answer is not a number: ' || answer_value
        when exp_num is not null and abs(got_num - exp_num) > tolerance
            then 'Value ' || cast(round(got_num, 4) as varchar) || ' differs from expected ' || expected_answer
                 || ' (tolerance ' || cast(tolerance as varchar) || ').'
        when exp_num is null and lower(answer_value) <> lower(expected_answer)
            then 'Answer ' || answer_value || ' differs from expected ' || expected_answer || '.'
        when metric_status = 'not_in_view' then 'Correct value, but ' || metric_key || ' is not defined in the semantic view: the analyst computed it ad hoc.'
        when has_zero_guard = 'false' then 'Correct value, but ' || metric_key || ' divides with no zero-guard.'
    end as reason,
    request_id, run_ts, generated_sql
from judged
