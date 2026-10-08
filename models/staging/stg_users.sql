-- One row per registered user.
select user_id, signup_date, country, plan from {{ ref('users') }}
