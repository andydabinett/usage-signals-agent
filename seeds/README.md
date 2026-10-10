# Seeds (hand-curated, committed)

- `figma_customer_stories.csv` — the account universe (D14). **Built without any request to figma.com** (AUP §j):
  URLs/titles come from the spec's Oct 10 index read plus public web-search results. `products_mentioned` is inferred
  from the story title/search snippet. `verified_in_browser=no` means a human still has to open each URL in a browser
  and confirm title + products. Headspace and Alaska Airlines link to Figma *blog* case studies (no `/customers/` URL found).
- `story_contacts.csv` — public **role titles only** quoted in those stories. No names.
- `ats_slugs.csv` — job-board slugs, verified against the public Greenhouse/Lever/Ashby APIs on 2026-10-10
  (`hs` is Headspace's Greenhouse board; Insider One is on Lever). `none` = no public board found under obvious slugs.
- `manual_snippets.csv` — LinkedIn/search snippets **pasted by a human** (D13). Empty until someone curates it.
