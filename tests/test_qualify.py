import datetime as dt

from signals import handoff as ho
from signals import qualify as q
from signals.warehouse import open_wh


def row(title, excerpt="Experience with Figma.", **kw):
    return {"title": title, "excerpt": excerpt, "mentions_figma": True, "mentions_figma_make": False,
            "mentions_ai_prototyping": False, **kw}


def test_lyft_cases_excluded():
    intern = q.classify(row("Content Systems Intern (Summer 2027)", "Nice to haves: Experience with design tools (Figma)"))
    ios = q.classify(row("Senior Software Engineer - iOS", "Familiarity with current design and prototyping tools (Figma, etc)."))
    assert not intern["qualifies"] and intern["qual_reason"] == "intern role excluded"
    assert not ios["qualifies"] and "listed tool" in ios["qual_reason"]


def test_okta_lead_ai_engineer_excluded_but_explicit_description_counts():
    ex = "Deep expertise interacting with REST/GraphQL APIs for enterprise developer tools (Jira, GitHub/GitLab, Figma, CI/CD platforms)."
    assert not q.classify(row("Lead AI Engineer", ex))["qualifies"]
    ok = q.classify(row("Lead AI Engineer", "You will lead designing for AI agents with our design team in Figma."))
    assert ok["qualifies"] and ok["is_make_ai_agent"]
    assert q.classify(row("Frontend Engineer", "Build with Figma Make.", mentions_figma_make=True))["qualifies"]


def test_design_roles_qualify():
    for t in ("Senior Art Director, Demand Gen", "Staff UX Designer", "Sr. Motion Designer", "Associate Creative Director, Digital Design",
              "Senior Design Operations Program Manager - Agentic Design", "Brand Designer", "Senior Digital Designer",
              "Senior Product Designer - Okta for AI Agents", "Design Engineer", "Concepteur de Produits - Technologie des opérations"):
        assert q.classify(row(t))["qualifies"], t
    assert q.classify(row("Senior Product Designer - Okta for AI Agents"))["is_make_ai_agent"]
    assert not q.classify(row("Sr Software Engineer II - Ads Manager (Front End)"))["qualifies"]
    assert not q.classify(row("Design Intern"))["qualifies"]


def test_dedupe_same_title_within_14_days():
    rows = [{"signal_id": "a", "account_id": "s", "title": "Associate Creative Director, Digital Design", "url": "u1", "d": dt.date(2026, 9, 24)},
            {"signal_id": "b", "account_id": "s", "title": "Associate Creative Director - Digital Design (Remote)", "url": "u2", "d": dt.date(2026, 10, 2)},
            {"signal_id": "c", "account_id": "s", "title": "Associate Creative Director, Digital Design", "url": "u3", "d": dt.date(2026, 11, 2)},
            {"signal_id": "d", "account_id": "t", "title": "Associate Creative Director, Digital Design", "url": "u4", "d": dt.date(2026, 9, 25)}]
    out = q.dedupe(rows)
    assert out["a"] == {"dup_of": None, "dup_urls": ["u1", "u2"]} and out["b"]["dup_of"] == "a"
    assert out["c"]["dup_of"] is None and out["d"]["dup_of"] is None  # >14 days later / other company


def _wh():
    wh = open_wh(":memory:")
    wh.load_rows("accounts", [{"account_id": "s", "account_name": "S", "story_url": "https://s.example/story", "story_title": "Story"}])
    wh.load_rows("enrichment", [{"account_id": "s", "employees": 1000, "employees_source": "manual_public"}])
    base = {"account_id": "s", "ats": "greenhouse", "mentions_figma": True, "mentions_figma_make": False, "mentions_ai_prototyping": False}
    wh.load_rows("job_posts", [
        {**base, "signal_id": "job:gh:1", "post_id": "1", "title": "Brand Designer", "url": "https://j/1", "published_on": dt.date(2026, 9, 24), "updated_on": dt.date(2026, 9, 24)},
        {**base, "signal_id": "job:gh:2", "post_id": "2", "title": "Brand Designer", "url": "https://j/2", "published_on": dt.date(2026, 10, 2), "updated_on": dt.date(2026, 10, 2)},
        {**base, "signal_id": "job:gh:3", "post_id": "3", "title": "UX Designer", "url": "https://j/3", "published_on": None, "updated_on": dt.date(2026, 10, 5)},
        {**base, "signal_id": "job:gh:4", "post_id": "4", "title": "Design Intern", "url": "https://j/4", "published_on": dt.date(2026, 10, 5), "updated_on": dt.date(2026, 10, 5)}])
    from signals import proxy
    q.apply(wh)
    proxy.build(wh, dt.date(2026, 10, 10))
    return wh


def test_scoring_counts_deduped_qualifying_posts_and_date_basis():
    from signals.scoring import score
    wh = _wh()
    r = next(x for x in score(wh, dt.date(2026, 10, 10)) if x["account_id"] == "s")
    assert r["hire_30d"] == 2  # Brand Designer x2 -> 1 (earliest kept), UX Designer 1, intern excluded
    sig = {s["signal_id"]: s for s in wh.query("SELECT * FROM signals WHERE account_id = 's'")}
    assert set(sig) == {"job:gh:1", "job:gh:3"} and sig["job:gh:1"]["dup_urls"] == "https://j/1 https://j/2"
    assert sig["job:gh:3"]["date_basis"] == "updated" and sig["job:gh:1"]["date_basis"] == "published"
    facts = ho.build_facts(wh, "s", dt.date(2026, 10, 10))
    src = {s["signal_id"]: s for s in facts["sources"]}
    assert src["job:gh:3"]["date_basis"] == "updated" and src["job:gh:1"]["also_posted_at"] == ["https://j/2"]
    t = ho.template(facts)
    assert "updated 2026-10-05" in t["why_now"] and ho.check(t, facts)["ok"]
    bad = dict(t, why_now="A UX Designer role was posted on 2026-10-05 [2].")
    assert any("updated on" in e for e in ho.check(bad, facts)["errors"])
