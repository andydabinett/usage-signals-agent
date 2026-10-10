# v2 rescore with post qualification + dedupe: Oct 10, 2026 (AS_OF 2026-10-10). For CoS review. NOT frozen.

Stored r3 data rescored offline (`signals requalify`, no network pull). Thresholds unchanged (hiring >= 2 / 30d; momentum >= 1.5x,
floor 1/mo; employees >= 200 wikidata/manual_public; >= 1 real cited signal in 30d). Posts: 101 Figma-related, 23 dropped
(4 intern, 19 non-design with Figma only as a listed tool), 13 deduped, 65 qualifying.
Every signal below has date_basis=published (no updated-only dates in this data).

## Flagged (4)
| Account | Total | Hiring >=2 | Momentum >=1.5 | Fit >=200 | Recent >=1 | Intent (rank) | Signals (date, basis, URL) |
|---|---|---|---|---|---|---|---|
| Okta | 75 | 6 (2 agent-design) PASS, 35 | 6 vs 2/60d = 6.00 PASS, 25 | 6,366 manual_public PASS, 15 | 6 PASS | 0 | 2026-09-11 published Senior Design Operations Program Manager - Agentic Design https://www.okta.com/company/careers/opportunity/8194325?gh_jid=8194325 ; 2026-09-18 published Principal Product Designer – UI Platform …/8145887 ; 2026-09-25 published Staff UX Designer …/8232605 ; 2026-10-01 published Staff Product Designer - Okta Identity Governance …/8247059 ; 2026-10-02 published Senior Product Designer - Okta for AI Agents …/8248278 ; 2026-10-08 published Senior Art Director, Demand Gen …/8262246 |
| Adyen | 48 | 2 PASS, 10 | 2 vs 0 = 2.00 PASS, 18 | 4,771 manual_public (unconfirmed) PASS, 20 | 2 PASS | 0 | 2026-10-01 published Senior Designer, Digital https://job-boards.greenhouse.io/adyen/jobs/8214546 ; 2026-10-07 published Senior Digital Designer https://job-boards.greenhouse.io/adyen/jobs/8242349 |
| Affirm | 48 | 2 PASS, 10 | 2 vs 0 = 2.00 PASS, 18 | 2,358 manual_public PASS, 20 | 2 PASS | 0 | 2026-09-21 published Senior Product Designer https://job-boards.greenhouse.io/affirm/jobs/7990774003 ; 2026-09-30 published Visual Designer II https://job-boards.greenhouse.io/affirm/jobs/7966043003 |
| Zapier | 48 | 2 PASS, 10 | 2 vs 0 = 2.00 PASS, 18 | 800 manual_public PASS, 20 | 2 PASS | 0 | 2026-09-16 published Growth Design Lead https://jobs.ashbyhq.com/zapier/b14ac81b-d94c-4a46-89a3-017f3d113517 ; 2026-10-02 published Sr. Motion Designer https://jobs.ashbyhq.com/zapier/c0582311-18cb-4415-9c86-79014f1b74f6 |

Affirm is a new flag. Its prior-60d baseline fell from 3 to 0 because those 3 posts were non-design roles where Figma was only a listed tool
(2x Senior Product Manager, 1: Many Merchant Growth, 2026-08-10; Senior Software Engineer, Frontend, 2026-08-21).

## Handoffs (LLM, all grounding PASS)
**Okta.** For: PLG / unowned queue (demo). Why this account: Okta's public Odyssey Design System is a Figma UI kit, so design work already runs through Figma [1]. Why now: Okta posted a Staff Product Designer role for Identity Governance on 2026-10-01 [2], then a Senior Art Director, Demand Gen role on 2026-10-08 [3]. Who: Hiring team for: Senior Art Director, Demand Gen (…/8262246): ask how the growing design team shares Figma files. First line: Saw Okta is hiring more designers; how are you scaling Odyssey across them? [1] https://github.com/okta/odyssey/ [2] …/8247059 [3] …/8262246

**Adyen.** For: PLG / unowned queue (demo). Why this account: Adyen's customer story shows Variables streamlining its design system in Figma Design and FigJam. [1] Why now: A Senior Designer, Digital role was posted on 2026-10-01, and a Senior Digital Designer role was posted on 2026-10-07. [2] [3] Who: Design Lead (customer story): ask how Variables is scaling as the design team hires. First line: Saw Adyen is hiring digital designers; how is your Variables-based design system holding up? [1] https://www.figma.com/customers/figma-helps-adyen-streamline-design-system/ (hand-recorded seed URL, never fetched) [2] …/8214546 [3] …/8242349

**Affirm.** For: PLG / unowned queue (demo). Why this account: Affirm maintains a public design system changelog built on a Figma Core Library, and it is a fintech with 2358 employees. [1] Why now: Affirm posted a Senior Product Designer role on 2026-09-21 [2], and a Visual Designer II role followed on 2026-09-30 [3]. Who: Hiring team for: Visual Designer II (…/7966043003): ask how the new visual design hire will work with the Figma library. First line: Saw Affirm is hiring visual designers; how is your Core Library supporting them? [1] https://www.affirm.design/latest/changelog.html [2] …/7990774003 [3] …/7966043003
Review note: "2358 employees" is attributed to [1], but the count comes from the 10-K. Grounding allows it because the number is in the facts.

**Zapier.** For: PLG / unowned queue (demo). Why this account: Zapier published a rebrand story describing its Figma libraries [1]. Why now: A Growth Design Lead job was posted on 2026-09-16 [2]. A motion designer job followed on 2026-10-02 [3]. Who: Hiring team for: Sr. Motion Designer (…c0582311…): ask how design tooling will support the new motion hire. First line: Saw your motion designer opening; how are your Figma libraries supporting the rebrand? [1] https://zapier.com/blog/zapiers-new-look/ [2] …b14ac81b… [3] …c0582311…

## Dropped since the last rescore
- Lyft: Content Systems Intern (intern), Senior Software Engineer - iOS (Figma only a listed tool). 0 qualifying posts in 30d.
- Samsara: the two Associate Creative Director, Digital Design posts (2026-09-24 and 2026-10-02) were deduped into one. 1 post < 2.
- Instacart: Senior Design Program Manager II x2 deduped to 1; Sr Software Engineer II - Ads Manager dropped as engineering. 1 post.
- Okta: Lead AI Engineer dropped. The excerpt only lists Figma among tools ("REST/GraphQL APIs for enterprise developer tools (Jira, GitHub/GitLab, Figma, CI/CD platforms)"), so it doesn't meet the explicit-description bar. Okta still flags with 6.

## At risk (cooling): Brex: 4 qualifying posts in the prior 60d (after dedupe), 0 in 30d.
## Near-misses
| Account | Total | Gates |
|---|---|---|
| Discord | 40 | hiring 3, momentum 3.00, recent 3 PASS; fit FAIL (no allowed employee source) |
| Stripe | 35 | hiring 2, fit 8,000, recent 2 PASS; momentum 2 vs 5/60d = 0.80 FAIL |
| Samsara, Instacart, InsiderOne, Robinhood, Datadog | 25 or less | hiring 1 < 2 (each one other gate short) |
| Linear | 20 | hiring 1 (deduped), fit 160 < 200 |

## Adyen headcount
Still unconfirmed: investors.adyen.com is JS-rendered, and Adyen's Pillar III PDF on brand.adyen.com is disallowed by robots.txt. Kept as
manual_public 4,771 with an "unconfirmed" note.

## Demo
Re-run on Samsara (Affirm now flags live). One SYNTHETIC post lifts Samsara to 2 posts, momentum 2.00, so it flags in demo only; the template handoff is labeled and passes.
LLM spend this step: $0.0544 (4 handoffs; Zapier needed a retry, $0.0266).
