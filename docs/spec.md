# Spec: Usage Signals Agent (real public signals + warehouse-first scoring + cited sales handoffs)

Owner: Andy Dabinett · Author: Product Management Agent · Date: Oct 10, 2026 (v2: real public data) · Status: build-ready · Build budget: about 1 day (+ ~1 hour of manual seed curation)

This is for Kyle Ketchum's setup at Figma, and the outreach is for the Figma Marketing Engineer, AI Deployment role. It replaces the Marketing Cortex spec, which is now in `/workspace/outreach/_set-aside/`. Crusoe is out of scope.

**What changed in v2:**
- The accounts and public signals are **real** (public companies and public, dated signals).
- Seats and daily usage are a **labeled synthetic proxy**, seeded from those real signal dates.
- Ingest respects robots.txt and terms of service, and is cached in DuckDB. The demo runs fully offline from a committed snapshot.
- Handoffs are cited and contain no personal data.

## 0. Sources: what's verified and what isn't
| Claim | Source | Status |
|---|---|---|
| The posting's success metrics: "agents live … hours saved … revenue driven"; "Build custom tools, agents, automations, and integrations"; "Query data using SQL across warehouses like Snowflake or BigQuery" | [Figma, Marketing Engineer (Greenhouse 6013495004)](https://boards.greenhouse.io/figma/jobs/6013495004) | **Verified.** Fetched Oct 10, 2026; quotes are verbatim. |
| The hiring manager works "alongside Kyle Ketchum" to make marketing "disproportionately faster and more effective with AI" | [Andrew Mattock's hiring post](https://www.linkedin.com/posts/andrewmattock_marketing-engineer-activity-7470522766140608512-Ikg6) | Verified from a search snippet only. LinkedIn wasn't opened directly. |
| Kyle: "Salesforce for record-keeping, Snowflake for product data, and Clay for turning it all into automated action." Product signals such as "seat growth, feature adoption, and component usage patterns exist in Snowflake." Routing them into Salesforce "created bloat." Segments combine "product-qualified activity with tech stack data, funding signals, and hiring patterns" to find unowned accounts. | [Clay customer story: Figma](https://www.clay.com/customers/figma) | **Verified.** Fetched Oct 10, 2026; quotes are verbatim. |
| The shift "from 'get everything into Salesforce' to treating the data warehouse as the source of truth"; Figma has 9 products | [Anders Krohn recap](https://www.linkedin.com/posts/anderskrohn_it-was-great-to-speak-with-kyle-ketchum-about-activity-7450122552884019200-ecs5), [Confessions of a CRM (Spotify)](https://open.spotify.com/episode/2tSb5dugcpdDxy48eC5JQt) | **Partly verified:** the host's paraphrase, seen in a snippet; I didn't listen to the episode. The Clay story keeps Salesforce as the system of record and calls Clay "the source of truth for GTM orchestration," so the README says "warehouse-first." |
| The RevFest 2026 talk "The GTM Engine Nobody Asked For", on "where to start with a signal-based selling architecture" | [Mattock's post](https://www.linkedin.com/posts/andrewmattock_when-jen-igartua-first-asked-me-to-speak-activity-7459992646762151937-QXIL), [Jen Igartua's post](https://www.linkedin.com/feed/update/urn:li:activity:7459962740271443968), [ConferenceGrid](https://conferencegrid.com/events/revfest-2026) | Title and topic verified from snippets. **Content unverified** (no recording found). The date conflicts (May 21 in the posts vs May 1 on ConferenceGrid), so the README says only "RevFest 2026 (Brooklyn)." |
| Kyle's title "Staff GTM Engineer" | [ConfBase](https://www.confbase.com/speakers/kyle-ketchum) | Third-party only; the Clay story says "Marketing Operations." The README says "GTM engineering." |
| The Figma agent left beta Oct 6, 2026 | [Figma on X](https://x.com/figma/status/2107496188765524016) (via the research doc) | Not re-opened. Used as the GA date. |
| Figma's Acceptable Use Policy §j bans scraping and "otherwise access[ing] Figma or Figma content programmatically" without express permission | [figma.com/aup](https://www.figma.com/aup/) | **Verified** Oct 10, 2026. This drives D12. |

## 1. Goal
Build a small Python repo that copies Kyle's public pattern on **real public companies**:
- **Real public signals** go into a warehouse: hiring posts that mention Figma, Figma Make or AI prototyping; funding filings and news; and Figma customer stories. A DuckDB file stands in for Snowflake.
- **Public enrichment** in the style of Clay: size, industry, and funding.
- **A clearly labeled synthetic usage proxy**, seeded from the real signal dates, because no public seat or usage data exists.
- **A transparent, rules-only score** decides which accounts to flag. No LLM is involved in scoring.
- **A short LLM handoff** for each flagged account. Every claim cites a source URL, and the handoff contains no personal data.

Demo story: "The Figma agent went GA on Oct 6. Which real companies show public intent, and what would a rep say, with receipts?"

## 2. Decisions made (PM defaults)
| # | Decision |
|---|---|
| D1 | **Repo:** `andydabinett/usage-signals-agent`, **private**. Nothing is deployed. The optional web view is a static HTML file. |
| D2 | **Stack:** Python 3.12, uv, `duckdb`, `typer`, `pydantic`, `httpx`, `jinja2`, `selectolax` (HTML parsing), `sqlglot` (dev), `pytest`, and `respx` (HTTP mocks). `snowflake-connector-python` is an optional extra. |
| D3 | **Fixed `AS_OF`.** `AS_OF` = the snapshot date stored in `snapshot_meta` (the committed snapshot uses the date of the freeze run). It can be overridden with `--as-of`. Never use `CURRENT_DATE`. |
| D4 | **SQL dialect rule:** use only the Snowflake ∩ DuckDB subset. **Banned:** `DATEADD`, `date_add`, `INTERVAL`, `::`, `QUALIFY`, `ILIKE`, list or struct types, `CURRENT_DATE`, and DuckDB `$name` params. Params use pyformat `%(name)s`; the DuckDB adapter rewrites them. Raw JSON is stored as a `VARCHAR` column, and only Python parses it. |
| D5 | **Real company names are allowed** (replacing the old "no real names" rule). **No personal data:** no person names, emails, phone numbers or LinkedIn profile URLs are stored. Contacts are **public role titles only**, such as "Head of Design," each with its source URL. |
| D6 | **Scoring lives in SQL** (`sql/score_accounts.sql`), and weights and thresholds are in `config/scoring.yaml`. |
| D7 | **Handoff model:** `anthropic/claude-sonnet-5.5`, with `reasoning: {effort: "low"}`, `max_tokens: 2000` and a strict `json_schema`. Override with `HANDOFF_MODEL`. |
| D8 | **Grounding check in code:** every number in the handoff text must be in the facts allow-list. Every sentence of `why_this_account` and `why_now` must end with a `[n]` citation that maps to a `signal_id` in the facts. Any proxy-derived number must be labeled "(proxy)." On failure, retry once, then fall back to a template. |
| D9 | **Ownership:** the CRM owner is unknown for real companies, so `owner_rep` is always NULL and every handoff is addressed "For: PLG / unowned queue (demo)." |
| D10 | **Handoff cache:** handoffs are cached in the `handoffs` table and committed in the snapshot, so the offline demo needs no API key. |
| D11 | **One HTTP client for all ingest** (`signals/http.py`). It sets `User-Agent: usage-signals-agent/0.1 (+https://github.com/andydabinett/usage-signals-agent; $CONTACT_EMAIL)`, checks robots.txt with `urllib.robotparser` plus a wildcard-aware path check (stdlib doesn't handle `*`), and rate-limits per host (default 1 request/s; GDELT 1 per 5 s; SEC ≤ 5/s). It caches every response in `raw_pulls`, retries 429 and 5xx up to 3 times with backoff, and **never** spoofs a browser User-Agent or bypasses a 403. If robots disallows a URL, it's skipped and logged. |
| D12 | **No programmatic access to figma.com,** because of the [AUP §j](https://www.figma.com/aup/). Figma Community also returned **403** to an honest bot User-Agent. Figma customer stories are therefore a **hand-curated seed CSV**: a human reads public pages in a browser and records company, URL, title and products mentioned. Figma Community signals are **dropped from v1** (see §4). |
| D13 | **LinkedIn data only as search-result snippets pasted by a human** into `seeds/manual_snippets.csv` (URL, snippet text, date, query). No requests to linkedin.com of any kind. |
| D14 | **The account universe is the companies in the curated customer-story seed** (§5.1), about 20 accounts. They're real Figma customers by Figma's own public statement, which makes the "expansion signal" framing plausible. |
| D15 | **The snapshot is committed** as `snapshot/warehouse.duckdb`, plus `snapshot/expected.json` holding the flagged list, at-risk list and totals. Tests assert against it (§12). `signals refresh` rebuilds from live sources, and `signals freeze` rewrites `expected.json` after review. |

## 3. Feasibility check (done Oct 10, 2026)
| Source | robots.txt | Terms of service | Sample fetch | Verdict |
|---|---|---|---|---|
| figma.com customer stories (`/customers/`) | `User-agent: *` doesn't disallow `/customers/` (it disallows `/api/*` and `/community/search?*`; GPTBot and ClaudeBot are fully disallowed) | **AUP §j forbids programmatic access** | One page returned 200 and listed 117 story links | **Manual seed only** (D12). |
| Figma Community (files, plugins, Make) | Community sitemaps are published (for example, 18,179 plugin URLs) | AUP §j | **403 (CloudFront "Request blocked")** on a plugin page and `/community` with an honest User-Agent | **Blocked; dropped from v1.** Could be reconsidered only with explicit Figma permission or an official API. |
| Greenhouse job board API `boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` | Only `/embed/` disallowed | A public, documented job-board API | 200 for figma, datadog (435 jobs, 2 mention Figma, 0 mention Figma Make), carta and customerio. 404 for slugs that don't exist | **OK.** Board slugs are mapped by hand per company. |
| Lever `api.lever.co/v0/postings/{slug}?mode=json` | `jobs.lever.co` allows `/`, `Crawl-delay: 1` | Public postings API | 404 for an unknown slug (the API works; slugs need mapping) | **OK** with a hand-mapped slug. Respect a 1 s delay. |
| Ashby `api.ashbyhq.com/posting-api/job-board/{slug}` | `jobs.ashbyhq.com` disallows `/api/` on that host; the documented API is on `api.ashbyhq.com` | Public posting API | 200 (tested on another company's board) | **OK** through `api.ashbyhq.com` only. |
| SEC EDGAR full-text search (Form D funding) `efts.sec.gov/LATEST/search-index?q=…&forms=D` | — | SEC fair-access policy: a declared User-Agent **with an email**, ≤ 10 requests/s | **403 "Undeclared Automated Tool"** because the test User-Agent had no email | **OK once `CONTACT_EMAIL` is set** (blocker B1). Covers US private raises only. |
| GDELT DOC 2.0 API (news: funding, launches) | — | Free; "limit requests to one every 5 seconds" | Answered with a rate-limit notice after quick back-to-back calls | **OK at 1 request per 5 s.** |
| HN Algolia API `hn.algolia.com/api/v1/search_by_date` | — | Free public API | 200 with results for "Figma Make" | **OK** (low-weight mention signal). |
| Wikidata API and SPARQL (employees P1128, industry P452, website P856) | `/w/api.php` not disallowed | CC0 data | 200; entity search worked, but employee count was empty for the tested company | **OK.** Coverage is patchy, so the fallbacks in §5.5 apply. |
| Company websites (homepage `<meta>`, `/about`, `/careers`) | Checked per domain at runtime | Per site | Not sampled per company | **OK if robots allows it.** Fetch only 3 paths per domain. |
| Crunchbase | Disallows `/search`, `/discover`, `/v4`, etc. | The free account has no API; the Basic API needs a license | The pricing page shows no prices (a "Start Free Trial" CTA only) | **Not used.** Listed under paid options. |
| Apollo | Allows most paths | The pricing FAQ says "API access is available on Custom plans" and that data is for internal use only | — | **Not used** (no free API, and it's contact or personal data). |
| LinkedIn | — | Scraping is barred by their terms | Not fetched | **Manual snippets only** (D13). |
| Google News | Disallows `/` except the home and topics pages; AI bots are fully disallowed | — | — | **Not used** (GDELT replaces it). |

## 4. Real vs. proxy fields (also copied into the README)
| Field | Real or proxy | Source |
|---|---|---|
| account name, domain, Figma customer-story URL and title, products mentioned (Make, Dev Mode, AI, MCP) | **Real** | Hand-curated from [figma.com/customers](https://www.figma.com/customers/) (D12) |
| open roles; roles mentioning "Figma"; roles mentioning "Figma Make", "AI prototyping" or "vibe coding"; posting first-published and updated dates; role titles | **Real** | Greenhouse, Lever and Ashby public job APIs |
| hiring momentum (qualifying posts in the last 30 days vs. the prior 60) | **Real (derived), drives the flag** | Same job APIs |
| last funding date and amount (US) | **Real** | SEC EDGAR Form D |
| funding and launch news mentions | **Real** | GDELT DOC API |
| HN mentions of company + Figma | **Real** | HN Algolia |
| employee count, industry, HQ country, website | **Real** (Wikidata, else a manual snippet, else NULL) | Wikidata; `seeds/manual_snippets.csv` |
| contact role titles | **Real** (titles only) | Job-post hiring-manager titles if published, customer-story speaker titles from the manual seed, or manual snippets |
| paid seats, active seats, daily Make and agent events | **Synthetic stand-in, CONTEXT ONLY** (never affects flag, total or at-risk) | `signals/proxy.py`, seeded from real signal dates (§6) |
| Figma agent first-use date | **Synthetic stand-in, CONTEXT ONLY** | §6 |
| owner_rep | Always NULL | D9 |

## 5. Ingest modules (`signals/ingest/`, one per source)
Each module exposes `pull(wh, accounts, since) -> int`. It writes raw responses to `raw_pulls`, writes normalized rows to its own table, and is idempotent per `(source, url)`.

| # | Module | Endpoint or input | Fields pulled | Cadence |
|---|---|---|---|---|
| 5.1 | `figma_customers_seed` | `seeds/figma_customer_stories.csv` (hand-curated, committed) | company, domain, story_url, story_title, products_mentioned[], accessed_on | Manual, monthly |
| 5.2 | `jobs_greenhouse` | `GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` | id, title, location, updated_at, first_published (if present), absolute_url, a content excerpt (the 300 characters around each match), the match flags `mentions_figma`, `mentions_figma_make`, `mentions_ai_prototyping` | Daily |
| 5.3 | `jobs_lever` | `GET https://api.lever.co/v0/postings/{slug}?mode=json` | id, text (title), createdAt, hostedUrl, categories, the same match flags | Daily |
| 5.4 | `jobs_ashby` | `GET https://api.ashbyhq.com/posting-api/job-board/{slug}` | id, title, publishedAt, jobUrl, department, the same match flags | Daily |
| 5.5 | `enrich_wikidata` | `wbsearchentities`, then SPARQL for P1128 (employees), P452 (industry), P17 (country), P856 (website) | qid, employees, industry_label, country, website, retrieved_at | Weekly |
| 5.6 | `enrich_website` | `https://{domain}/`, `/about`, `/careers` (robots-checked) | `<title>`, meta description, og:site_name, and whether the careers page links to an ATS (used to auto-suggest an ATS slug for human review) | Weekly |
| 5.7 | `funding_edgar` | `GET https://efts.sec.gov/LATEST/search-index?q="{legal_name}"&forms=D&startdt={AS_OF-365d}&enddt={AS_OF}` | accession no., filing date, entity name, filing URL. An entity is accepted only if its normalized name matches the seed's `legal_name` exactly | Weekly |
| 5.8 | `news_gdelt` | `GET https://api.gdeltproject.org/api/v2/doc/doc?query="{company}" (funding OR raises OR launches OR layoffs)&mode=artlist&format=json&timespan=3months&maxrecords=25` | url, title, seendate, domain, and the tag matched (funding, launch or layoffs) by keyword | Daily (1 per 5 s) |
| 5.9 | `mentions_hn` | `GET https://hn.algolia.com/api/v1/search_by_date?query="{company}" figma&tags=story` | objectID, title, url, created_at, points | Daily |
| 5.10 | `manual_snippets` | `seeds/manual_snippets.csv` (columns: account_id, url, snippet, query, collected_on, kind ∈ {employees, role_title, funding, other}) | as given. The parser pulls employee ranges like "1,001-5,000 employees" for size | Manual |

**Board slugs** come from `seeds/ats_slugs.csv` (account_id, ats ∈ {greenhouse, lever, ashby, none}, slug, verified_on). They're mapped by hand, and 5.6 can suggest candidates.

**Match regexes** (case-insensitive, run on HTML-unescaped content):
- `figma_make`: `\bfigma make\b`
- `ai_prototyping`: `\bai[- ]prototyp|\bvibe[- ]coding\b`
- `figma`: `\bfigma\b`

**Initial seed:** `seeds/figma_customer_stories.csv`, 20 rows. These are real Figma customer stories whose titles I saw on [figma.com/customers](https://www.figma.com/customers/) on Oct 10, 2026, during the one-page feasibility fetch. The builder confirms each URL in a browser and fills in `products_mentioned` by reading the page.
- **Make or AI stories:** Saddle (`figma-make-helps-saddle-go-from-idea-to-launch-in-2-weeks`), Civica (`how-figma-make-accelerates-empowers-product-managers-at-civica`), Accor (`how-figma-make-helps-the-design-team-shape-decisions-at-accor`), Findable (`how-findable-moved-50-percent-faster-with-figma-make`), Carrefour (`how-carrefour-leveraged-ai-to-drive-design-delivery`), Grab (`how-grab-scales-hyperlocal-experiences-across-southeast-asia-with-figma-and-ai`), Insider One (`how-insider-one-customers-convert-designs-into-campaigns-instantly-with-figma-mcp`), Botim (`botim-ai-ready-design`)
- **Other stories:** Datadog, Carta, Customer.io, Plaid, Adyen, HelloFresh, King, Crunchyroll, ASOS, Headspace, Alaska Airlines, Amadeus. Their slugs are listed on the same index page.

## 6. Synthetic usage proxy (seeded from real signals)
All proxy tables carry `is_proxy=TRUE`, and the UI shows a "proxy" badge on every proxy-derived number. The proxy is deterministic, and `random.Random(20261006)` is used only for seat-id shuffles.

**Windows:** W0 = AS_OF−6 … AS_OF; W1 = AS_OF−13 … AS_OF−7; 8 weeks of history in total.

1. **Seats.** `paid_seats = clamp(round(employees × 0.02), 5, 400)`. If employees is NULL, use 20 and set `fit_unknown=TRUE`. Baseline active seats = `round(0.5 × paid_seats)`. Baseline weekly events = `active × 20`.
2. **Signal multipliers.** Each real dated signal adds a multiplier to the week containing its date, plus the following week at half strength:

   | Signal | Multiplier |
   |---|---|
   | job post mentioning Figma Make or AI prototyping | +0.60 |
   | job post mentioning Figma | +0.20 |
   | Form D filing or a GDELT funding article | +0.50 |
   | GDELT launch article | +0.20 |
   | HN mention | +0.10 |
   | GDELT layoffs article | −0.40 |

   Multipliers add up and are capped at +1.5 and floored at −0.6. Weekly events = baseline × (1 + multiplier).
3. **Hiring velocity.** If real hiring velocity (roles published in the last 14 days vs. the 14–28 days before) falls by 50% or more, and at least 4 roles were published 14–28 days ago, apply −0.30 to W0. This is the real basis for "decline."
4. **Active seats per week.** `round(baseline_active × (1 + 0.5 × multiplier))`, clamped to `[1, paid_seats]`.
5. **Agent usage.** This happens **only if** the account has real Make or AI evidence (the customer story mentions Make, AI or MCP, or a job post mentions `figma_make` or `ai_prototyping`). The proxy first-agent date is the later of the GA date (2026-10-06) and the first real Make/AI signal date on or after GA. If there's no signal on or after GA, use GA + 3 days. Agent seats in W0 = `ceil(0.25 × active_w0)`. Agent events = 10 × agent seats, and they count toward the weekly total.
6. **Distribution.** Days and seats are filled round-robin, as in Appendix A rule 3, so the sums are exact and the first agent `usage_date` equals the first-agent date.
7. **Lineage.** Every proxy week stores `driver_signal_ids` (a VARCHAR list of IDs, comma-joined), so `explain` can show which real signals created a spike.

## 7. Scoring (sql/score_accounts.sql; constants in config/scoring.yaml). v2, Oct 10 2026: real signals drive the flag

**v2 (Oct 10, 2026, Andy's decision): real public signals decide the flag.** Synthetic seats and usage are context only.
`sql/score_accounts.sql` reads every constant from `config/scoring.yaml`. These thresholds were set once, from first principles,
and committed together with this README section **before** v2 was run on live data. They are not tuned to hit a flag count.

**Flag = every gate passes:**

| Gate (all real) | Measure | Threshold | Why this number |
|---|---|---|---|
| AI/design hiring | open posts in the last 30 days that mention Figma, Figma Make, AI prototyping or vibe coding (matched in context), or design roles for AI agents (title has "design" and "agent") | **≥ 2** | One post can be a backfill, a recruiter template, or one team's habit. Two in a month is the smallest count that suggests a pattern rather than an accident. |
| Momentum | 30-day count vs. the prior-60-day monthly rate (prior 60 ÷ 2), with that rate floored at 1/month | **ratio ≥ 1.5** | "Now" has to beat the account's own baseline by a margin larger than normal month-to-month noise. With counts this small, +50% is the smallest lift that isn't one extra post. The floor stops 1-vs-0 from reading as infinite growth. |
| Company fit | employee count from Wikidata or `manual_public` (10-K, annual report, company page); snippets and estimates don't count | **≥ 200** | About where a company has a dedicated design org, several squads and procurement, so Figma Organization/Enterprise and agent rollout is a sales motion and not a self-serve Pro upgrade. Unknown counts fail: no fit without a source. No upper cap, because large companies buy too. |
| Recent cited signal | non-synthetic signals with a URL in the last 30 days | **≥ 1** | Every flag must have a dated, clickable reason a rep can open. |

**Points (0–100) only rank accounts.** They never decide the flag:
hiring 5/post (capped at 5 posts) plus 10 if any post is Make/AI/agent-design (max 35); momentum ratio ≥3 → 25, ≥2 → 18, ≥1.5 → 12;
fit 200–5,000 → 20, >5,000 → 15, 50–199 → 5; public intent: 5 per HN mention in 90 days (max 2) plus 10 for a Form D in 180 days (max 20).
Public intent is **not a gate**. HN and Form D coverage is sparse and depends on press attention, so gating on it would mostly measure
how famous a company is. Blog mentions have no ingest source yet.

**At risk (real, "cooling"):** ≥ 4 qualifying posts in the prior 60 days and 0 in the last 30.

**Context only (synthetic stand-ins, labeled everywhere):** usage growth WoW, seat breadth, agent adoption (the v1 point tables).
They're shown in `score`/`explain`/web and may appear in a handoff labeled "(synthetic stand-in)". They never enter total, flag or at-risk.
`tests/test_scoring_fixture.py::test_changing_synthetic_values_never_changes_flag_outcome` rewrites the synthetic usage and seats six ways and checks that
flags, at-risk and totals stay identical.

Every sub-score, its value and its threshold is printed by `signals score --all` and `signals explain <id>`, and shown on the web page.
`AS_OF` is the snapshot date in `snapshot_meta` (never `CURRENT_DATE`); override it with `--as-of`.
Known limitation: the post date is `COALESCE(first published, updated)`. Some boards only give an updated date, and a re-edited old post can look new.

**Unit fixture:** `tests/fixtures/synthetic_12.sql` (Appendix A) now tests only the context-only proxy math (growth/breadth/agent
tables unchanged). It has no real hiring, so under v2 nothing in it flags. Real-gate behavior is tested on the respx-mocked fixture warehouse.

## 8. Tables (sql/schema.sql; adds to v1)
- `raw_pulls(source, url, fetched_at, status, content_type, body VARCHAR, sha256)`. The body is capped at 2 MB, and **only responses allowed by robots** are stored.
- `accounts(account_id, account_name, legal_name, domain, story_url, story_title, products_mentioned VARCHAR, owner_rep)`
- `job_posts(account_id, ats, post_id, title, url, published_on, updated_on, mentions_figma, mentions_figma_make, mentions_ai_prototyping, excerpt)`
- `funding(account_id, source, filed_on, url, round_label, amount_usd)`
- `news(account_id, source, url, title, seen_on, tag)`
- `mentions(account_id, source, url, title, created_on, points)`
- `enrichment(account_id, employees, employees_source_url, industry, country, website, qid, retrieved_on)`
- `contacts(account_id, role_title, source_url)`. **There are no name or email columns.**
- `signals` is a view: a UNION of job_posts, funding, news and mentions with `signal_id, account_id, kind, signal_date, url, title`.
- Proxy tables: `seats(..., is_proxy)` and `usage_daily(..., is_proxy, driver_signal_ids)`.
- `handoffs`, `snapshot_meta(as_of, frozen_at, git_sha, source_counts VARCHAR)`.

## 9. Handoff (LLM, cited)
- **Facts JSON:** the score components (proxy values labeled), a list of up to 6 real signals (`signal_id`, kind, date, title, url), enrichment, the account's customer-story URL and title, and up to 2 role titles with their source URLs.
- **Output (strict schema):** `{addressed_to, why_this_account, why_now, who_to_contact:[{role_title, source_url, angle}] (1–2), suggested_first_line, citations:[{n, signal_id, url}], numbers_cited:[...]}`
- **Rules:**
  - ≤ 120 words.
  - Cite `[n]` on every factual sentence.
  - Label proxy numbers "(proxy)."
  - Never name individuals.
  - Never claim the account is a Figma customer beyond what its story URL shows.
- **The grounding check (D8) also verifies that:**
  - every `citations.url` is in the facts;
  - every `role_title` exists in `contacts`;
  - the text has no `@`, phone pattern or capitalized two-word person-name pattern next to a role. That last check is a heuristic that warns rather than fails.

## 10. Warehouse adapter
Unchanged from v1: the `Warehouse` protocol (`query`, `execute`, `load_rows`, `close`), the `DuckDBAdapter` (rewrites `%(name)s` to `$name`), and the `SnowflakeAdapter` stub (reads `SNOWFLAKE_*`, lazily imports the connector, and raises a clear `RuntimeError` if either is missing).

## 11. CLI (`uv run signals …`) and offline demo
| Command | Behavior |
|---|---|
| `refresh [--only SOURCE] [--since DATE]` | **Online.** Runs the §5 modules through the polite client, then rebuilds the proxy. Prints request counts per host, robots skips and errors. Requires `CONTACT_EMAIL`. |
| `freeze` | Copies `data/warehouse.duckdb` to `snapshot/warehouse.duckdb`, writes `snapshot/expected.json` (flagged, at_risk, totals, source_counts, as_of), and prints a diff against the previous version. |
| `score [--all] [--json]` | **Offline.** Defaults to `snapshot/warehouse.duckdb`. |
| `explain <account_id>` | Shows the components, real signals with URLs, the proxy lineage (which signals drove which weeks), and the flag-clause evaluation. |
| `handoff [<id>] [--refresh]` | Served from cache offline. `--refresh` needs `OPENROUTER_API_KEY`. |
| `web` | Writes `out/index.html`: flagged cards with breakdown bars (proxy segments hatched), cited handoffs, the at-risk list, a real-vs-proxy legend, and the snapshot date. |

**Demo script (3 minutes, fully offline):**
1. **0:00** README "Why this" and the real/proxy table.
2. **0:30** `signals score --all`: the flagged real companies, each with at least one real signal.
3. **1:10** `signals explain <top account>`: the job post mentioning Figma Make (URL), the funding filing (URL), and the proxy spike lining up with those dates.
4. **1:50** `signals handoff <top account>`: cited sentences, role titles only.
5. **2:20** `signals web`.
6. **2:40** The Snowflake adapter stub and the SQL dialect test.

## 12. README outline
1. Pitch and screenshot.
2. **Why this, for this role.**
3. The **real vs. proxy table** (§4).
4. Data ethics: robots.txt and terms respected; no figma.com or LinkedIn scraping; no personal data; the honest User-Agent and rate limits.
5. Quickstart, offline (snapshot).
6. Refreshing live data.
7. Scoring (§7).
8. Grounding.
9. Swapping in Snowflake.
10. Sources (§0, unverified items labeled).
11. Paid options.

**Draft: Why this, for this role** (updated)
> Figma's [Marketing Engineer, AI Deployment posting](https://boards.greenhouse.io/figma/jobs/6013495004) measures success by "agents live," "hours saved," and "revenue driven — pipeline, conversion lift, or deal velocity directly attributable to what you've built." This repo targets revenue driven, using the stack Kyle Ketchum has described publicly:
>
> - **Warehouse-first signals.** In the [Clay customer story](https://www.clay.com/customers/figma), product signals like "seat growth, feature adoption, and component usage patterns exist in Snowflake," and routing them into Salesforce "created bloat." The [Confessions of a CRM](https://open.spotify.com/episode/2tSb5dugcpdDxy48eC5JQt) host [summarized](https://www.linkedin.com/posts/anderskrohn_it-was-great-to-speak-with-kyle-ketchum-about-activity-7450122552884019200-ecs5) the shift as "treating the data warehouse as the source of truth." → All scoring is Snowflake-compatible SQL behind an adapter.
> - **Enrichment plus product activity.** Kyle combines "product-qualified activity with tech stack data, funding signals, and hiring patterns" ([Clay](https://www.clay.com/customers/figma)). → Real hiring posts that mention Figma Make or AI prototyping, real funding filings, and public firmographics, joined to a clearly labeled usage proxy where no public data exists.
> - **Signal-based selling.** The RevFest 2026 talk ["The GTM Engine Nobody Asked For"](https://www.linkedin.com/posts/andrewmattock_when-jen-igartua-first-asked-me-to-speak-activity-7459992646762151937-QXIL) was pitched at "where to start with a signal-based selling architecture." → Five explainable signals, a written-down flag rule, and an `explain` command with source links.
> - **Agents a team can trust.** The posting asks you to "Define evaluation criteria, instrument AI workflows." → Handoffs cite every claim, invent no numbers, and contain no personal data, all enforced in code.
>
> The accounts are real public companies that appear in Figma's own [customer stories](https://www.figma.com/customers/). Usage numbers are a synthetic proxy and are labeled that way everywhere.

## 13. Acceptance criteria
1. The repo `andydabinett/usage-signals-agent` exists and is **private**. Nothing is deployed.
2. `uv sync && uv run pytest` passes **with the network disabled** (a socket guard fixture blocks network access, and HTTP is mocked with respx).
3. **Snapshot assertion:** `score --json` on `snapshot/warehouse.duckdb` equals `snapshot/expected.json` exactly (flagged list in order, at_risk, totals).
4. Every account in `expected.json["flagged"]` has ≥ 1 real signal dated within 30 days of `as_of`, with a URL, and at least one of them is a job post or funding row. A test checks this.
5. **Unit fixture:** the synthetic 12-account math matches the §7 fixture table exactly (flagged `["A01","A09","A10","A02"]`, at risk `["A06","A07"]`). Changing one weight in `config/scoring.yaml` changes totals with no SQL edits.
6. `test_sql_dialect.py`: every `sql/*.sql` parses with `sqlglot` (`read="snowflake"`), and no banned token from D4 appears.
7. `SnowflakeAdapter()` raises the documented error without the env or extra. With a mocked connector, it passes SQL and params through unchanged.
8. **Polite client** (respx tests):
   - a robots-disallowed URL is never requested;
   - requests to the same host are spaced ≥ the configured delay;
   - the User-Agent contains the repo URL and `CONTACT_EMAIL`;
   - a 403 is recorded and not retried with different headers;
   - 429 triggers backoff.
9. **No figma.com or linkedin.com requests:** the client has a hard denylist (`*.figma.com`, `*.linkedin.com`), and a test asserts that a call raises an error.
10. Each ingest module, given a recorded fixture response, writes the expected normalized rows. Fixtures live in `tests/fixtures/http/`, one per module.
11. **Proxy:**
    - every `seats` and `usage_daily` row has `is_proxy=TRUE`;
    - weekly totals equal the §6 formula for 2 hand-computed fixture accounts;
    - agent usage exists only for accounts with real Make or AI evidence;
    - `driver_signal_ids` resolve to rows in `signals`.
12. **No personal data:**
    - no table has columns named like `name`, `email`, `phone` or `linkedin_url`, except `account_name`, `legal_name` and `role_title`;
    - a regex scan of the snapshot finds no email addresses other than in `raw_pulls` bodies, and there those are redacted before storage by an `[email]` replacement.
13. **Cached handoffs in the snapshot** pass the D8 and §9 checks:
    - every sentence is cited;
    - every URL is in the facts;
    - every number is in the allow-list;
    - proxy numbers are labeled.
    A unit test with an invented "35%" or an uncited sentence asserts it's rejected.
14. The offline demo commands (`score`, `explain`, `handoff`, `web`) complete with no `OPENROUTER_API_KEY` and no network.
15. `out/index.html` is self-contained, shows the snapshot date, and visually separates proxy from real.
16. `grep -r "sk-or-"` across the repo, snapshot and out finds nothing, and `.env` is gitignored.
17. The README contains the §4 table with a source per field, the §12 why-section with clickable links, and the paid options section.

## 14. Paid options (needs Andy's approval; none signed up for)
| Tool | Why it would help | Price (as shown on the pricing page) | Link | Checked |
|---|---|---|---|---|
| Brave Search API (Search) | Automated search-result snippets for LinkedIn company size and hiring, replacing manual `manual_snippets.csv` | **$5 per 1,000 requests**. The FAQ says a credit card is required "to subscribe to a free plan," and **storing results requires a plan with storage rights** (no price listed), which matters because this repo caches. | [brave.com/search/api](https://brave.com/search/api/) | Oct 10, 2026 |
| Crunchbase Pro / API | Global funding rounds (EDGAR is US-only) | **No price shown publicly.** The pricing page only offers "Start Free Trial," and the API needs a Basic or Enterprise license ([docs](https://data.crunchbase.com/docs/using-the-api)). | [about.crunchbase.com/pricing](https://about.crunchbase.com/pricing/) | Oct 10, 2026 |
| Apollo | Firmographics and titles | Free plan exists, but "API access is available on Custom plans" (no public price), and the data is for internal use only | [apollo.io/pricing](https://www.apollo.io/pricing) | Oct 10, 2026 |

## 15. Out of scope
Any figma.com scraping (including Community); any linkedin.com access; storing personal data; real Snowflake, Clay or Salesforce connections; CRM write-back; Slack alerts; ML weights; scheduled jobs (cadences are documented, not automated); deploying; making the repo public; outreach; Crusoe.

## 16. Blockers and verification notes
- **B1 — `CONTACT_EMAIL`:** SEC EDGAR returns 403 without an email in the User-Agent. Andy must choose the address to put in `.env` for `refresh`. The offline demo doesn't need it.
- **B2 — the snapshot needs one online `refresh` + review + `freeze`** before acceptance criterion 3 can pass. The expected flagged list **cannot be known until that run**; the builder commits it after a human reviews `explain` output for each flagged account.
- **Model:** `anthropic/claude-sonnet-5.5` is listed with `structured_outputs` on the [OpenRouter models API](https://openrouter.ai/api/v1/models) and was tested earlier today. One strict-schema handoff call returned valid JSON in 5.2 s for $0.005. **No new LLM calls were made for v2.** The key was never printed.
- The feasibility fetches were limited to a single robots.txt and sample page per source. The figma.com sample pages were fetched once each to check access, then the AUP was found. **The built tool must not fetch figma.com.**

## Appendix A: unit fixture `synthetic_12` (carried over from v1; used only for scoring-math tests, with AS_OF fixed at 2026-10-10)

**Windows** (with `AS_OF=2026-10-10`):
- W0 = 2026-10-04..2026-10-10 (the current week)
- W1 = 2026-09-27..2026-10-03 (the prior week)
- History = 6 earlier weeks, so data runs from 2026-08-16. Every "week" is 7 consecutive days ending on a Saturday.

**Random seed:** `random.Random(20261006)` is used **only** for names, emails, titles and contact order. **All usage numbers are deterministic** from the table below.

| id | name (synthetic) | case | plan | owner_rep | paid seats | active W0 | active W1 & history | events W1 & history (E1) | events W0 (E0) | agent seats W0 | first agent date | employees | industry | last funding |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A01 | Northwind Robotics | spike + agent GA | org | NULL | 40 | 31 | 20 | 400 | 970 | 12 | 2026-10-07 | 850 | Robotics | Series C, 2026-08-12 |
| A02 | Larkspur Health | spike + agent GA | org | NULL | 25 | 14 | 10 | 300 | 520 | 6 | 2026-10-06 | 400 | Healthtech | Series B, 2024-03-05 |
| A03 | Quillmate Pay | growth, thin breadth | org | NULL | 60 | 20 | 18 | 500 | 780 | 3 | 2026-10-08 | 1200 | Fintech | Series D, 2026-06-01 |
| A04 | Brightwave Media | steady, beta agent | pro | NULL | 30 | 20 | 20 | 600 | 630 | 4 | 2026-09-20 | 300 | Media | none |
| A05 | Copperline Logistics | steady | org | NULL | 50 | 32 | 32 | 900 | 880 | 0 | NULL | 2500 | Logistics | Series B, 2025-01-15 |
| A06 | Tidepool Games | decline | pro | NULL | 35 | 9 | 25 | 700 | 350 | 2 | 2026-09-15 | 180 | Gaming | none |
| A07 | Harbor & Pine Goods | decline | pro | NULL | 20 | 6 | 12 | 240 | 150 | 0 | NULL | 90 | Ecommerce | none |
| A08 | Orbitkind Studio | spike, poor fit | pro | NULL | 6 | 5 | 2 | 20 | 90 | 5 | 2026-10-06 | 25 | Agency | none |
| A09 | Meridian Trust Bank | spike, owned | enterprise | Dana Whitlock | 300 | 190 | 150 | 3000 | 6200 | 40 | 2026-10-06 | 12000 | Banking | none |
| A10 | Sproutlane Learning | new agent adopter | org | NULL | 15 | 6 | 5 | 100 | 135 | 6 | 2026-10-09 | 220 | Edtech | Series A, 2026-09-02 |
| A11 | Vantor Analytics | tiny decline (noise) | pro | NULL | 10 | 3 | 5 | 80 | 40 | 0 | NULL | 60 | Analytics | none |
| A12 | Kestrel Aero | steady, high fit, beta agent | enterprise | NULL | 45 | 25 | 25 | 800 | 840 | 8 | 2026-09-10 | 3000 | Aerospace | Series E, 2026-07-20 |

**Generation rules:**
1. **Seats.** Create `paid seats` paid editor seats with ids `{acct}-S{nnn}`, starting at 001, plus 3 unpaid viewer seats per account (these never have usage). In a given week, the active seats are the first `active` paid seats by id. Agent seats are the first `agent seats` of the active seats.
2. **Agent events.** In each week that is on or after the first agent date, agent events = 10 × agent seats. For beta accounts (A04, A06, A12), use the W0 agent-seat count for every week from the first agent date onward. The first partial week is still 10 × seats, spread only over the days from the first agent date. Agent events count toward E. Make events = E − agent events.
3. **Distribution.** Within a week and product, build cells = days (ascending; for agent, only days on or after the first agent date) × seats (ascending), ordered by day first. Then deal events one at a time, round-robin across the cells. This makes the sums exact, puts the first agent `usage_date` on the first agent date, and makes every listed seat active. The seeder must assert `events ≥ cells` for every week and product.
4. **Fields.** `minutes = events × 3`. Enrichment `enriched_at = 2026-10-09`.
5. **Contacts.** 3 per account: the personas are design_leader (the champion), eng_leader and product_leader, with names drawn from fixed first/last name lists using the seed. Email = `first.last@{domain}`, where the domain is `{slug}.example` (the reserved TLD, so no real domains are used).

