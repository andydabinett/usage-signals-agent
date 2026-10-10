# Scoring v2 rescore: Oct 10, 2026 (AS_OF 2026-10-10), for CoS review. NOT frozen.

**What was run:** a fresh v2 rescore of the stored r3 live data (pulled earlier today, 38 accounts). No new network pull, because the data is same-day.
The thresholds were committed first (df3dc11), then the code (9aceab6), then a hygiene fix (a657986). Scoring on live data happened only after that.
Gates: hiring >= 2 qualifying posts in 30d; momentum ratio >= 1.5 (baseline floored at 1/mo); employees >= 200 (wikidata/manual_public); >= 1 real cited signal in 30d.
Points rank only. Synthetic seats and usage are context only.

## Flagged (6)
| Account | Total | Hiring (>=2) | Momentum (>=1.5) | Fit (>=200) | Recent (>=1) | Intent (rank only) | Real cited signals (date, title, URL) |
|---|---|---|---|---|---|---|---|
| Okta | 75 | 7 posts, 2 agent-design: PASS (35 pts) | 7 vs 2/60d: 7.00 PASS (25) | 6,366 manual_public: PASS (15) | 7 PASS | HN 0, Form D no (0) | 2026-10-08 Senior Art Director, Demand Gen https://www.okta.com/company/careers/opportunity/8262246?gh_jid=8262246 ; 2026-10-06 Lead AI Engineer …/8208088 ; 2026-10-02 Senior Product Designer - Okta for AI Agents …/8248278 ; 2026-10-01 Staff Product Designer - Okta Identity Governance …/8247059 ; 2026-09-25 Staff UX Designer …/8232605 ; 2026-09-18 Principal Product Designer – UI Platform …/8145887 ; 2026-09-11 Senior Design Operations Program Manager - Agentic Design …/8194325 |
| Lyft | 53 | 2 PASS (10) | 2 vs 2/60d: 2.00 PASS (18) | 3,913 PASS (20) | 2 PASS | HN 1 (5) | 2026-09-24 Content Systems Intern (Summer 2027) https://app.careerpuck.com/job-board/lyft/job/8817900002?gh_jid=8817900002 ; 2026-09-15 Senior Software Engineer - iOS https://app.careerpuck.com/job-board/lyft/job/8780012002?gh_jid=8780012002 |
| Adyen | 48 | 2 PASS (10) | 2 vs 0: 2.00 PASS (18) | 4,771 PASS (20) | 2 PASS | 0 | 2026-10-07 Senior Digital Designer https://job-boards.greenhouse.io/adyen/jobs/8242349 ; 2026-10-01 Senior Designer, Digital https://job-boards.greenhouse.io/adyen/jobs/8214546 |
| Samsara | 48 | 2 PASS (10) | 2 vs 0: 2.00 PASS (18) | 4,100 PASS (20) | 2 PASS | 0 | 2026-10-02 Associate Creative Director, Digital Design https://www.samsara.com/company/careers/roles/8250008?gh_jid=8250008 ; 2026-09-24 same title https://www.samsara.com/company/careers/roles/8205153?gh_jid=8205153 |
| Zapier | 48 | 2 PASS (10) | 2 vs 0: 2.00 PASS (18) | 800 PASS (20) | 2 PASS | 0 | 2026-10-02 Sr. Motion Designer https://jobs.ashbyhq.com/zapier/c0582311-18cb-4415-9c86-79014f1b74f6 ; 2026-09-16 Growth Design Lead https://jobs.ashbyhq.com/zapier/b14ac81b-d94c-4a46-89a3-017f3d113517 |
| Instacart | 47 | 3 PASS (15) | 3 vs 4/60d: 1.50 PASS (12) | 3,600 PASS (20) | 3 PASS | 0 | 2026-10-02 Senior Design Program Manager II https://instacart.careers/job/?gh_jid=8249753 and …8249751 ; 2026-09-28 Sr Software Engineer II - Ads Manager (Front End) https://instacart.careers/job/?gh_jid=8237393 |

Review notes: Samsara and Instacart each count the same title twice (two requisitions, likely two locations). Lyft's two posts are an intern and an iOS engineer whose descriptions mention Figma. Instacart sits exactly on the momentum line (1.50).
Synthetic context values for these accounts don't affect the flags (that's what the invariance test checks).

## At risk (cooling): Brex: 9 qualifying posts in the prior 60d, 0 in the last 30d.

## Near-misses (one gate short)
| Account | Total | Failing gate |
|---|---|---|
| Linear | 43 | fit: 160 employees < 200 (hiring 2, ratio 2.00, recent 3, HN 2) |
| Discord | 40 | fit: employee count unknown (hiring 3, ratio 3.00) |
| Ramp | 38 | fit: unknown (hiring 2, ratio 2.00, Form D yes) |
| Stripe | 40 | momentum: 3 vs 6/60d = 1.00 < 1.5 |
| Affirm | 30 | momentum: 2 vs 3/60d = 1.33 < 1.5 |

## Demo scenario (SYNTHETIC), re-checked under v2
One synthetic post on **Affirm** (2026-10-07) lifts momentum to 2.00, so Affirm flags (63) in `data/demo.duckdb` only. The template handoff
is labeled "SYNTHETIC DEMO SCENARIO" and passes grounding. The demo web page carries the SYNTHETIC banner; the live page has no SYNTHETIC text.

LLM spend this step: $0 (no LLM handoffs were generated for the new flags).
