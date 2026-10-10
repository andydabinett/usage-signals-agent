"""5.5 — Wikidata via /wiki/Special:EntityData/<QID>.json with hand-mapped QIDs (seed column `wikidata_qid`, ';'-separated
candidates, first one with an employee count wins). robots.txt disallows /w/ (wbsearchentities) and query.wikidata.org/sparql
for generic bots but explicitly allows `/wiki/Special:EntityData/*.`; the polite client re-checks robots before every fetch.
Reads P1128 (employees, latest P585), P452 (industry), P17 (country), P856 (website). CC0."""
from __future__ import annotations

import datetime as dt

from .common import read_csv, replace_for_accounts

ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"


def _entity(data: dict, qid: str) -> dict:
    ents = data.get("entities", {})
    return ents.get(qid) or (next(iter(ents.values())) if ents else {})


def _claims(ent: dict, prop: str) -> list[dict]:
    return [c for c in ent.get("claims", {}).get(prop, []) if c.get("rank") != "deprecated"
            and c.get("mainsnak", {}).get("snaktype") == "value"]


def parse_entity(ent: dict) -> dict:
    emps = []
    for c in _claims(ent, "P1128"):
        try:
            amt = int(float(c["mainsnak"]["datavalue"]["value"]["amount"]))
        except (KeyError, ValueError, TypeError):
            continue
        when = ""
        for q in c.get("qualifiers", {}).get("P585", []):
            when = q.get("datavalue", {}).get("value", {}).get("time", "") or when
        emps.append((c.get("rank") == "preferred", when, amt))
    def first_id(prop):
        for c in _claims(ent, prop):
            v = c["mainsnak"].get("datavalue", {}).get("value")
            return v.get("id") if isinstance(v, dict) else v
        return None
    return {"employees": sorted(emps)[-1][2] if emps else None, "industry_qid": first_id("P452"),
            "country_qid": first_id("P17"), "website": first_id("P856")}


def label(client, qid: str | None) -> str | None:
    if not qid:
        return None
    r = client.get(ENTITY.format(qid=qid), source="enrich_wikidata")
    if r is None or r.status_code != 200:
        return None
    return _entity(r.json(), qid).get("labels", {}).get("en", {}).get("value")


def pull(wh, accounts, since=None, client=None, seeds_dir=None, today: dt.date | None = None) -> int:
    today = today or dt.date.today()
    qids = {r["account_id"]: [q.strip() for q in (r.get("wikidata_qid") or "").split(";") if q.strip()]
            for r in read_csv("figma_customer_stories.csv", seeds_dir)}
    out = []
    for a in accounts:
        best = None
        for qid in qids.get(a["account_id"], []):
            r = client.get(ENTITY.format(qid=qid), source="enrich_wikidata")
            if r is None or r.status_code != 200:
                continue
            facts = {**parse_entity(_entity(r.json(), qid)), "qid": qid}
            if best is None or (best["employees"] is None and facts["employees"] is not None):
                best = facts
            if best["employees"] is not None:
                break
        if not best:
            continue
        out.append({"account_id": a["account_id"], "employees": best["employees"],
                    "employees_source_url": f"https://www.wikidata.org/wiki/{best['qid']}" if best["employees"] else None,
                    "employees_source": "wikidata" if best["employees"] else None,
                    "industry": label(client, best["industry_qid"]), "country": label(client, best["country_qid"]),
                    "website": best["website"], "qid": best["qid"], "retrieved_on": today})
    return replace_for_accounts(wh, "enrichment", [r["account_id"] for r in out], out)
