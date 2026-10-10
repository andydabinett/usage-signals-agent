"""One module per source; each exposes pull(wh, accounts, since, client=...) -> int."""
MODULES = [
    "figma_customers_seed", "jobs_greenhouse", "jobs_lever", "jobs_ashby", "enrich_wikidata",
    "enrich_website", "funding_edgar", "news_gdelt", "mentions_hn", "manual_snippets",
]
