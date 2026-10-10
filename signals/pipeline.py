"""Online refresh orchestration."""
from __future__ import annotations

import datetime as dt
import importlib
import json

from .http import PoliteClient
from .ingest import MODULES
from . import proxy

ORDER = ["figma_customers_seed", "jobs_greenhouse", "jobs_lever", "jobs_ashby", "enrich_wikidata", "manual_snippets",
         "enrich_website", "funding_edgar", "news_gdelt", "mentions_hn"]
assert set(ORDER) == set(MODULES)


def derive_contacts(wh) -> int:
    """Accounts with no story/snippet role title get a public, person-free role reference from their own Figma-mentioning
    job post (the hiring team for that role), with the job post URL as source."""
    rows = wh.query("""SELECT j.account_id, j.title, j.url FROM job_posts j
        WHERE (j.mentions_figma OR j.mentions_figma_make OR j.mentions_ai_prototyping)
          AND j.account_id NOT IN (SELECT account_id FROM contacts) ORDER BY j.account_id, j.mentions_figma_make DESC, j.published_on DESC""")
    out, seen = [], set()
    for r in rows:
        if r["account_id"] in seen:
            continue
        seen.add(r["account_id"])
        out.append({"account_id": r["account_id"], "role_title": f"Hiring team for: {r['title']}"[:160], "source_url": r["url"]})
    return wh.load_rows("contacts", out)


def refresh(wh, as_of: dt.date, only: str | None = None, since: dt.date | None = None, contact_email: str | None = None,
            client: PoliteClient | None = None, log=print, seeds_dir=None) -> dict:
    client = client or PoliteClient(wh=wh, contact_email=contact_email, log=log)
    counts = {}
    for name in ORDER:
        if only and name not in (only, "figma_customers_seed"):
            continue
        mod = importlib.import_module(f"signals.ingest.{name}")
        accounts = wh.query("SELECT account_id, account_name, domain, products_mentioned FROM accounts ORDER BY account_id")
        kw = {"as_of": as_of} if name == "funding_edgar" else {}
        log(f"[{name}] …")
        counts[name] = mod.pull(wh, accounts, since, client=client, seeds_dir=seeds_dir, **kw)
        log(f"[{name}] rows={counts[name]}")
    counts["derived_contacts"] = derive_contacts(wh)
    proxy.build(wh, as_of)
    src_counts = {t: wh.query(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"] for t in
                  ("accounts", "job_posts", "funding", "news", "mentions", "enrichment", "contacts", "raw_pulls")}
    wh.execute("DELETE FROM snapshot_meta")
    wh.load_rows("snapshot_meta", [{"as_of": as_of, "frozen_at": None, "git_sha": None, "source_counts": json.dumps(src_counts)}])
    return {"module_rows": counts, "table_counts": src_counts, **client.summary()}
