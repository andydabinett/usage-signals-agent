"""Post qualification + dedupe (CoS review, Oct 10). Threshold-neutral: decides WHICH posts count, not how many are needed.

A Figma-related post (mentions Figma / Figma Make / AI prototyping, or an agent-design title) QUALIFIES if:
  * it is a design role (product, UX/UI, visual, brand, motion, creative, art direction, illustration, design ops), or
  * its description is explicitly about AI prototyping, Figma Make, or designing for AI agents (any role), and
  * it is not an intern / internship role.
Engineering and other roles where Figma only appears as a listed tool do NOT qualify.
Dedupe: same account + normalized title within 14 days of the cluster's earliest post = one post; earliest date kept,
all URLs listed (dup_urls). date_basis = 'published' (first-published date) or 'updated' (only an updated date exists).
"""
from __future__ import annotations

import datetime as dt
import re

DEDUPE_DAYS = 14
RX_INTERN = re.compile(r"\bintern(ship)?s?\b|\bco-?op\b|\bapprentice", re.I)
RX_DESIGN_TITLE = re.compile(
    r"\bdesign(er|ers)?\b|\bux\b|\bui\b|\bcreative\b|\bart director\b|\billustrat\w*|\bmotion\b|\bbrand\b|\bvisual\b|"
    r"\bdesignops\b|\bcontent design\w*|\buser research\w*|\bconcepteur\w*|\bdise[nñ]ador\w*", re.I)
RX_NON_DESIGN_TITLE = re.compile(r"\b(engineer|engineering|developer|scientist|architect|analyst|counsel|accountant|sales|"
                                 r"account executive|recruiter)\b", re.I)
RX_DESIGN_ENG_OK = re.compile(r"\b(design|ux|ui) (engineer|technologist)\b", re.I)
RX_AGENT_DESIGN_DESC = re.compile(r"\bdesign(ing)? (for|of) (ai )?agents?\b|\bagent(ic)? (ux|experience|design|interfaces?)\b|"
                                  r"\bagentic design\b|\bdesigning agentic\b", re.I)
RX_AGENT_TITLE = re.compile(r"\bagent(s|ic)?\b", re.I)


def norm_title(t: str | None) -> str:
    t = re.sub(r"\(.*?\)", " ", (t or "").lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", t)).strip()


def is_design_role(title: str | None) -> bool:
    t = title or ""
    if not RX_DESIGN_TITLE.search(t):
        return False
    return not RX_NON_DESIGN_TITLE.search(t) or bool(RX_DESIGN_ENG_OK.search(t))


def classify(row: dict) -> dict:
    """Return role_class, qualifies, is_make_ai_agent and a reason for one job_posts row."""
    title, ex = row.get("title") or "", row.get("excerpt") or ""
    figma_related = bool(row.get("mentions_figma") or row.get("mentions_figma_make") or row.get("mentions_ai_prototyping")
                         or ("design" in title.lower() and RX_AGENT_TITLE.search(title)))
    explicit = bool(row.get("mentions_figma_make") or row.get("mentions_ai_prototyping") or RX_AGENT_DESIGN_DESC.search(ex))
    agent_design = ("design" in title.lower() and bool(RX_AGENT_TITLE.search(title))) or bool(RX_AGENT_DESIGN_DESC.search(ex))
    if not figma_related:
        return {"role_class": None, "qualifies": False, "is_make_ai_agent": False, "qual_reason": "not Figma-related"}
    if RX_INTERN.search(title):
        return {"role_class": "intern", "qualifies": False, "is_make_ai_agent": False, "qual_reason": "intern role excluded"}
    if is_design_role(title):
        return {"role_class": "design", "qualifies": True, "is_make_ai_agent": explicit or agent_design,
                "qual_reason": "design role"}
    if explicit:
        return {"role_class": "other", "qualifies": True, "is_make_ai_agent": True,
                "qual_reason": "description explicitly about AI prototyping / Figma Make / designing for AI agents"}
    return {"role_class": "other", "qualifies": False, "is_make_ai_agent": False,
            "qual_reason": "non-design role; Figma only a listed tool"}


def dedupe(rows: list[dict]) -> dict[str, dict]:
    """rows: qualifying posts with signal_id, account_id, title, url, d. Returns signal_id -> {dup_of, dup_urls}."""
    out: dict[str, dict] = {}
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault((r["account_id"], norm_title(r["title"])), []).append(r)
    for g in groups.values():
        g.sort(key=lambda r: (r["d"] or dt.date.max, r["signal_id"]))
        head = None
        for r in g:
            if head is not None and r["d"] and head["d"] and (r["d"] - head["d"]).days <= DEDUPE_DAYS:
                out[r["signal_id"]] = {"dup_of": head["signal_id"], "dup_urls": None}
                out[head["signal_id"]]["dup_urls"].append(r["url"])
            else:
                head = r
                out[r["signal_id"]] = {"dup_of": None, "dup_urls": [r["url"]]}
    return out


COLS = {"role_class": "VARCHAR", "qualifies": "BOOLEAN", "is_make_ai_agent": "BOOLEAN", "qual_reason": "VARCHAR",
        "date_basis": "VARCHAR", "dup_of": "VARCHAR", "dup_urls": "VARCHAR"}


def apply(wh) -> dict:
    for c, t in COLS.items():
        wh.execute(f"ALTER TABLE job_posts ADD COLUMN IF NOT EXISTS {c} {t}")
    rows = wh.query("SELECT signal_id, account_id, title, url, excerpt, published_on, updated_on, mentions_figma, "
                    "mentions_figma_make, mentions_ai_prototyping FROM job_posts")
    quals = []
    stats = {"figma_related": 0, "qualifying": 0, "dropped": {}, "deduped": 0}
    upd = []
    wh.execute("UPDATE job_posts SET role_class = NULL, qualifies = FALSE, is_make_ai_agent = FALSE, qual_reason = 'not Figma-related', "
               "dup_of = NULL, dup_urls = NULL, date_basis = CASE WHEN published_on IS NOT NULL THEN 'published' "
               "WHEN updated_on IS NOT NULL THEN 'updated' END")
    for r in rows:
        c = classify(r)
        basis = "published" if r["published_on"] else ("updated" if r["updated_on"] else None)
        d = r["published_on"] or r["updated_on"]
        if c["qual_reason"] != "not Figma-related":
            stats["figma_related"] += 1
            if not c["qualifies"]:
                stats["dropped"][c["qual_reason"]] = stats["dropped"].get(c["qual_reason"], 0) + 1
        if c["qualifies"]:
            quals.append({**r, "d": d})
        if c["qual_reason"] != "not Figma-related":
            upd.append((r["signal_id"], c, basis))
    dd = dedupe(quals)
    for sid, c, basis in upd:
        x = dd.get(sid, {"dup_of": None, "dup_urls": None})
        wh.execute("UPDATE job_posts SET role_class = %(rc)s, qualifies = %(q)s, is_make_ai_agent = %(m)s, qual_reason = %(why)s, "
                   "date_basis = %(b)s, dup_of = %(dup)s, dup_urls = %(urls)s WHERE signal_id = %(s)s",
                   {"rc": c["role_class"], "q": c["qualifies"], "m": c["is_make_ai_agent"], "why": c["qual_reason"], "b": basis,
                    "dup": x["dup_of"], "urls": " ".join(x["dup_urls"]) if x["dup_urls"] else None, "s": sid})
    from . import ROOT
    wh.executescript((ROOT / "sql" / "signals_view.sql").read_text())
    stats["qualifying"] = sum(1 for v in dd.values() if v["dup_of"] is None)
    stats["deduped"] = sum(1 for v in dd.values() if v["dup_of"])
    return stats
