CREATE OR REPLACE VIEW signals AS
SELECT signal_id, account_id,
       CASE WHEN mentions_figma_make OR mentions_ai_prototyping THEN 'job_make'
            WHEN is_make_ai_agent THEN 'job_agent_design' ELSE 'job_figma' END AS kind,
       COALESCE(published_on, updated_on) AS signal_date, url, title,
       COALESCE(is_synthetic, FALSE) AS is_synthetic, COALESCE(date_basis, 'published') AS date_basis, dup_urls
FROM job_posts
WHERE qualifies AND dup_of IS NULL
UNION ALL
SELECT signal_id, account_id, 'funding' AS kind, filed_on AS signal_date, url, round_label AS title, FALSE AS is_synthetic, 'published' AS date_basis, CAST(NULL AS VARCHAR) AS dup_urls FROM funding
UNION ALL
SELECT signal_id, account_id, 'news_' || tag AS kind, seen_on AS signal_date, url, title, FALSE AS is_synthetic, 'published' AS date_basis, CAST(NULL AS VARCHAR) AS dup_urls FROM news
UNION ALL
SELECT signal_id, account_id, 'hn' AS kind, created_on AS signal_date, url, title, FALSE AS is_synthetic, 'published' AS date_basis, CAST(NULL AS VARCHAR) AS dup_urls FROM mentions;
