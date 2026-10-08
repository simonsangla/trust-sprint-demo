-- One row per booking. Only confirmed bookings count as bookings and revenue.
select
    booking_id,
    user_id,
    session_id,
    booking_date,
    cast(amount as decimal(12, 2))  as amount,
    status,
    status = 'confirmed'            as is_confirmed
from {{ ref('bookings') }}
