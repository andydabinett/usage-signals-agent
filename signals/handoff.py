"""§9 cited handoffs + D8 grounding check (enforced in code). LLM via OpenRouter; cached in `handoffs`."""
from __future__ import annotations

import datetime as dt
import json
import os
import re

import httpx

from .scoring import score

ADDRESSED_TO = "For: PLG / unowned queue (demo)"
DEFAULT_MODEL = "anthropic/claude-sonnet-5.5"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
KIND_RANK = {"job_make": 0, "funding": 1, "news_funding": 2, "job_figma": 3, "news_launch": 4, "hn": 5, "news_layoffs": 6}
KIND_LABEL = {"job_make": "job post mentioning Figma Make / AI prototyping", "job_figma": "job post mentioning Figma",
              "funding": "SEC Form D funding filing", "news_funding": "funding news", "news_launch": "launch news",
              "news_layoffs": "layoffs news", "hn": "Hacker News mention", "story": "Figma customer story"}
MAX_WORDS = 120

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["addressed_to", "why_this_account", "why_now", "who_to_contact", "suggested_first_line", "citations", "numbers_cited"],
    "properties": {
        "addressed_to": {"type": "string"},
        "why_this_account": {"type": "string"},
        "why_now": {"type": "string"},
        "who_to_contact": {"type": "array", "minItems": 1, "maxItems": 2, "items": {
            "type": "object", "additionalProperties": False, "required": ["role_title", "source_url", "angle"],
            "properties": {"role_title": {"type": "string"}, "source_url": {"type": "string"}, "angle": {"type": "string"}}}},
        "suggested_first_line": {"type": "string"},
        "citations": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["n", "signal_id", "url"],
            "properties": {"n": {"type": "integer"}, "signal_id": {"type": "string"}, "url": {"type": "string"}}}},
        "numbers_cited": {"type": "array", "items": {"type": "string"}},
    },
}

SYSTEM = f"""You write a short sales handoff for a Figma rep about one account. Output JSON matching the schema.
Rules (enforced by code; violations are rejected):
- addressed_to must be exactly "{ADDRESSED_TO}".
- Total under {MAX_WORDS} words across why_this_account, why_now, suggested_first_line and angles.
- Every sentence in why_this_account and why_now ends with a citation like [1] whose n maps to an entry in `citations`;
  each citation's signal_id and url must be copied exactly from facts.sources.
- Use only numbers that appear in the facts. Any number from facts.score.proxy must be followed by "(proxy)".
- who_to_contact: 1-2 entries copied exactly from facts.contacts (role_title + source_url). Never name individuals.
- No emails, phone numbers or person names. Do not claim the account is a Figma customer beyond what its story shows.
- numbers_cited lists every number you used, as written."""


# ---------- facts ----------
def build_facts(wh, account_id: str, as_of: dt.date) -> dict:
    row = next(r for r in score(wh, as_of) if r["account_id"] == account_id)
    acct = wh.query("SELECT * FROM accounts WHERE account_id = %(a)s", {"a": account_id})[0]
    enr = (wh.query("SELECT employees, industry, country FROM enrichment WHERE account_id = %(a)s", {"a": account_id}) or [{}])[0]
    sigs = wh.query("SELECT signal_id, kind, signal_date, title, url FROM signals WHERE account_id = %(a)s AND url IS NOT NULL "
                    "AND signal_date <= %(as_of)s", {"a": account_id, "as_of": as_of})
    sigs.sort(key=lambda s: (KIND_RANK.get(s["kind"], 9), -(s["signal_date"].toordinal() if s["signal_date"] else 0)))
    sources = [{"signal_id": f"story:{account_id}", "kind": "story", "date": None, "title": acct["story_title"], "url": acct["story_url"]}]
    sources += [{"signal_id": s["signal_id"], "kind": s["kind"], "date": s["signal_date"].isoformat() if s["signal_date"] else None,
                 "title": s["title"], "url": s["url"]} for s in sigs[:6]]
    contacts = wh.query("SELECT role_title, source_url FROM contacts WHERE account_id = %(a)s ORDER BY role_title", {"a": account_id})[:2]
    g = float(row["g"])
    return {
        "account_id": account_id, "account_name": acct["account_name"], "as_of": as_of.isoformat(),
        "customer_story": {"url": acct["story_url"], "title": acct["story_title"], "products_mentioned": acct["products_mentioned"]},
        "score": {"total": int(row["total"]), "growth_pts": int(row["growth_pts"]), "breadth_pts": int(row["breadth_pts"]),
                  "agent_pts": int(row["agent_pts"]), "fit_pts": int(row["fit_pts"]), "intent_pts": int(row["intent_pts"]),
                  "real": {"figma_make_or_ai_roles_30d": int(row["make_roles"]), "figma_roles_30d": int(row["figma_roles"]),
                           "real_signals_30d": int(row["real_signals_30d"])},
                  "proxy": {"weekly_events_w0": int(row["e0"]), "weekly_events_w1": int(row["e1"]),
                            "wow_growth_pct": int(round(g * 100)), "active_seats_w0": int(row["active_w0"]),
                            "paid_seats": int(row["paid_seats"]), "agent_seats_w0": int(row["agent_seats_w0"])}},
        "enrichment": {k: enr.get(k) for k in ("employees", "industry", "country")},
        "sources": sources, "contacts": contacts,
    }


# ---------- grounding ----------
NUM_RX = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?%?")
CITE_RX = re.compile(r"\[(\d+)\]")
PHONE_RX = re.compile(r"\+?\d[\d\s().-]{7,}\d")
NAME_NEAR_ROLE = re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b,? (?:the |our |their )?(?:VP|Head|Director|Lead|Manager|Chief|CTO|CEO|CMO)")


def _norm_num(tok: str) -> str:
    t = tok.replace(",", "").rstrip("%")
    try:
        f = float(t)
        return str(int(f)) if f == int(f) else str(f)
    except ValueError:
        return t


def _walk_numbers(obj, out: set[str]) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            _walk_numbers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_numbers(v, out)
    elif isinstance(obj, bool) or obj is None:
        return
    elif isinstance(obj, (int, float)):
        out.add(_norm_num(str(obj)))
    elif isinstance(obj, str):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", obj):
            y, m, d = obj.split("-")
            out.update({y, str(int(m)), str(int(d))})
        for tok in NUM_RX.findall(obj):
            out.add(_norm_num(tok))


def allowed_numbers(facts: dict) -> tuple[set[str], set[str]]:
    real: set[str] = set()
    proxy: set[str] = set()
    f2 = json.loads(json.dumps(facts, default=str))
    _walk_numbers(f2["score"].pop("proxy"), proxy)
    _walk_numbers(f2, real)
    return real | proxy, proxy - real


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", text.strip()) if s.strip()]


def check(out: dict, facts: dict) -> dict:
    errors, warnings = [], []
    src = {s["signal_id"]: s["url"] for s in facts["sources"]}
    if out.get("addressed_to") != ADDRESSED_TO:
        errors.append("addressed_to must be the PLG / unowned queue")
    cites = {c["n"]: c for c in out.get("citations", [])}
    for c in cites.values():
        if c["signal_id"] not in src:
            errors.append(f"citation [{c['n']}] signal_id not in facts: {c['signal_id']}")
        elif c["url"] != src[c["signal_id"]]:
            errors.append(f"citation [{c['n']}] url not in facts: {c['url']}")
    for field in ("why_this_account", "why_now"):
        for s in sentences(out.get(field, "")):
            if not re.search(r"(\[\d+\])+[\s.!?\"')]*$", s):
                errors.append(f"uncited sentence in {field}: {s!r}")
    texts = [out.get("why_this_account", ""), out.get("why_now", ""), out.get("suggested_first_line", "")]
    texts += [w.get("angle", "") for w in out.get("who_to_contact", [])]
    full = " ".join(texts)
    for n in CITE_RX.findall(full):
        if int(n) not in cites:
            errors.append(f"[{n}] has no citation entry")
    allowed, proxy_only = allowed_numbers(facts)
    scrubbed = CITE_RX.sub(" ", full)
    for m in NUM_RX.finditer(scrubbed):
        tok = _norm_num(m.group(0))
        if tok not in allowed:
            errors.append(f"number not in facts allow-list: {m.group(0)}")
        elif tok in proxy_only and "(proxy)" not in scrubbed[m.end(): m.end() + 40]:
            errors.append(f"proxy number not labeled (proxy): {m.group(0)}")
    roles = {(c["role_title"], c["source_url"]) for c in facts["contacts"]}
    for w in out.get("who_to_contact", []):
        if (w["role_title"], w["source_url"]) not in roles:
            errors.append(f"role_title not in contacts: {w['role_title']}")
    if len(full.split()) > MAX_WORDS:
        errors.append(f"too long: {len(full.split())} words > {MAX_WORDS}")
    if "@" in full:
        errors.append("contains '@'")
    if PHONE_RX.search(re.sub(r"\d{4}-\d{2}-\d{2}", " ", scrubbed)):
        errors.append("contains a phone-like pattern")
    if NAME_NEAR_ROLE.search(full):
        warnings.append("possible person name next to a role (heuristic)")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


# ---------- generation ----------
def template(facts: dict) -> dict:
    srcs = facts["sources"]
    story = srcs[0]
    real = [s for s in srcs[1:]]
    cits = [{"n": 1, "signal_id": story["signal_id"], "url": story["url"]}]
    why_acct = f"{facts['account_name']} is featured in a public Figma customer story [1]."
    if real:
        top = real[0]
        cits.append({"n": 2, "signal_id": top["signal_id"], "url": top["url"]})
        why_now = f"Recent {KIND_LABEL.get(top['kind'], top['kind'])} dated {top['date']} [2]."
    else:
        why_now = "No dated public signal beyond the customer story [1]."
    who = [{"role_title": c["role_title"], "source_url": c["source_url"], "angle": "Figma agent rollout"} for c in facts["contacts"][:2]]
    return {"addressed_to": ADDRESSED_TO, "why_this_account": why_acct, "why_now": why_now, "who_to_contact": who,
            "suggested_first_line": "Saw your team's public Figma story and recent hiring; curious how the new Figma agent fits.",
            "citations": cits, "numbers_cited": []}


def call_llm(facts: dict, model: str, feedback: list[str] | None = None, transport=None) -> tuple[dict, float]:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set (needed only for handoff --refresh)")
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "facts:\n" + json.dumps(facts, default=str, indent=1)}]
    if feedback:
        msgs.append({"role": "user", "content": "Your previous answer was rejected by the grounding check:\n- " + "\n- ".join(feedback)
                     + "\nFix every issue and answer again."})
    body = {"model": model, "messages": msgs, "max_tokens": 2000, "reasoning": {"effort": "low"},
            "response_format": {"type": "json_schema", "json_schema": {"name": "handoff", "strict": True, "schema": SCHEMA}},
            "provider": {"require_parameters": True}, "usage": {"include": True}}
    with httpx.Client(timeout=120, transport=transport) as c:
        r = c.post(OPENROUTER_URL, json=body, headers={"Authorization": f"Bearer {key}", "X-Title": "usage-signals-agent"})
    if r.status_code != 200:
        raise RuntimeError(f"OpenRouter HTTP {r.status_code}: {r.text[:300]}")
    j = r.json()
    cost = float((j.get("usage") or {}).get("cost") or 0.0)
    return json.loads(j["choices"][0]["message"]["content"]), cost


def generate(facts: dict, model: str | None = None, transport=None) -> dict:
    model = model or os.environ.get("HANDOFF_MODEL") or DEFAULT_MODEL
    cost, feedback, attempts = 0.0, None, []
    for _ in range(2):  # D8: retry once, then template
        try:
            out, c = call_llm(facts, model, feedback, transport)
            cost += c
        except (RuntimeError, httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
            attempts.append({"error": str(e)[:300]})
            break
        rep = check(out, facts)
        attempts.append(rep)
        if rep["ok"]:
            return {"mode": "llm", "model": model, "output": out, "grounding": {**rep, "attempts": attempts}, "cost_usd": cost}
        feedback = rep["errors"]
    out = template(facts)
    rep = check(out, facts)
    return {"mode": "template", "model": model, "output": out, "grounding": {**rep, "attempts": attempts}, "cost_usd": cost}


def save(wh, account_id: str, facts: dict, res: dict) -> None:
    wh.execute("DELETE FROM handoffs WHERE account_id = %(a)s", {"a": account_id})
    wh.load_rows("handoffs", [{"account_id": account_id, "model": res["model"],
                               "created_at": dt.datetime.now(dt.timezone.utc).replace(tzinfo=None), "mode": res["mode"],
                               "facts_json": json.dumps(facts, default=str), "output_json": json.dumps(res["output"]),
                               "grounding_json": json.dumps(res["grounding"]), "cost_usd": res["cost_usd"]}])


def cached(wh, account_id: str) -> dict | None:
    rows = wh.query("SELECT * FROM handoffs WHERE account_id = %(a)s", {"a": account_id})
    if not rows:
        return None
    r = rows[0]
    return {**r, "facts": json.loads(r["facts_json"]), "output": json.loads(r["output_json"]), "grounding": json.loads(r["grounding_json"])}


def render_text(h: dict) -> str:
    o = h["output"]
    lines = [o["addressed_to"], "", "Why this account: " + o["why_this_account"], "Why now: " + o["why_now"], "Who to contact:"]
    lines += [f"  - {w['role_title']} ({w['source_url']}): {w['angle']}" for w in o["who_to_contact"]] or ["  - (no public role title on file)"]
    lines += ["First line: " + o["suggested_first_line"], "Citations:"]
    lines += [f"  [{c['n']}] {c['url']}" for c in o["citations"]]
    lines += [f"(mode: {h['mode']}, model: {h['model']})"]
    return "\n".join(lines)
