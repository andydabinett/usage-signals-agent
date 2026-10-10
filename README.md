# Usage Signals Agent

Real public signals → warehouse-first, rules-only scoring → short **cited** sales handoffs, on **real public companies**
that appear in Figma's own customer stories. Seats and usage are a **clearly labeled synthetic proxy** (no public usage data exists).

> Demo story: *"The Figma agent went GA on Oct 6. Which real companies show public intent, and what would a rep say, with receipts?"*

**Status:** private repo, nothing deployed. The offline snapshot (`snapshot/`) is **pending**: it is frozen only after a human reviews
the live pull (`signals explain` for every flagged account). Until then, run the demo with `--db data/warehouse.duckdb`.

## Why this, for this role

Figma's [Marketing Engineer, AI Deployment posting](https://boards.greenhouse.io/figma/jobs/6013495004) measures success by "agents live," "hours saved," and "revenue driven — pipeline, conversion lift, or deal velocity directly attributable to what you've built." This repo targets revenue driven, using the stack Kyle Ketchum has described publicly:

- **Warehouse-first signals.** In the [Clay customer story](https://www.clay.com/customers/figma), product signals like "seat growth, feature adoption, and component usage patterns exist in Snowflake," and routing them into Salesforce "created bloat." The [Confessions of a CRM](https://open.spotify.com/episode/2tSb5dugcpdDxy48eC5JQt) host [summarized](https://www.linkedin.com/posts/anderskrohn_it-was-great-to-speak-with-kyle-ketchum-about-activity-7450122552884019200-ecs5) the shift as "treating the data warehouse as the source of truth." → All scoring is Snowflake-compatible SQL behind an adapter.
- **Enrichment plus product activity.** Kyle combines "product-qualified activity with tech stack data, funding signals, and hiring patterns" ([Clay](https://www.clay.com/customers/figma)). → Real hiring posts that mention Figma Make or AI prototyping, real funding filings, and public firmographics, joined to a clearly labeled usage proxy where no public data exists.
- **Signal-based selling.** The RevFest 2026 talk ["The GTM Engine Nobody Asked For"](https://www.linkedin.com/posts/andrewmattock_when-jen-igartua-first-asked-me-to-speak-activity-7459992646762151937-QXIL) was pitched at "where to start with a signal-based selling architecture." → Five explainable signals, a written-down flag rule, and an `explain` command with source links.
- **Agents a team can trust.** The posting asks you to "Define evaluation criteria, instrument AI workflows." → Handoffs cite every claim, invent no numbers, and contain no personal data, all enforced in code.

The accounts are real public companies that appear in Figma's own [customer stories](https://www.figma.com/customers/). Usage numbers are a synthetic proxy and are labeled that way everywhere.

## Real vs. proxy

| Field | Real or proxy | Source |
|---|---|---|
| account name, domain, Figma customer-story URL and title, products mentioned (Make, Dev Mode, AI, MCP) | **Real** | Hand-curated `seeds/figma_customer_stories.csv` from [figma.com/customers](https://www.figma.com/customers/) — never fetched by code |
| open roles; roles mentioning "Figma" / "Figma Make" / "AI prototyping" / "vibe coding"; posting dates; role titles | **Real** | [Greenhouse](https://developers.greenhouse.io/job-board.html), [Lever](https://github.com/lever/postings-api), [Ashby](https://developers.ashbyhq.com/docs/public-job-posting-api) public job APIs |
| hiring velocity (roles published last 14 days vs. the 14–28 days before) | **Real (derived)** | Same job APIs |
| last funding date (US) | **Real** | [SEC EDGAR](https://efts.sec.gov/LATEST/search-index) Form D full-text search |
| funding and launch news mentions | **Real** | [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) |
| HN mentions of company + Figma | **Real** | [HN Algolia API](https://hn.algolia.com/api) |
| employee count, industry, HQ country, website | **Real** (Wikidata, else a manual snippet, else NULL) | [Wikidata](https://www.wikidata.org/) API + SPARQL; `seeds/manual_snippets.csv` |
| contact role titles | **Real** (titles only) | Customer-story speaker titles (`seeds/story_contacts.csv`), manual snippets, or "Hiring team for: <role>" from the account's own job post |
| paid seats, active seats, daily Make and agent events | **Synthetic proxy** | `signals/proxy.py`, seeded from real signal dates |
| Figma agent first-use date | **Synthetic proxy** (gated by real Make/AI evidence) | `signals/proxy.py` |
| owner_rep | Always NULL | CRM owner unknown for real companies → every handoff goes to "PLG / unowned queue (demo)" |

## Data ethics

- **robots.txt and terms respected.** One polite client (`signals/http.py`) checks robots.txt (stdlib parser + wildcard-aware matcher),
  rate-limits per host (1 req/s default, GDELT 1 per 5 s, SEC ≤ 5/s, robots Crawl-delay honoured), retries 429/5xx with backoff,
  records 403s and **never** retries them with different headers.
- **Honest User-Agent:** `usage-signals-agent/0.1 (+https://github.com/andydabinett/usage-signals-agent; $CONTACT_EMAIL)`. No browser spoofing.
- **No figma.com access by code** ([AUP §j](https://www.figma.com/aup/)) and **no linkedin.com access** of any kind. Both are on a hard
  denylist that raises before any I/O (including redirects). Figma Community signals are dropped from v1.
- **No personal data.** No person names, emails, phones or profile URLs are stored; emails inside raw API bodies are redacted to `[email]`.

## Quickstart (offline)

```bash
uv sync
uv run pytest                        # network disabled by a socket guard; HTTP mocked with respx
uv run signals score --all           # default: snapshot/warehouse.duckdb (pending freeze; use --db data/warehouse.duckdb)
uv run signals explain <account_id>
uv run signals handoff <account_id>  # served from the cached `handoffs` table, no API key needed
uv run signals web                   # writes out/index.html (self-contained)
```

## Refreshing live data

```bash
cp .env.example .env   # set CONTACT_EMAIL (SEC fair-access policy); OPENROUTER_API_KEY only for handoff --refresh
set -a; . ./.env; set +a
uv run signals refresh                                    # -> data/warehouse.duckdb, prints per-host counts, robots skips, errors
uv run signals handoff --refresh --db data/warehouse.duckdb
# human review of `signals explain` for every flagged account, then:
uv run signals freeze                                     # -> snapshot/warehouse.duckdb + snapshot/expected.json
```

Cadences (documented, not scheduled): job boards / GDELT / HN daily; Wikidata, websites, EDGAR weekly; seeds monthly.

## Scoring

`sql/score_accounts.sql`, constants in `config/scoring.yaml` (change a weight → totals change, no SQL edit). Max 100:

| Component | Inputs | Points | Max |
|---|---|---|---|
| Usage growth WoW (proxy) | g = (E0 − E1) / max(E1, 1) | ≥1.00 → 25 · ≥0.50 → 18 · ≥0.20 → 10 | 25 |
| Seat breadth (proxy) | active_w0 / paid_seats | 0 if active < 5; ≥0.60 → 20 · ≥0.40 → 12 · ≥0.20 → 4 | 20 |
| Agent adoption newness (proxy, gated by real evidence) | agent seats W0, first agent date vs GA (2026-10-06) | ≥5 & new → 20 · ≥5 → 12 · 1–4 → 4 | 20 |
| Fit (real) | employees, last funding | 200–5,000 → 10 · >5,000 → 8 · 50–199 → 5; +10 if funded in last 180 days | 20 |
| Public intent (real) | job posts in last 30 days | ≥1 Make/AI role → 15 · ≥2 Figma roles → 8 · 1 → 4 | 15 |

**Flag:** `total ≥ 55 AND growth ≥ 10 AND fit ≥ 5 AND real_signals_30d ≥ 1`. **At risk:** `g ≤ −0.30 AND E1 ≥ 100`.
`AS_OF` is the snapshot date in `snapshot_meta` (never `CURRENT_DATE`); override with `--as-of`.

## Grounding

Handoffs (`anthropic/claude-sonnet-5.5`, strict JSON schema, `reasoning.effort=low`, override with `HANDOFF_MODEL`) are checked in code:
every sentence of *why this account* / *why now* ends with `[n]` mapping to a `signal_id` in the facts; every citation URL is in the facts;
every number is in the facts allow-list; proxy numbers carry "(proxy)"; role titles exist in `contacts`; no `@`/phone patterns (a
person-name heuristic warns). On failure: retry once with the errors, then fall back to a deterministic template.

## Swapping in Snowflake

All SQL is the Snowflake ∩ DuckDB subset (`tests/test_sql_dialect.py` parses each file with `sqlglot` as Snowflake and bans
`DATEADD`, `INTERVAL`, `::`, `QUALIFY`, `ILIKE`, `CURRENT_DATE`, `$name`, list/struct types). Params are pyformat `%(name)s`;
`DuckDBAdapter` rewrites them, `SnowflakeAdapter` (`uv sync --extra snowflake`, `SNOWFLAKE_*` env) passes them through unchanged.

## Sources

| Claim | Source | Status |
|---|---|---|
| Posting success metrics and SQL/warehouse requirement | [Figma Marketing Engineer posting](https://boards.greenhouse.io/figma/jobs/6013495004) | Verified Oct 10, 2026 |
| Salesforce / Snowflake / Clay stack, "created bloat", segment recipe | [Clay customer story: Figma](https://www.clay.com/customers/figma) | Verified Oct 10, 2026 |
| Hiring manager works alongside Kyle Ketchum | [Andrew Mattock's post](https://www.linkedin.com/posts/andrewmattock_marketing-engineer-activity-7470522766140608512-Ikg6) | *Unverified: search snippet only* |
| "Warehouse as the source of truth" | [Anders Krohn recap](https://www.linkedin.com/posts/anderskrohn_it-was-great-to-speak-with-kyle-ketchum-about-activity-7450122552884019200-ecs5), [podcast](https://open.spotify.com/episode/2tSb5dugcpdDxy48eC5JQt) | *Partly verified: host paraphrase* |
| RevFest 2026 (Brooklyn) talk title/topic | [Mattock's post](https://www.linkedin.com/posts/andrewmattock_when-jen-igartua-first-asked-me-to-speak-activity-7459992646762151937-QXIL), [ConferenceGrid](https://conferencegrid.com/events/revfest-2026) | *Title/topic from snippets; content unverified* |
| Figma agent GA Oct 6, 2026 | [Figma on X](https://x.com/figma/status/2107496188765524016) | *Not re-opened* |
| Figma AUP §j (no programmatic access) | [figma.com/aup](https://www.figma.com/aup/) | Verified Oct 10, 2026 |

## Paid options

None signed up for; each needs Andy's approval.

| Tool | Why it would help | Price (as shown) | Link | Checked |
|---|---|---|---|---|
| Brave Search API | Automate the manual LinkedIn/search snippets | $5 per 1,000 requests; card required even for free plan; storing results needs a plan with storage rights (no price listed) | [brave.com/search/api](https://brave.com/search/api/) | Oct 10, 2026 |
| Crunchbase Pro / API | Global funding rounds (EDGAR is US-only) | No public price; API needs Basic/Enterprise license | [about.crunchbase.com/pricing](https://about.crunchbase.com/pricing/) | Oct 10, 2026 |
| Apollo | Firmographics and titles | API only on Custom plans (no public price); data for internal use only | [apollo.io/pricing](https://www.apollo.io/pricing) | Oct 10, 2026 |
