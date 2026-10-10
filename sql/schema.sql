-- Snowflake ∩ DuckDB subset only (see tests/test_sql_dialect.py). Raw JSON lives in VARCHAR columns.
CREATE TABLE IF NOT EXISTS raw_pulls (source VARCHAR, url VARCHAR, fetched_at TIMESTAMP, status INTEGER, content_type VARCHAR, body VARCHAR, sha256 VARCHAR);
CREATE TABLE IF NOT EXISTS accounts (account_id VARCHAR, account_name VARCHAR, legal_name VARCHAR, domain VARCHAR, story_url VARCHAR, story_title VARCHAR, products_mentioned VARCHAR, owner_rep VARCHAR);
CREATE TABLE IF NOT EXISTS job_posts (signal_id VARCHAR, account_id VARCHAR, ats VARCHAR, post_id VARCHAR, title VARCHAR, url VARCHAR, published_on DATE, updated_on DATE, mentions_figma BOOLEAN, mentions_figma_make BOOLEAN, mentions_ai_prototyping BOOLEAN, excerpt VARCHAR);
CREATE TABLE IF NOT EXISTS funding (signal_id VARCHAR, account_id VARCHAR, source VARCHAR, filed_on DATE, url VARCHAR, round_label VARCHAR, amount_usd DOUBLE);
CREATE TABLE IF NOT EXISTS news (signal_id VARCHAR, account_id VARCHAR, source VARCHAR, url VARCHAR, title VARCHAR, seen_on DATE, tag VARCHAR);
CREATE TABLE IF NOT EXISTS mentions (signal_id VARCHAR, account_id VARCHAR, source VARCHAR, url VARCHAR, title VARCHAR, created_on DATE, points INTEGER);
CREATE TABLE IF NOT EXISTS enrichment (account_id VARCHAR, employees INTEGER, employees_source_url VARCHAR, industry VARCHAR, country VARCHAR, website VARCHAR, qid VARCHAR, retrieved_on DATE);
CREATE TABLE IF NOT EXISTS website_meta (account_id VARCHAR, url VARCHAR, page_title VARCHAR, meta_description VARCHAR, og_site VARCHAR, ats_hint VARCHAR, retrieved_on DATE);
CREATE TABLE IF NOT EXISTS manual_snippets (account_id VARCHAR, url VARCHAR, snippet VARCHAR, query VARCHAR, collected_on DATE, kind VARCHAR);
CREATE TABLE IF NOT EXISTS contacts (account_id VARCHAR, role_title VARCHAR, source_url VARCHAR);
CREATE TABLE IF NOT EXISTS seats (account_id VARCHAR, seat_id VARCHAR, seat_type VARCHAR, is_proxy BOOLEAN);
CREATE TABLE IF NOT EXISTS usage_daily (account_id VARCHAR, seat_id VARCHAR, usage_date DATE, product VARCHAR, events INTEGER, minutes INTEGER, is_proxy BOOLEAN, driver_signal_ids VARCHAR);
CREATE TABLE IF NOT EXISTS proxy_weeks (account_id VARCHAR, week_end DATE, multiplier DOUBLE, active_seats INTEGER, make_events INTEGER, agent_seats INTEGER, agent_events INTEGER, driver_signal_ids VARCHAR, is_proxy BOOLEAN);
CREATE TABLE IF NOT EXISTS handoffs (account_id VARCHAR, model VARCHAR, created_at TIMESTAMP, mode VARCHAR, facts_json VARCHAR, output_json VARCHAR, grounding_json VARCHAR, cost_usd DOUBLE);
CREATE TABLE IF NOT EXISTS snapshot_meta (as_of DATE, frozen_at TIMESTAMP, git_sha VARCHAR, source_counts VARCHAR);
