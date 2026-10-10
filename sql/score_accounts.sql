-- Rules-only score. All constants come from config/scoring.yaml as pyformat params; all dates are precomputed in Python
-- (no dialect-specific date math, so the same text runs on Snowflake and DuckDB).
WITH weekly AS (
  SELECT account_id,
         SUM(CASE WHEN usage_date >= %(w0_start)s AND usage_date <= %(as_of)s THEN events ELSE 0 END) AS e0,
         SUM(CASE WHEN usage_date >= %(w1_start)s AND usage_date <= %(w1_end)s THEN events ELSE 0 END) AS e1,
         COUNT(DISTINCT CASE WHEN usage_date >= %(w0_start)s AND usage_date <= %(as_of)s THEN seat_id END) AS active_w0,
         COUNT(DISTINCT CASE WHEN product = 'agent' AND usage_date >= %(w0_start)s AND usage_date <= %(as_of)s THEN seat_id END) AS agent_seats_w0,
         MIN(CASE WHEN product = 'agent' THEN usage_date END) AS first_agent_date
  FROM usage_daily
  WHERE usage_date <= %(as_of)s
  GROUP BY account_id
),
paid AS (
  SELECT account_id, COUNT(*) AS paid_seats FROM seats WHERE seat_type = 'paid' GROUP BY account_id
),
fund AS (
  SELECT account_id, MAX(filed_on) AS last_funding FROM funding WHERE filed_on <= %(as_of)s GROUP BY account_id
),
intent AS (
  SELECT account_id,
         SUM(CASE WHEN mentions_figma_make OR mentions_ai_prototyping THEN 1 ELSE 0 END) AS make_roles,
         SUM(CASE WHEN mentions_figma THEN 1 ELSE 0 END) AS figma_roles
  FROM job_posts
  WHERE COALESCE(published_on, updated_on) >= %(intent_start)s AND COALESCE(published_on, updated_on) <= %(as_of)s
  GROUP BY account_id
),
sig AS (
  SELECT account_id, COUNT(*) AS real_signals_30d
  FROM signals
  WHERE signal_date >= %(intent_start)s AND signal_date <= %(as_of)s AND url IS NOT NULL
  GROUP BY account_id
),
base AS (
  SELECT a.account_id, a.account_name,
         COALESCE(w.e0, 0) AS e0, COALESCE(w.e1, 0) AS e1,
         COALESCE(w.active_w0, 0) AS active_w0, COALESCE(p.paid_seats, 0) AS paid_seats,
         COALESCE(w.agent_seats_w0, 0) AS agent_seats_w0, w.first_agent_date,
         e.employees, f.last_funding,
         COALESCE(i.make_roles, 0) AS make_roles, COALESCE(i.figma_roles, 0) AS figma_roles,
         COALESCE(s.real_signals_30d, 0) AS real_signals_30d,
         (COALESCE(w.e0, 0) - COALESCE(w.e1, 0)) * 1.0 / GREATEST(COALESCE(w.e1, 0), 1) AS g,
         CASE WHEN COALESCE(p.paid_seats, 0) > 0 THEN COALESCE(w.active_w0, 0) * 1.0 / p.paid_seats ELSE 0 END AS b
  FROM accounts a
  LEFT JOIN weekly w ON w.account_id = a.account_id
  LEFT JOIN paid p ON p.account_id = a.account_id
  LEFT JOIN enrichment e ON e.account_id = a.account_id
  LEFT JOIN fund f ON f.account_id = a.account_id
  LEFT JOIN intent i ON i.account_id = a.account_id
  LEFT JOIN sig s ON s.account_id = a.account_id
),
pts AS (
  SELECT base.*,
         CASE WHEN g >= %(growth_t1)s THEN %(growth_p1)s WHEN g >= %(growth_t2)s THEN %(growth_p2)s
              WHEN g >= %(growth_t3)s THEN %(growth_p3)s ELSE 0 END AS growth_pts,
         CASE WHEN active_w0 < %(breadth_min_active)s THEN 0
              WHEN b >= %(breadth_t1)s THEN %(breadth_p1)s WHEN b >= %(breadth_t2)s THEN %(breadth_p2)s
              WHEN b >= %(breadth_t3)s THEN %(breadth_p3)s ELSE 0 END AS breadth_pts,
         CASE WHEN agent_seats_w0 >= %(agent_min_seats)s AND first_agent_date >= %(ga_date)s THEN %(agent_p_new)s
              WHEN agent_seats_w0 >= %(agent_min_seats)s THEN %(agent_p_seats)s
              WHEN agent_seats_w0 >= 1 THEN %(agent_p_some)s ELSE 0 END AS agent_pts,
         (CASE WHEN employees IS NULL THEN 0
               WHEN employees > %(fit_mid_hi)s THEN %(fit_p_large)s
               WHEN employees >= %(fit_mid_lo)s THEN %(fit_p_mid)s
               WHEN employees >= %(fit_small_lo)s THEN %(fit_p_small)s ELSE 0 END)
         + (CASE WHEN last_funding IS NOT NULL AND last_funding >= %(funding_cutoff)s THEN %(fit_p_funding)s ELSE 0 END) AS fit_pts,
         CASE WHEN make_roles >= 1 THEN %(intent_p_make)s WHEN figma_roles >= %(intent_min_figma)s THEN %(intent_p_figma2)s
              WHEN figma_roles >= 1 THEN %(intent_p_figma1)s ELSE 0 END AS intent_pts
  FROM base
)
SELECT account_id, account_name, e0, e1, g, active_w0, paid_seats, b, agent_seats_w0, first_agent_date,
       employees, last_funding, make_roles, figma_roles, real_signals_30d,
       growth_pts, breadth_pts, agent_pts, fit_pts, intent_pts,
       growth_pts + breadth_pts + agent_pts + fit_pts + intent_pts AS total,
       CASE WHEN growth_pts + breadth_pts + agent_pts + fit_pts + intent_pts >= %(flag_min_total)s
             AND growth_pts >= %(flag_min_growth)s AND fit_pts >= %(flag_min_fit)s
             AND real_signals_30d >= %(flag_min_real_signals)s THEN TRUE ELSE FALSE END AS flagged,
       CASE WHEN g <= %(at_risk_max_growth)s AND e1 >= %(at_risk_min_e1)s THEN TRUE ELSE FALSE END AS at_risk
FROM pts
ORDER BY total DESC, account_id;
