-- Scoring v2: REAL public signals drive the flag (gates); synthetic seats/usage are CONTEXT ONLY and never enter
-- total, flagged or cooling. All constants come from config/scoring.yaml; all dates are precomputed in Python
-- (no dialect-specific date math, so the same text runs on Snowflake and DuckDB).
WITH posts AS (
  SELECT account_id, COALESCE(is_synthetic, FALSE) AS is_synthetic, url,
         COALESCE(published_on, updated_on) AS d,
         CASE WHEN mentions_figma_make OR mentions_ai_prototyping
                   OR (LOWER(title) LIKE '%design%' AND LOWER(title) LIKE '%agent%') THEN 1 ELSE 0 END AS is_make,
         CASE WHEN mentions_figma OR mentions_figma_make OR mentions_ai_prototyping
                   OR (LOWER(title) LIKE '%design%' AND LOWER(title) LIKE '%agent%') THEN 1 ELSE 0 END AS qual
  FROM job_posts
),
hire AS (
  SELECT account_id,
         SUM(CASE WHEN qual = 1 AND d > %(win_start)s AND d <= %(as_of)s THEN 1 ELSE 0 END) AS hire_30d,
         SUM(CASE WHEN is_make = 1 AND d > %(win_start)s AND d <= %(as_of)s THEN 1 ELSE 0 END) AS hire_make_30d,
         SUM(CASE WHEN qual = 1 AND d > %(prior_start)s AND d <= %(win_start)s THEN 1 ELSE 0 END) AS hire_prior60
  FROM posts GROUP BY account_id
),
recent AS (
  SELECT account_id, COUNT(*) AS real_signals_30d, MAX(signal_date) AS latest_real_signal
  FROM signals
  WHERE signal_date > %(win_start)s AND signal_date <= %(as_of)s AND url IS NOT NULL AND NOT is_synthetic
  GROUP BY account_id
),
hn AS (
  SELECT account_id, COUNT(*) AS hn_90d FROM mentions
  WHERE created_on > %(intent_start)s AND created_on <= %(as_of)s AND url IS NOT NULL GROUP BY account_id
),
fund AS (
  SELECT account_id, MAX(filed_on) AS last_funding FROM funding WHERE filed_on <= %(as_of)s GROUP BY account_id
),
weekly AS (
  SELECT account_id,
         SUM(CASE WHEN usage_date >= %(w0_start)s AND usage_date <= %(as_of)s THEN events ELSE 0 END) AS e0,
         SUM(CASE WHEN usage_date >= %(w1_start)s AND usage_date <= %(w1_end)s THEN events ELSE 0 END) AS e1,
         COUNT(DISTINCT CASE WHEN usage_date >= %(w0_start)s AND usage_date <= %(as_of)s THEN seat_id END) AS active_w0,
         COUNT(DISTINCT CASE WHEN product = 'agent' AND usage_date >= %(w0_start)s AND usage_date <= %(as_of)s THEN seat_id END) AS agent_seats_w0,
         MIN(CASE WHEN product = 'agent' THEN usage_date END) AS first_agent_date
  FROM usage_daily WHERE usage_date <= %(as_of)s GROUP BY account_id
),
paid AS (SELECT account_id, COUNT(*) AS paid_seats FROM seats WHERE seat_type = 'paid' GROUP BY account_id),
base AS (
  SELECT a.account_id, a.account_name,
         CASE WHEN e.employees_source IN ('wikidata', 'manual_public') THEN e.employees END AS employees,
         e.employees_source, f.last_funding,
         COALESCE(h.hire_30d, 0) AS hire_30d, COALESCE(h.hire_make_30d, 0) AS hire_make_30d,
         COALESCE(h.hire_prior60, 0) AS hire_prior60,
         COALESCE(h.hire_prior60, 0) * 1.0 / %(prior_months)s AS baseline_30d,
         COALESCE(h.hire_30d, 0) * 1.0 / GREATEST(COALESCE(h.hire_prior60, 0) * 1.0 / %(prior_months)s, %(gate_momentum_floor)s) AS momentum_ratio,
         COALESCE(r.real_signals_30d, 0) AS real_signals_30d, r.latest_real_signal,
         COALESCE(n.hn_90d, 0) AS hn_90d,
         CASE WHEN f.last_funding IS NOT NULL AND f.last_funding >= %(funding_cutoff)s THEN 1 ELSE 0 END AS formd_180d,
         COALESCE(w.e0, 0) AS e0, COALESCE(w.e1, 0) AS e1,
         COALESCE(w.active_w0, 0) AS active_w0, COALESCE(p.paid_seats, 0) AS paid_seats,
         COALESCE(w.agent_seats_w0, 0) AS agent_seats_w0, w.first_agent_date,
         (COALESCE(w.e0, 0) - COALESCE(w.e1, 0)) * 1.0 / GREATEST(COALESCE(w.e1, 0), 1) AS g,
         CASE WHEN COALESCE(p.paid_seats, 0) > 0 THEN COALESCE(w.active_w0, 0) * 1.0 / p.paid_seats ELSE 0 END AS b
  FROM accounts a
  LEFT JOIN enrichment e ON e.account_id = a.account_id
  LEFT JOIN fund f ON f.account_id = a.account_id
  LEFT JOIN hire h ON h.account_id = a.account_id
  LEFT JOIN recent r ON r.account_id = a.account_id
  LEFT JOIN hn n ON n.account_id = a.account_id
  LEFT JOIN weekly w ON w.account_id = a.account_id
  LEFT JOIN paid p ON p.account_id = a.account_id
),
pts AS (
  SELECT base.*,
         LEAST(hire_30d, %(hiring_post_cap)s) * %(hiring_per_post)s
           + CASE WHEN hire_make_30d >= 1 THEN %(hiring_make_bonus)s ELSE 0 END AS hiring_pts,
         CASE WHEN hire_30d = 0 THEN 0
              WHEN momentum_ratio >= %(momentum_t1)s THEN %(momentum_p1)s WHEN momentum_ratio >= %(momentum_t2)s THEN %(momentum_p2)s
              WHEN momentum_ratio >= %(momentum_t3)s THEN %(momentum_p3)s ELSE 0 END AS momentum_pts,
         CASE WHEN employees IS NULL THEN 0 WHEN employees > %(fit_mid_hi)s THEN %(fit_p_large)s
              WHEN employees >= %(fit_mid_lo)s THEN %(fit_p_mid)s WHEN employees >= %(fit_small_lo)s THEN %(fit_p_small)s
              ELSE 0 END AS fit_pts,
         LEAST(hn_90d, %(intent_hn_cap)s) * %(intent_hn_each)s + formd_180d * %(intent_p_formd)s AS intent_pts,
         CASE WHEN hire_30d >= %(gate_min_hiring_30d)s THEN TRUE ELSE FALSE END AS gate_hiring,
         CASE WHEN hire_30d >= 1 AND momentum_ratio >= %(gate_min_momentum_ratio)s THEN TRUE ELSE FALSE END AS gate_momentum,
         CASE WHEN employees IS NOT NULL AND employees >= %(gate_min_employees)s THEN TRUE ELSE FALSE END AS gate_fit,
         CASE WHEN real_signals_30d >= %(gate_min_recent_real_cited)s THEN TRUE ELSE FALSE END AS gate_recent,
         -- CONTEXT ONLY (synthetic stand-ins)
         CASE WHEN g >= %(growth_t1)s THEN %(growth_p1)s WHEN g >= %(growth_t2)s THEN %(growth_p2)s
              WHEN g >= %(growth_t3)s THEN %(growth_p3)s ELSE 0 END AS growth_pts,
         CASE WHEN active_w0 < %(breadth_min_active)s THEN 0 WHEN b >= %(breadth_t1)s THEN %(breadth_p1)s
              WHEN b >= %(breadth_t2)s THEN %(breadth_p2)s WHEN b >= %(breadth_t3)s THEN %(breadth_p3)s ELSE 0 END AS breadth_pts,
         CASE WHEN agent_seats_w0 >= %(agent_min_seats)s AND first_agent_date >= %(ga_date)s THEN %(agent_p_new)s
              WHEN agent_seats_w0 >= %(agent_min_seats)s THEN %(agent_p_seats)s
              WHEN agent_seats_w0 >= 1 THEN %(agent_p_some)s ELSE 0 END AS agent_pts
  FROM base
)
SELECT pts.*,
       hiring_pts + momentum_pts + fit_pts + intent_pts AS total,
       CASE WHEN gate_hiring AND gate_momentum AND gate_fit AND gate_recent THEN TRUE ELSE FALSE END AS flagged,
       CASE WHEN hire_prior60 >= %(cooling_min_prior60)s AND hire_30d <= %(cooling_max_30d)s THEN TRUE ELSE FALSE END AS at_risk
FROM pts
ORDER BY flagged DESC, total DESC, account_id;
