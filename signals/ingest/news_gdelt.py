"""5.8 — GDELT DOC 2.0 API (1 request per 5 s). Tags funding / launch / layoffs by keyword on the title."""
from __future__ import annotations

import re

from .common import parse_date, read_csv, replace_for_accounts, short_hash

URL = "https://api.gdeltproject.org/api/v2/doc/doc"
TAGS = [("layoffs", re.compile(r"\blay ?offs?\b|\bjob cuts?\b|\bcuts? \d+ jobs\b", re.I)),
        ("funding", re.compile(r"\braises?\b|\bfunding\b|\bseries [a-h]\b|\binvestment round\b", re.I)),
        ("launch", re.compile(r"\blaunch(es|ed)?\b|\bunveils?\b|\bintroduces?\b", re.I))]


def tag_of(title: str) -> str | None:
    for tag, rx in TAGS:
        if rx.search(title or ""):
            return tag
    return None


def parse_articles(account_id: str, company: str, data: dict) -> list[dict]:
    rows, seen = [], set()
    cname = re.compile(r"\b" + re.escape(company) + r"\b", re.I)
    for art in data.get("articles", []) or []:
        title, url = art.get("title") or "", art.get("url")
        tag = tag_of(title)
        if not url or url in seen or not tag or not cname.search(title):
            continue
        seen.add(url)
        rows.append({"signal_id": f"news:gdelt:{short_hash(url)}", "account_id": account_id, "source": "gdelt",
                     "url": url, "title": title[:300], "seen_on": parse_date(art.get("seendate")), "tag": tag})
    return rows


def pull(wh, accounts, since=None, client=None, seeds_dir=None) -> int:
    names = {r["account_id"]: r["search_name"] or r["company"] for r in read_csv("figma_customer_stories.csv", seeds_dir)}
    rows, done = [], []
    for a in accounts:
        q = names.get(a["account_id"], a["account_name"])
        resp = client.get(URL, source="news_gdelt", params={
            "query": f'"{q}" (funding OR raises OR launches OR layoffs)', "mode": "artlist", "format": "json",
            "timespan": "3months", "maxrecords": "25"})
        if resp is None or resp.status_code != 200:
            continue
        try:
            data = resp.json()
        except ValueError:  # GDELT answers rate-limit notices as text
            client.errors.append(f"gdelt non-json for {a['account_id']}: {resp.text[:80]!r}")
            continue
        done.append(a["account_id"])
        rows += parse_articles(a["account_id"], a["account_name"], data)
    return replace_for_accounts(wh, "news", done, rows)
