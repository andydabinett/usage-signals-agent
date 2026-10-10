"""5.6 — company homepage, /about, /careers (robots-checked; 3 paths per domain). Suggests ATS slugs for human review."""
from __future__ import annotations

import datetime as dt
import re

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from ..http import ForbiddenHost, redact
from .common import replace_for_accounts

PATHS = ["/", "/about", "/careers"]
ATS_RX = re.compile(r"(boards\.greenhouse\.io|job-boards\.greenhouse\.io|jobs\.lever\.co|jobs\.ashbyhq\.com)/([A-Za-z0-9_-]+)")


def parse_page(text: str) -> dict:
    tree = HTMLParser(text or "")
    def meta(sel):
        n = tree.css_first(sel)
        return (n.attributes.get("content") or "").strip() if n else None
    t = tree.css_first("title")
    m = ATS_RX.search(text or "")
    return {"page_title": t.text(strip=True)[:300] if t else None, "meta_description": (meta('meta[name="description"]') or "")[:500] or None,
            "og_site": meta('meta[property="og:site_name"]'), "ats_hint": f"{m.group(1)}/{m.group(2)}" if m else None}


def pull(wh, accounts, since=None, client=None, seeds_dir=None, today: dt.date | None = None) -> int:
    today = today or dt.date.today()
    rows, done = [], []
    for a in accounts:
        dom = a.get("domain")
        if not dom:
            continue
        done.append(a["account_id"])
        for p in PATHS:
            url = f"https://{dom}{p}"
            try:
                resp = client.get(url, source="enrich_website")
            except ForbiddenHost:
                continue
            if resp is None or resp.status_code != 200 or "html" not in resp.headers.get("content-type", ""):
                continue
            meta = {k: (redact(v) if isinstance(v, str) else v) for k, v in parse_page(resp.text).items()}
            rows.append({"account_id": a["account_id"], "url": str(resp.url), **meta, "retrieved_on": today})
    return replace_for_accounts(wh, "website_meta", done, rows)
