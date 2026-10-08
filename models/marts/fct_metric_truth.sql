-- Independent re-derivation of every expected answer, straight from the staging tables.
-- One row per question. truth_value is text; truth_numeric is set when the answer is a number.
-- The ratio here DOES guard the zero denominator (nullif), which the semantic view deliberately does not.
with q as (select * from {{ ref('stg_question_pack') }}),

confirmed as (
    select b.booking_date, b.amount, b.booking_id, s.channel
    from {{ ref('stg_bookings') }} b
    join {{ ref('stg_sessions') }} s on s.session_id = b.session_id
    where b.is_confirmed
),

n_bookings as (
    select q.question_id, count(c.booking_id) as v
    from q left join confirmed c
      on c.booking_date between q.date_from and q.date_to and (q.channel is null or c.channel = q.channel)
    group by q.question_id
),
revenue as (
    select q.question_id, sum(c.amount) as v
    from q left join confirmed c
      on c.booking_date between q.date_from and q.date_to and (q.channel is null or c.channel = q.channel)
    group by q.question_id
),
n_sessions as (
    select q.question_id, count(s.session_id) as v
    from q left join {{ ref('stg_sessions') }} s
      on s.session_date between q.date_from and q.date_to and (q.channel is null or s.channel = q.channel)
    group by q.question_id
),
active as (
    select q.question_id, count(distinct s.user_id) as v
    from q left join {{ ref('stg_sessions') }} s
      on s.session_date between q.date_from and q.date_to and (q.channel is null or s.channel = q.channel)
    group by q.question_id
),
channel_revenue as (
    select q.question_id, c.channel, sum(c.amount) as v
    from q join confirmed c on c.booking_date between q.date_from and q.date_to
    where q.metric_key = 'top_channel_by_revenue'
    group by q.question_id, c.channel
),
top_channel as (
    select question_id, channel
    from (select question_id, channel, row_number() over (partition by question_id order by v desc) as rn from channel_revenue) t
    where rn = 1
),
paying as (
    select count(*) as v from {{ ref('stg_users') }} where plan <> 'free'
)

select
    q.question_id,
    q.metric_key,
    case q.metric_key
        when 'bookings'               then cast(nb.v as varchar)
        when 'revenue'                then cast(round(rv.v, 2) as varchar)
        when 'active_users'           then cast(au.v as varchar)
        when 'conversion_rate'        then coalesce(cast(round(nb.v * 1.0 / nullif(ns.v, 0), 4) as varchar), 'UNDEFINED')
        when 'top_channel_by_revenue' then tc.channel
        when 'avg_booking_value'      then cast(round(rv.v / nullif(nb.v, 0), 2) as varchar)
        when 'paying_customers'       then cast(p.v as varchar)
        else 'UNDEFINED'
    end as truth_value
from q
left join n_bookings nb on nb.question_id = q.question_id
left join revenue rv    on rv.question_id = q.question_id
left join n_sessions ns on ns.question_id = q.question_id
left join active au     on au.question_id = q.question_id
left join top_channel tc on tc.question_id = q.question_id
cross join paying p
