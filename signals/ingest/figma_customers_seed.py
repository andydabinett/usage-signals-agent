"""5.1 — hand-curated seed of Figma customer stories. NO request to figma.com is ever made (D12)."""
from __future__ import annotations

from .common import read_csv


def pull(wh, accounts=None, since=None, client=None, seeds_dir=None) -> int:
    rows = read_csv("figma_customer_stories.csv", seeds_dir)
    wh.execute("DELETE FROM accounts")
    n = wh.load_rows("accounts", [{
        "account_id": r["account_id"], "account_name": r["company"], "legal_name": r["legal_name"] or None,
        "domain": r["domain"] or None, "story_url": r["story_url"], "story_title": r["story_title"],
        "products_mentioned": r["products_mentioned"], "owner_rep": None,  # D9
    } for r in rows])
    wh.execute("DELETE FROM contacts")
    wh.load_rows("contacts", [{"account_id": c["account_id"], "role_title": c["role_title"], "source_url": c["source_url"]}
                              for c in read_csv("story_contacts.csv", seeds_dir)])
    return n


def seed_rows(seeds_dir=None) -> list[dict]:
    return read_csv("figma_customer_stories.csv", seeds_dir)
