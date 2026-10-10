"""5.7 — SEC EDGAR full-text search for Form D. Requires CONTACT_EMAIL in the UA (SEC fair-access policy).
An entity is accepted only if its normalized name equals the seed's normalized legal_name."""
from __future__ import annotations

import datetime as dt
import re

from .common import read_csv, replace_for_accounts

URL = "https://efts.sec.gov/LATEST/search-index"
SUFFIX = re.compile(r"\b(inc|incorporated|corp|corporation|llc|ltd|limited|plc|co|company|sa|se|nv|n v|ag|as|holdings?)\b")


def norm(name: str) -> str:
    s = re.sub(r"\(cik[^)]*\)", " ", (name or "").lower())
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = SUFFIX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def filing_url(cik: str, adsh: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{adsh.replace('-', '')}/{adsh}-index.htm"


def parse_hits(account_id: str, legal_name: str, data: dict) -> list[dict]:
    want = norm(legal_name)
    rows, seen = [], set()
    for h in data.get("hits", {}).get("hits", []):
        src = h.get("_source", {})
        adsh = src.get("adsh") or h.get("_id", "").split(":")[0]
        names = src.get("display_names") or []
        ciks = src.get("ciks") or []
        if not adsh or adsh in seen or not any(norm(n) == want for n in names):
            continue
        seen.add(adsh)
        cik = ciks[0] if ciks else "0"
        rows.append({"signal_id": f"fund:edgar:{adsh}", "account_id": account_id, "source": "sec_edgar_form_d",
                     "filed_on": dt.date.fromisoformat(src["file_date"]), "url": filing_url(cik, adsh),
                     "round_label": f"SEC Form {src.get('form') or src.get('root_form') or 'D'} filing", "amount_usd": None})
    return rows


def pull(wh, accounts, since=None, client=None, seeds_dir=None, as_of: dt.date | None = None) -> int:
    as_of = as_of or dt.date.today()
    legal = {r["account_id"]: r["legal_name"] or r["company"] for r in read_csv("figma_customer_stories.csv", seeds_dir)}
    rows, done = [], []
    for a in accounts:
        name = legal.get(a["account_id"]) or a["account_name"]
        resp = client.get(URL, source="funding_edgar", params={
            "q": f'"{name}"', "forms": "D", "startdt": (as_of - dt.timedelta(days=365)).isoformat(), "enddt": as_of.isoformat()})
        if resp is None or resp.status_code != 200:
            continue
        done.append(a["account_id"])
        rows += parse_hits(a["account_id"], name, resp.json())
    return replace_for_accounts(wh, "funding", done, rows, "AND source = 'sec_edgar_form_d'")
