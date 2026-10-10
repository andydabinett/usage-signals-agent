from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html
import re
from pathlib import Path

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from .. import SEEDS_DIR
from ..http import redact

RX_MAKE = re.compile(r"\bfigma make\b", re.I)
RX_AIPROTO = re.compile(r"\bai[- ]prototyp|\bvibe[- ]coding\b", re.I)
RX_FIGMA = re.compile(r"\bfigma\b", re.I)
# AI-prototyping / vibe-coding counts only with Figma or Figma Make anywhere in the post, or a DESIGN context within
# CTX_WINDOW chars of the term (Oct 10 tightening). Bare "prototype" is not design context: Pinterest TPM boilerplate
# ("Prototype lightweight AI-powered helpers ... ('vibe coding')", "AI coding assistants ('vibe coding')") must not count.
CTX_WINDOW = 150
RX_DESIGN_CTX = re.compile(r"\bux\b|\bui/ux\b|\bux/ui\b|\bwirefram\w*|\bmock-?ups?\b|\bproduct design\w*|"
                           r"\b(?:ux|ui|product|visual|interaction|brand) designers?\b|\bdesigners?\b|\bdesign systems?\b|"
                           r"\bdesign (?:prototyp\w*|team|crafts?|tools?)\b|\binteraction design\b|\bprototyp\w* (?:designs?|ui|ux|interfaces?|user flows?)\b", re.I)


def html_to_text(s: str | None) -> str:
    if not s:
        return ""
    s = html.unescape(s)  # Greenhouse content is HTML-escaped HTML
    try:
        text = HTMLParser(s).text(separator=" ")
    except Exception:
        text = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def ai_prototyping_in_context(text: str, figma_anywhere: bool | None = None) -> bool:
    """True only if an AI-prototyping/vibe-coding term appears AND (Figma/Figma Make appear anywhere in the post OR a
    design context appears within CTX_WINDOW chars of the term). The matched term is never its own context."""
    if not RX_AIPROTO.search(text):
        return False
    if figma_anywhere is None:
        figma_anywhere = bool(RX_FIGMA.search(text) or RX_MAKE.search(text))
    if figma_anywhere:
        return True
    for m in RX_AIPROTO.finditer(text):
        win = text[max(0, m.start() - CTX_WINDOW): m.start()] + " " + text[m.end(): m.end() + CTX_WINDOW]
        if RX_DESIGN_CTX.search(RX_AIPROTO.sub(" ", win)):
            return True
    return False


def match_flags(text: str) -> dict:
    return {
        "mentions_figma": bool(RX_FIGMA.search(text)),
        "mentions_figma_make": bool(RX_MAKE.search(text)),
        "mentions_ai_prototyping": ai_prototyping_in_context(text),
    }


def excerpt(text: str, width: int = 300) -> str | None:
    """The ~300 characters around each match (Make/AI first, then Figma), joined with ' … '."""
    spans = []
    for rx in (RX_MAKE, RX_AIPROTO, RX_FIGMA):
        for m in rx.finditer(text):
            a = max(0, m.start() - width // 2)
            b = min(len(text), m.end() + width // 2)
            if not any(a < y and b > x for x, y in spans):
                spans.append((a, b))
    if not spans:
        return None
    return redact(" … ".join(text[a:b].strip() for a, b in sorted(spans)[:3]))


def parse_date(v) -> dt.date | None:
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):  # epoch ms (Lever)
        return dt.datetime.fromtimestamp(v / 1000, dt.timezone.utc).date()
    s = str(v)
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y%m%dT%H%M%SZ", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s if fmt != "%Y-%m-%d" else s[:10], fmt).date()
        except ValueError:
            pass
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def short_hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:10]


def read_csv(name: str, seeds_dir: Path | None = None) -> list[dict]:
    p = (seeds_dir or SEEDS_DIR) / name
    with p.open(newline="") as f:
        return [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def ats_slugs(ats: str, seeds_dir: Path | None = None) -> dict[str, str]:
    return {r["account_id"]: r["slug"] for r in read_csv("ats_slugs.csv", seeds_dir) if r["ats"] == ats and r["slug"]}


def replace_for_accounts(wh, table: str, account_ids: list[str], rows: list[dict], extra_where: str = "") -> int:
    for a in account_ids:
        wh.execute(f"DELETE FROM {table} WHERE account_id = %(a)s {extra_where}", {"a": a})
    return wh.load_rows(table, rows)


def job_row(account_id, ats, post_id, title, url, published, updated, text) -> dict:
    flags = match_flags(text)
    return {
        "signal_id": f"job:{ats}:{post_id}", "account_id": account_id, "ats": ats, "post_id": str(post_id),
        "title": title, "url": url, "published_on": published, "updated_on": updated, **flags,
        "excerpt": excerpt(text) if any(flags.values()) else None,
    }
