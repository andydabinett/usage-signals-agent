"""5.9 — HN Algolia search_by_date for '"{company}" figma' stories (low-weight mention signal)."""
from __future__ import annotations

from .common import parse_date, replace_for_accounts

URL = "https://hn.algolia.com/api/v1/search_by_date"


def parse_hits(account_id: str, data: dict) -> list[dict]:
    rows = []
    for h in data.get("hits", []):
        oid = h.get("objectID")
        if not oid:
            continue
        rows.append({"signal_id": f"hn:{oid}", "account_id": account_id, "source": "hn_algolia",
                     "url": f"https://news.ycombinator.com/item?id={oid}", "title": (h.get("title") or "")[:300],
                     "created_on": parse_date(h.get("created_at")), "points": h.get("points")})
    return rows


def pull(wh, accounts, since=None, client=None, seeds_dir=None) -> int:
    rows, done = [], []
    for a in accounts:
        params = {"query": f'"{a["account_name"]}" figma', "tags": "story"}
        resp = client.get(URL, source="mentions_hn", params=params)
        if resp is None or resp.status_code != 200:
            continue
        done.append(a["account_id"])
        rows += parse_hits(a["account_id"], resp.json())
    return replace_for_accounts(wh, "mentions", done, rows)
