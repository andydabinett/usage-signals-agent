"""5.3 — Lever public postings API (robots Crawl-delay: 1 honoured by the client)."""
from __future__ import annotations

from .common import ats_slugs, html_to_text, job_row, parse_date, replace_for_accounts

URL = "https://api.lever.co/v0/postings/{slug}?mode=json"


def pull(wh, accounts, since=None, client=None, seeds_dir=None) -> int:
    slugs = ats_slugs("lever", seeds_dir)
    total = 0
    for a in accounts:
        slug = slugs.get(a["account_id"])
        if not slug:
            continue
        resp = client.get(URL.format(slug=slug), source="jobs_lever")
        if resp is None or resp.status_code != 200:
            continue
        rows = []
        for j in resp.json():
            parts = [j.get("text", ""), j.get("descriptionPlain") or html_to_text(j.get("description")),
                     j.get("additionalPlain") or ""]
            for lst in j.get("lists") or []:
                parts.append(lst.get("text", "") + " " + html_to_text(lst.get("content")))
            d = parse_date(j.get("createdAt"))
            rows.append(job_row(a["account_id"], "lever", j["id"], j.get("text"), j.get("hostedUrl"), d, d,
                                html_to_text(" ".join(parts))))
        total += replace_for_accounts(wh, "job_posts", [a["account_id"]], rows, "AND ats = 'lever'")
    return total
