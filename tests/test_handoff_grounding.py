"""Criterion 13 (unit part) + cached-handoff checks against the snapshot when it exists."""
import json

import httpx
import pytest
import respx

from signals import SNAPSHOT_DB
from signals import handoff as ho
from signals.warehouse import open_wh

FACTS = {
    "account_id": "acme", "account_name": "Acme Design", "as_of": "2026-10-10",
    "customer_story": {"url": "https://www.figma.com/customers/acme-story/", "title": "How Acme ships faster", "products_mentioned": "Make"},
    "score": {"total": 72, "growth_pts": 25, "breadth_pts": 12, "agent_pts": 20, "fit_pts": 10, "intent_pts": 15,
              "real": {"figma_make_or_ai_roles_30d": 1, "figma_roles_30d": 2, "real_signals_30d": 3},
              "proxy": {"weekly_events_w0": 410, "weekly_events_w1": 300, "wow_growth_pct": 37, "active_seats_w0": 14,
                        "paid_seats": 20, "agent_seats_w0": 4}},
    "enrichment": {"employees": 850, "industry": "software", "country": "United States"},
    "sources": [{"signal_id": "story:acme", "kind": "story", "date": None, "title": "How Acme ships faster", "url": "https://www.figma.com/customers/acme-story/"},
                {"signal_id": "job:greenhouse:101", "kind": "job_make", "date": "2026-10-02", "title": "Senior Product Designer",
                 "url": "https://boards.greenhouse.io/acme/jobs/101"}],
    "contacts": [{"role_title": "Head of Design", "source_url": "https://www.figma.com/customers/acme-story/"}],
}

GOOD = {
    "addressed_to": ho.ADDRESSED_TO,
    "why_this_account": "Acme Design is in a public Figma customer story about Figma Make [1].",
    "why_now": "On Oct 2 it posted a Senior Product Designer role that mentions Figma Make [2]. Weekly events grew 37% (proxy) [2].",
    "who_to_contact": [{"role_title": "Head of Design", "source_url": "https://www.figma.com/customers/acme-story/", "angle": "Agent rollout for prototyping"}],
    "suggested_first_line": "Noticed your team is hiring for Figma Make skills.",
    "citations": [{"n": 1, "signal_id": "story:acme", "url": "https://www.figma.com/customers/acme-story/"},
                  {"n": 2, "signal_id": "job:greenhouse:101", "url": "https://boards.greenhouse.io/acme/jobs/101"}],
    "numbers_cited": ["2", "37%"],
}


def mutate(**kw):
    return {**json.loads(json.dumps(GOOD)), **kw}


def test_good_passes():
    rep = ho.check(GOOD, FACTS)
    assert rep["ok"], rep["errors"]


def test_invented_number_rejected():
    rep = ho.check(mutate(why_now="Usage is up 35% (proxy) [2]."), FACTS)
    assert not rep["ok"] and any("35%" in e for e in rep["errors"])


def test_uncited_sentence_rejected():
    rep = ho.check(mutate(why_this_account="Acme Design is a great fit for the agent."), FACTS)
    assert not rep["ok"] and any("uncited" in e for e in rep["errors"])


def test_unlabeled_proxy_number_rejected():
    rep = ho.check(mutate(why_now="Weekly events grew 37% [2]."), FACTS)
    assert not rep["ok"] and any("proxy" in e for e in rep["errors"])


def test_url_not_in_facts_rejected():
    bad = mutate(citations=[{"n": 1, "signal_id": "story:acme", "url": "https://evil.example"},
                            {"n": 2, "signal_id": "job:greenhouse:101", "url": "https://boards.greenhouse.io/acme/jobs/101"}])
    assert not ho.check(bad, FACTS)["ok"]


def test_unknown_role_and_email_rejected():
    bad = mutate(who_to_contact=[{"role_title": "CEO", "source_url": "https://x", "angle": "email ceo@acme.example"}])
    errs = ho.check(bad, FACTS)["errors"]
    assert any("role_title" in e for e in errs) and any("@" in e for e in errs)


def test_template_fallback_is_grounded():
    assert ho.check(ho.template(FACTS), FACTS)["ok"]


def test_generate_retries_then_falls_back(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-a-key")
    bad = mutate(why_now="Usage is up 35% [2].")
    with respx.mock() as r:
        route = r.post(ho.OPENROUTER_URL).mock(return_value=httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(bad)}}], "usage": {"cost": 0.001}}))
        res = ho.generate(FACTS)
    assert route.call_count == 2 and res["mode"] == "template" and res["grounding"]["ok"]
    sent = json.loads(route.calls[0].request.content)
    assert sent["response_format"]["json_schema"]["strict"] is True and sent["reasoning"] == {"effort": "low"} and sent["max_tokens"] == 2000


@pytest.mark.skipif(not SNAPSHOT_DB.exists(), reason="PENDING: snapshot not frozen yet (needs manual review + `signals freeze`)")
def test_cached_snapshot_handoffs_pass_grounding():
    wh = open_wh(SNAPSHOT_DB, read_only=True)
    rows = wh.query("SELECT account_id FROM handoffs")
    assert rows
    for r in rows:
        h = ho.cached(wh, r["account_id"])
        assert ho.check(h["output"], h["facts"])["ok"], r["account_id"]
