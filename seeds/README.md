# Seeds (hand-curated, committed)

- `figma_customer_stories.csv` — the account universe (D14). **Built without any request to figma.com** (AUP §j):
  URLs/titles come from the spec's Oct 10 index read plus public web-search results. `products_mentioned` is inferred
  from the story title/search snippet. `verified_in_browser=no` means a human still has to open each URL in a browser
  and confirm title + products. Headspace and Alaska Airlines link to Figma *blog* case studies (no `/customers/` URL found).
- `story_contacts.csv` — public **role titles only** quoted in those stories. No names.
- `ats_slugs.csv` — job-board slugs, verified against the public Greenhouse/Lever/Ashby APIs on 2026-10-10
  (`hs` is Headspace's Greenhouse board; Insider One is on Lever). `none` = no public board found under obvious slugs.
- `manual_snippets.csv` — LinkedIn/search snippets **pasted by a human** (D13). Empty until someone curates it.

## Oct 10, 2026 update
- 11 accounts with no public Greenhouse/Lever/Ashby board were swapped out (Saddle, Civica, Accor, Findable, Carrefour, Grab, Botim,
  King, ASOS, Alaska Airlines, Amadeus) for publicly documented Figma users with boards: Duolingo, Pinterest, Dropbox, GitLab, Discord,
  Coinbase, Mozilla, Asana, Stripe (Greenhouse), Linear, Notion (Ashby). `source_type` records the kind of public source.
- `wikidata_qid` is hand-mapped from public Wikidata pages (`;` = candidates; first one with an employee count wins).
- `manual_employees.csv` (`source=manual_public`): counts from a 10-K, an annual report or the company's own page, for accounts
  Wikidata had no count for. Values were taken from public search snippets of the cited page; a human should confirm each one.
