"""5.10 — human-pasted search snippets (LinkedIn data ONLY this way, D13). Fills employees when Wikidata has none."""
from __future__ import annotations

import datetime as dt
import re

from .common import parse_date, read_csv

RANGE = re.compile(r"(\d[\d,]*)\s*[-–]\s*(\d[\d,]*)\s+employees", re.I)
PLUS = re.compile(r"(\d[\d,]*)\+\s+employees", re.I)


def parse_employees(snippet: str) -> int | None:
    m = RANGE.search(snippet or "")
    if m:
        lo, hi = (int(x.replace(",", "")) for x in m.groups())
        return (lo + hi) // 2
    m = PLUS.search(snippet or "")
    return int(m.group(1).replace(",", "")) if m else None


def pull(wh, accounts=None, since=None, client=None, seeds_dir=None) -> int:
    rows = read_csv("manual_snippets.csv", seeds_dir)
    wh.execute("DELETE FROM manual_snippets")
    n = wh.load_rows("manual_snippets", [{**r, "collected_on": parse_date(r["collected_on"])} for r in rows])
    for r in rows:
        if r["kind"] == "employees" and (emp := parse_employees(r["snippet"])):
            have = wh.query("SELECT employees FROM enrichment WHERE account_id = %(a)s", {"a": r["account_id"]})
            if not have:
                wh.load_rows("enrichment", [{"account_id": r["account_id"], "employees": emp, "employees_source_url": r["url"],
                                             "retrieved_on": parse_date(r["collected_on"]) or dt.date.today()}])
            elif have[0]["employees"] is None:
                wh.execute("UPDATE enrichment SET employees = %(e)s, employees_source_url = %(u)s WHERE account_id = %(a)s",
                           {"e": emp, "u": r["url"], "a": r["account_id"]})
        elif r["kind"] == "role_title":
            wh.load_rows("contacts", [{"account_id": r["account_id"], "role_title": r["snippet"][:120], "source_url": r["url"]}])
    return n
