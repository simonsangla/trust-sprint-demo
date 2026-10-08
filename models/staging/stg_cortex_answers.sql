-- The frozen output of one live Cortex Analyst run. answer_value is the first relevant cell of the executed SQL.
select
    question_id,
    question,
    nullif(generated_sql, '')                    as generated_sql,
    nullif(answer_value, '')                     as answer_value,
    request_id,
    cast(run_ts as timestamp)                    as run_ts,
    analyst_text,
    nullif(execution_error, '')                  as execution_error,
    row_count
from {{ ref('cortex_answers') }}
