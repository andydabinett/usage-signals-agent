"""Hand-entered employee counts with a citable public source (company about/careers page, annual report, SEC 10-K).
Only fills accounts that still have no employee count after Wikidata. source=manual_public."""
from __future__ import annotations

import datetime as dt

from .common import parse_date, read_csv


def pull(wh, accounts=None, since=None, client=None, seeds_dir=None) -> int:
    n = 0
    for r in read_csv("manual_employees.csv", seeds_dir):
        if not r["employees"] or not r["source_url"]:
            continue
        emp = int(r["employees"].replace(",", ""))
        have = wh.query("SELECT employees FROM enrichment WHERE account_id = %(a)s", {"a": r["account_id"]})
        src = r.get("source") or "manual_public"
        if not have:
            wh.load_rows("enrichment", [{"account_id": r["account_id"], "employees": emp, "employees_source_url": r["source_url"],
                                         "employees_source": src, "retrieved_on": parse_date(r["collected_on"]) or dt.date.today()}])
            n += 1
        elif have[0]["employees"] is None:
            wh.execute("UPDATE enrichment SET employees = %(e)s, employees_source_url = %(u)s, employees_source = %(s)s "
                       "WHERE account_id = %(a)s", {"e": emp, "u": r["source_url"], "s": src, "a": r["account_id"]})
            n += 1
    return n
