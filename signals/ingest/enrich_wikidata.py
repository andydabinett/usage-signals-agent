"""5.5 — Wikidata entity search + SPARQL (P1128 employees, P452 industry, P17 country, P856 website). CC0."""
from __future__ import annotations

import datetime as dt
import re

from .common import read_csv, replace_for_accounts

SEARCH = "https://www.wikidata.org/w/api.php"
SPARQL = "https://query.wikidata.org/sparql"
ORGISH = re.compile(r"compan|airline|corporat|brand|platform|service|group|business|retail|developer|multinational|"
                    r"startup|firm|operator|provider|chain|conglomerate|plc|enterprise|software|app|bank|fintech|"
                    r"game|streaming|hotel|e-commerce|online", re.I)

QUERY = """SELECT ?emp ?empDate ?industryLabel ?countryLabel ?website WHERE {
  OPTIONAL { wd:%(qid)s p:P1128 ?st . ?st ps:P1128 ?emp . OPTIONAL { ?st pq:P585 ?empDate } }
  OPTIONAL { wd:%(qid)s wdt:P452 ?industry }
  OPTIONAL { wd:%(qid)s wdt:P17 ?country }
  OPTIONAL { wd:%(qid)s wdt:P856 ?website }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}"""


def pick_entity(results: list[dict]) -> dict | None:
    for r in results:
        if ORGISH.search(r.get("description") or ""):
            return r
    return None


def parse_sparql(qid: str, data: dict) -> dict:
    rows = data.get("results", {}).get("bindings", [])
    emps = []
    industry = country = website = None
    for b in rows:
        if "emp" in b:
            try:
                emps.append((b.get("empDate", {}).get("value", ""), int(float(b["emp"]["value"]))))
            except ValueError:
                pass
        industry = industry or b.get("industryLabel", {}).get("value")
        country = country or b.get("countryLabel", {}).get("value")
        website = website or b.get("website", {}).get("value")
    employees = sorted(emps)[-1][1] if emps else None  # latest point-in-time
    return {"employees": employees, "industry": industry, "country": country, "website": website}


def pull(wh, accounts, since=None, client=None, seeds_dir=None, today: dt.date | None = None) -> int:
    today = today or dt.date.today()
    names = {r["account_id"]: r["search_name"] or r["company"] for r in read_csv("figma_customer_stories.csv", seeds_dir)}
    out = []
    for a in accounts:
        aid = a["account_id"]
        resp = client.get(SEARCH, source="enrich_wikidata", params={
            "action": "wbsearchentities", "search": names.get(aid, a["account_name"]), "language": "en",
            "type": "item", "format": "json", "limit": "7"})
        if resp is None or resp.status_code != 200:
            continue
        ent = pick_entity(resp.json().get("search", []))
        if not ent:
            continue
        qid = ent["id"]
        r2 = client.get(SPARQL, source="enrich_wikidata", params={"query": QUERY % {"qid": qid}, "format": "json"})
        facts = parse_sparql(qid, r2.json()) if r2 is not None and r2.status_code == 200 else {}
        out.append({"account_id": aid, "employees": facts.get("employees"),
                    "employees_source_url": f"https://www.wikidata.org/wiki/{qid}" if facts.get("employees") else None,
                    "industry": facts.get("industry"), "country": facts.get("country"), "website": facts.get("website"),
                    "qid": qid, "retrieved_on": today})
    return replace_for_accounts(wh, "enrichment", [r["account_id"] for r in out], out)
