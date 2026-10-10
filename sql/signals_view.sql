CREATE OR REPLACE VIEW signals AS
SELECT signal_id, account_id,
       CASE WHEN mentions_figma_make OR mentions_ai_prototyping THEN 'job_make' ELSE 'job_figma' END AS kind,
       COALESCE(published_on, updated_on) AS signal_date, url, title,
       COALESCE(is_synthetic, FALSE) AS is_synthetic
FROM job_posts
WHERE mentions_figma OR mentions_figma_make OR mentions_ai_prototyping
UNION ALL
SELECT signal_id, account_id, 'funding' AS kind, filed_on AS signal_date, url, round_label AS title, FALSE AS is_synthetic FROM funding
UNION ALL
SELECT signal_id, account_id, 'news_' || tag AS kind, seen_on AS signal_date, url, title, FALSE AS is_synthetic FROM news
UNION ALL
SELECT signal_id, account_id, 'hn' AS kind, created_on AS signal_date, url, title, FALSE AS is_synthetic FROM mentions;
