"""5.2 — Greenhouse public job board API."""
from __future__ import annotations

from .common import ats_slugs, html_to_text, job_row, parse_date, replace_for_accounts

URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"


def pull(wh, accounts, since=None, client=None, seeds_dir=None) -> int:
    slugs = ats_slugs("greenhouse", seeds_dir)
    total = 0
    for a in accounts:
        slug = slugs.get(a["account_id"])
        if not slug:
            continue
        resp = client.get(URL.format(slug=slug), source="jobs_greenhouse")
        if resp is None or resp.status_code != 200:
            continue
        rows = []
        for j in resp.json().get("jobs", []):
            text = html_to_text(j.get("title", "") + " " + (j.get("content") or ""))
            rows.append(job_row(a["account_id"], "greenhouse", j["id"], j.get("title"), j.get("absolute_url"),
                                parse_date(j.get("first_published")), parse_date(j.get("updated_at")), text))
        total += replace_for_accounts(wh, "job_posts", [a["account_id"]], rows, "AND ats = 'greenhouse'")
    return total
