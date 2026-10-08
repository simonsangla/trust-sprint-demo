-- One row per website session.
select session_id, user_id, session_date, channel from {{ ref('sessions') }}
