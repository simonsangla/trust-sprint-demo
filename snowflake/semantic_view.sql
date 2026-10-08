-- Semantic view for the Trust Sprint demo. Shape follows bricks/snowflake-cortex-semantic-view/emit.sql
-- (CONTRACT.md): IF NOT EXISTS only, never the destructive create-idiom, no standing-charge clause.
-- {{SCHEMA}} is substituted by scripts/snowflake_setup.py and scripts/promote.py.
--
-- verified: https://docs.snowflake.com/en/sql-reference/sql/create-semantic-view --
-- "CREATE [ OR REPLACE ] SEMANTIC VIEW [ IF NOT EXISTS ] <name> TABLES ( logicalTable [ , ... ] ) ..."
--
-- Governed metrics: bookings, revenue, active_users, session_count, conversion_rate.
-- NO churn metric exists on purpose: "What is our customer churn rate?" must be refused.
-- conversion_rate divides with NO zero-guard on purpose: a slice with no sessions is not protected.
CREATE SEMANTIC VIEW IF NOT EXISTS {{SCHEMA}}.TRUST_DEMO_SV
  TABLES (
    users AS {{SCHEMA}}.USERS
      PRIMARY KEY (user_id)
      COMMENT = 'One row per registered user. plan is free, pro or team.',
    sessions AS {{SCHEMA}}.SESSIONS
      PRIMARY KEY (session_id)
      COMMENT = 'One row per website session. channel is the acquisition channel.',
    bookings AS {{SCHEMA}}.BOOKINGS
      PRIMARY KEY (booking_id)
      COMMENT = 'One row per booking. status is confirmed or cancelled; only confirmed bookings count as bookings and revenue. amount is in EUR.'
  )
  RELATIONSHIPS (
    sessions_to_users AS sessions (user_id) REFERENCES users,
    bookings_to_users AS bookings (user_id) REFERENCES users,
    bookings_to_sessions AS bookings (session_id) REFERENCES sessions
  )
  DIMENSIONS (
    users.country AS country COMMENT = 'User country code',
    users.plan AS plan COMMENT = 'Subscription plan: free, pro or team',
    users.signup_date AS signup_date COMMENT = 'Date the user signed up',
    sessions.channel AS channel COMMENT = 'Acquisition channel of the session',
    sessions.session_date AS session_date COMMENT = 'Date of the session',
    bookings.booking_date AS booking_date COMMENT = 'Date of the booking',
    bookings.status AS status COMMENT = 'Booking status: confirmed or cancelled'
  )
  METRICS (
    bookings.bookings AS COUNT(CASE WHEN bookings.status = 'confirmed' THEN bookings.booking_id END)
      COMMENT = 'Number of confirmed bookings. Cancelled bookings are excluded.',
    bookings.revenue AS SUM(CASE WHEN bookings.status = 'confirmed' THEN bookings.amount END)
      COMMENT = 'Revenue in EUR: sum of the amount of confirmed bookings. Cancelled bookings are excluded.',
    sessions.session_count AS COUNT(sessions.session_id)
      COMMENT = 'Number of website sessions',
    sessions.active_users AS COUNT(DISTINCT sessions.user_id)
      COMMENT = 'Active users: distinct users with at least one session in the period',
    conversion_rate AS bookings.bookings / sessions.session_count
      COMMENT = 'Booking conversion rate: confirmed bookings divided by sessions'
  )
  COMMENT = 'Trust Sprint demo semantic view over fictional data. Governed metrics: bookings, revenue, active_users, session_count, conversion_rate. No churn metric is defined.';
