# Usage Signals Agent

Real public signals → warehouse-first, rules-only scoring → short **cited** sales handoffs, on **real public companies**
that appear in Figma's own customer stories. Seats and usage are a **clearly labeled synthetic proxy** (no public usage data exists).

> Demo story: *"The Figma agent went GA on Oct 6. Which real companies show public intent, and what would a rep say, with receipts?"*

**Status:** private repo, nothing deployed. `snapshot/` was **frozen on Oct 10, 2026** (as_of 2026-10-10) after Chief of Staff - Coding
approved the manual review. Flagged: **Okta, Affirm, Zapier**; at risk: **Brex**. All offline commands default to the snapshot.

## Live result vs demo scenario

**Frozen live result (scoring v2 + qualification + word-set dedupe, Oct 10):** flagged Okta (75), Affirm (48), Zapier (48); at risk Brex.
Adyen dropped out once its "Senior Designer, Digital" / "Senior Digital Designer" pair counted as one role. Earlier history below.

**Live (honest) result, Oct 10 r3 pull, 38 accounts, thresholds unchanged:** 0 flagged; at risk: Carta, PostHog, Webflow.
Near-misses: Instacart 50 and Samsara 50 (both fail `min_growth` 10 and `min_total` 55), then Duolingo, Okta and Robinhood at 36.
See `docs/live-pull-2026-10-10-r3.md`.

**Demo scenario (`signals demo <account>`), clearly SYNTHETIC:** copies the live warehouse to `data/demo.duckdb` (the live file is never
modified) and injects ONE synthetic job post on one real account (here Instacart, dated 2026-10-07). Every synthetic row has
`is_synthetic = TRUE`, a `SYNTHETIC:` signal_id, a `[SYNTHETIC]` title prefix and an `example.invalid` URL; `snapshot_meta.mode = 'demo'`.
The handoff's `addressed_to` starts with `SYNTHETIC DEMO SCENARIO`, any sentence citing the synthetic source must say SYNTHETIC
(grounding rejects it otherwise), and "real" counts in the handoff facts exclude the synthetic row. The web page shows a red SYNTHETIC
banner and marks the row. Scoring refuses to run on a *live* warehouse that contains a synthetic row (`SyntheticInLiveError`).

```
signals demo instacart --db data/warehouse.duckdb --out data/demo.duckdb
signals handoff instacart --refresh --db data/demo.duckdb
signals web --db data/demo.duckdb --out out/demo/index.html
```

## Dedupe

Same account + same normalized title within 14 days = one role (earliest date kept; all URLs listed). The normalized title is the
*set* of words (lowercase; punctuation, parentheticals and word order ignored), so "Senior Designer, Digital" == "Senior Digital Designer".

## Matching rule (AI prototyping / vibe coding)

"AI prototyping" / "vibe coding" counts only if Figma or Figma Make appears anywhere in the same post, or a design context (UX, UI/UX,
designer, product design, design system, wireframe, mock-up, ...) appears within 150 characters of the term. Bare "prototype" is not
design context. This drops the Pinterest TPM boilerplate ("AI coding assistants ('vibe coding')"). `signals rematch` re-applies the rule
offline to stored excerpts (which hold the same 150-char window).

## Why this, for this role

Figma's [Marketing Engineer, AI Deployment posting](https://boards.greenhouse.io/figma/jobs/6013495004) measures success by "agents live," "hours saved," and "revenue driven — pipeline, conversion lift, or deal velocity directly attributable to what you've built." This repo targets revenue driven, using the stack Kyle Ketchum has described publicly:

- **Warehouse-first signals.** In the [Clay customer story](https://www.clay.com/customers/figma), product signals like "seat growth, feature adoption, and component usage patterns exist in Snowflake," and routing them into Salesforce "created bloat." The [Confessions of a CRM](https://open.spotify.com/episode/2tSb5dugcpdDxy48eC5JQt) host [summarized](https://www.linkedin.com/posts/anderskrohn_it-was-great-to-speak-with-kyle-ketchum-about-activity-7450122552884019200-ecs5) the shift as "treating the data warehouse as the source of truth." → All scoring is Snowflake-compatible SQL behind an adapter.
- **Enrichment plus product activity.** Kyle combines "product-qualified activity with tech stack data, funding signals, and hiring patterns" ([Clay](https://www.clay.com/customers/figma)). → Real hiring posts that mention Figma Make or AI prototyping, real funding filings, and public firmographics, joined to a clearly labeled usage proxy where no public data exists.
- **Signal-based selling, real signals first.** A rep acts on a reason they can open and check. So v2 flags an account only when *public, cited* signals line up: AI/design hiring, momentum against its own baseline, and a sourced company size. Synthetic usage is shown as context because Figma's real product data would replace it inside the warehouse, but it never decides who gets a call. The RevFest 2026 talk ["The GTM Engine Nobody Asked For"](https://www.linkedin.com/posts/andrewmattock_when-jen-igartua-first-asked-me-to-speak-activity-7459992646762151937-QXIL) was pitched at "where to start with a signal-based selling architecture." → Four real gates with written-down thresholds and reasons, and an `explain` command with source links.
- **Agents a team can trust.** The posting asks you to "Define evaluation criteria, instrument AI workflows." → Handoffs cite every claim, invent no numbers, and contain no personal data, all enforced in code.

The accounts are real public companies that appear in Figma's own [customer stories](https://www.figma.com/customers/). Usage numbers are a synthetic stand-in, labeled that way everywhere, and never decide a flag.

## Real vs. proxy

| Field | Real or proxy | Source |
|---|---|---|
| account name, domain, Figma customer-story URL and title, products mentioned (Make, Dev Mode, AI, MCP) | **Real** | Hand-curated `seeds/figma_customer_stories.csv`: Figma customer stories/blog plus public non-Figma sources (company blogs, handbooks, GitHub, conference talks); `source_type` per row. Never fetched by code |
| open roles; roles mentioning "Figma" / "Figma Make" / "AI prototyping" / "vibe coding"; posting dates; role titles | **Real** | [Greenhouse](https://developers.greenhouse.io/job-board.html), [Lever](https://github.com/lever/postings-api), [Ashby](https://developers.ashbyhq.com/docs/public-job-posting-api) public job APIs |
| hiring momentum (qualifying posts in the last 30 days vs. the prior 60) | **Real (derived), drives the flag** | Same job APIs |
| last funding date (US) | **Real** | [SEC EDGAR](https://efts.sec.gov/LATEST/search-index) Form D full-text search (kept; 0 Form D hits for the current universe, which is mostly public or late-stage companies) |
| funding and launch news mentions | **Dropped for v1** | [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/): two live pulls (5 s, then ≥10 s spacing with backoff) got 429 on about half the queries and empty results on the rest. The module stays and runs only with `--only news_gdelt` |
| HN mentions of company + Figma | **Real** | [HN Algolia API](https://hn.algolia.com/api) |
| employee count, industry, HQ country, website | **Real** (Wikidata, else hand-entered with a public source, else NULL) | [Wikidata](https://www.wikidata.org/) `Special:EntityData/<QID>.json` for hand-mapped QIDs (robots.txt disallows `/w/api.php` and `query.wikidata.org/sparql`); `seeds/manual_employees.csv` (`source=manual_public`: 10-K, annual report or the company's own page) |
| contact role titles | **Real** (titles only) | Customer-story speaker titles (`seeds/story_contacts.csv`), manual snippets, or "Hiring team for: <role>" from the account's own job post |
| paid seats, active seats, daily Make and agent events | **Synthetic stand-in, CONTEXT ONLY** (never affects flag, total or at-risk) | `signals/proxy.py`, seeded from real signal dates |
| Figma agent first-use date | **Synthetic stand-in, CONTEXT ONLY** | `signals/proxy.py` |
| owner_rep | Always NULL | CRM owner unknown for real companies → every handoff goes to "PLG / unowned queue (demo)" |

## Data ethics

- **robots.txt and terms respected.** One polite client (`signals/http.py`) checks robots.txt (stdlib parser + wildcard-aware matcher),
  rate-limits per host (1 req/s default, GDELT 1 per 5 s, SEC ≤ 5/s, robots Crawl-delay honoured), retries 429/5xx with backoff,
  records 403s and **never** retries them with different headers.
- **Honest User-Agent:** `usage-signals-agent/0.1 (+https://github.com/andydabinett/usage-signals-agent; $CONTACT_EMAIL)`. No browser spoofing.
  For `*.sec.gov` only, `SEC_USER_AGENT` (env, e.g. `Your Name you@example.com`) supplies SEC's documented "Name email" format; the repo-URL form got 403 "Undeclared Automated Tool".
- **No figma.com access by code** ([AUP §j](https://www.figma.com/aup/)) and **no linkedin.com access** of any kind. Both are on a hard
  denylist that raises before any I/O (including redirects). Figma Community signals are dropped from v1.
- **No personal data.** No person names, emails, phones or profile URLs are stored; emails inside raw API bodies are redacted to `[email]`.

## Quickstart (offline)

```bash
uv sync
uv run pytest                        # network disabled by a socket guard; HTTP mocked with respx
uv run signals score --all           # default: snapshot/warehouse.duckdb (frozen Oct 10, 2026)
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

**Which posts qualify (threshold-neutral, `signals/qualify.py`; re-apply offline with `signals requalify`):**
- A Figma-related post qualifies if it is a **design role** (product, UX/UI, visual, brand, motion, creative, art direction,
  illustration, design ops; "design engineer" counts), or if **any role's description is explicitly about** AI prototyping,
  Figma Make, or designing for AI agents. **Interns are excluded.** Engineering, PM and other roles where Figma only appears as a listed
  tool are excluded (for example Okta "Lead AI Engineer", Lyft "Senior Software Engineer - iOS").
- **Dedupe:** the same company and normalized title (lowercased, punctuation and parentheticals removed) within 14 days of the earliest post is
  one post. The earliest date is kept and every URL is listed (`dup_urls`; "also posted at" in the handoff, "also (same role)" in explain).
- **Dates:** the first-published date is preferred (Greenhouse `first_published`, Ashby `publishedAt`, Lever `createdAt`). Where only an
  updated date exists, the signal is marked `date_basis=updated`. `explain`, the web page and the handoff facts show this, and grounding
  rejects a handoff that states such a date as "posted" instead of "updated on". In the Oct 10 data every post had a first-published date.
- **No blog source in v1.** Public intent is only HN mentions and SEC Form D. Company blog or engineering-post mentions have no ingest
  module, so they aren't counted.

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

## Grounding

Handoffs (`anthropic/claude-sonnet-5.5`, strict JSON schema, `reasoning.effort=low`, override with `HANDOFF_MODEL`) are checked in code:
every sentence of *why this account* / *why now* ends with `[n]` mapping to a `signal_id` in the facts; every citation URL is in the facts;
every number is in the facts allow-list AND in the source(s) cited by its own sentence (headcount is a cited `employees:` source, e.g.
Affirm's 10-K); synthetic stand-in numbers carry "(synthetic stand-in)"; when agent-design or Figma Make posts exist (`lead_with`),
*why now* must cite one of them first and, for agent-design, the first line must speak to AI agents; role titles exist in `contacts`; no `@`/phone patterns (a
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
