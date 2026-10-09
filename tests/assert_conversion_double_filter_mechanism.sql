-- Pins WHY Q04/Q05 failed, not just that they failed. Re-derives from the seeds, per question:
--   session_only : confirmed bookings / sessions, filtered on sessions.session_date alone  -> must equal the owner's expected_answer
--   both_filters : same ratio with BOTH sessions.session_date AND bookings.booking_date
--                  filters, as the analyst's generated_sql did (sessions LEFT JOIN bookings)   -> must equal the frozen analyst answer
-- and the denominator must collapse (sessions without a booking drop out) while the numerator is unchanged.
-- Returns a row on any violation. Mutation-tested: change a tolerance/value and it goes red.
with q as (
    select question_id, date_from, date_to, channel, cast(expected_answer as double) as expected, tolerance
    from {{ ref('stg_question_pack') }}
    where question_id in ('Q04', 'Q05')
),
joined as (
    select q.question_id, s.session_id, b.booking_id, b.is_confirmed, b.booking_date, s.session_date
    from q
    join {{ ref('stg_sessions') }} s
      on s.session_date between q.date_from and q.date_to and (q.channel is null or s.channel = q.channel)
    left join {{ ref('stg_bookings') }} b on b.session_id = s.session_id
),
derived as (
    select
        j.question_id,
        count(distinct j.session_id)                                                         as sessions_session_only,
        count(distinct case when j.booking_date between q.date_from and q.date_to
                            then j.session_id end)                                           as sessions_both_filters,
        count(case when j.is_confirmed then j.booking_id end)                                as bookings_session_only,
        count(case when j.is_confirmed and j.booking_date between q.date_from and q.date_to
                   then j.booking_id end)                                                    as bookings_both_filters
    from joined j join q on q.question_id = j.question_id
    group by j.question_id
)
select d.question_id, d.sessions_session_only, d.sessions_both_filters, d.bookings_session_only, d.bookings_both_filters,
       a.answer_value, q.expected
from derived d
join q on q.question_id = d.question_id
join {{ ref('stg_cortex_answers') }} a on a.question_id = d.question_id
where
    -- (a) session filter alone reproduces the owner's number
    abs(d.bookings_session_only * 1.0 / d.sessions_session_only - q.expected) > q.tolerance
    -- (b) both filters reproduce the analyst's frozen number
    or abs(d.bookings_both_filters * 1.0 / d.sessions_both_filters - cast(a.answer_value as double)) > 0.000001
    -- mechanism: denominator collapses, numerator does not
    or d.sessions_both_filters >= d.sessions_session_only
    or d.bookings_both_filters <> d.bookings_session_only
