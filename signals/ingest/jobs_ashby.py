"""5.4 — Ashby posting API, via api.ashbyhq.com only (jobs.ashbyhq.com disallows /api/)."""
from __future__ import annotations

from .common import ats_slugs, html_to_text, job_row, parse_date, replace_for_accounts

URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def pull(wh, accounts, since=None, client=None, seeds_dir=None) -> int:
    slugs = ats_slugs("ashby", seeds_dir)
    total = 0
    for a in accounts:
        slug = slugs.get(a["account_id"])
        if not slug:
            continue
        resp = client.get(URL.format(slug=slug), source="jobs_ashby")
        if resp is None or resp.status_code != 200:
            continue
        rows = []
        for j in resp.json().get("jobs", []):
            text = html_to_text((j.get("title") or "") + " " + (j.get("descriptionPlain") or j.get("descriptionHtml") or ""))
            d = parse_date(j.get("publishedAt"))
            rows.append(job_row(a["account_id"], "ashby", j["id"], j.get("title"), j.get("jobUrl"), d, d, text))
        total += replace_for_accounts(wh, "job_posts", [a["account_id"]], rows, "AND ats = 'ashby'")
    return total
