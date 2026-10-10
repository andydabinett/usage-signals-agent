"""Criterion 10: each ingest module + recorded fixture -> expected normalized rows."""
import datetime as dt

import httpx
import respx

from conftest import AS_OF, SEEDS, make_client, mock_all
from signals.ingest import (enrich_website, enrich_wikidata, figma_customers_seed, funding_edgar, jobs_ashby, jobs_greenhouse,
                            jobs_lever, manual_employees, manual_snippets, mentions_hn, news_gdelt)
from signals.warehouse import open_wh


def setup():
    wh = open_wh(":memory:")
    figma_customers_seed.pull(wh, seeds_dir=SEEDS)
    accts = wh.query("SELECT account_id, account_name, domain, products_mentioned FROM accounts ORDER BY account_id")
    return wh, accts


def run(mod, **kw):
    wh, accts = setup()
    with respx.mock(assert_all_called=False) as r:
        mock_all(r)
        n = mod.pull(wh, accts, None, client=make_client(wh), seeds_dir=SEEDS, **kw)
    return wh, n


def test_seed():
    wh, accts = setup()
    assert [a["account_id"] for a in accts] == ["acme", "bolt"]
    row = wh.query("SELECT * FROM accounts WHERE account_id='acme'")[0]
    assert row["owner_rep"] is None and row["products_mentioned"] == "Make"
    assert wh.query("SELECT role_title FROM contacts") == [{"role_title": "Head of Design"}]


def test_greenhouse():
    wh, n = run(jobs_greenhouse)
    rows = wh.query("SELECT * FROM job_posts ORDER BY post_id")
    assert n == 3
    a = rows[0]
    assert (a["post_id"], a["published_on"], a["mentions_figma"], a["mentions_figma_make"], a["mentions_ai_prototyping"]) == \
        ("101", dt.date(2026, 10, 2), True, True, True)
    assert "Figma Make" in a["excerpt"] and "[email]" in a["excerpt"] and "@" not in a["excerpt"]
    assert (rows[1]["mentions_figma"], rows[1]["mentions_figma_make"]) == (True, False)
    assert rows[2]["excerpt"] is None and not rows[2]["mentions_figma"]
    assert wh.query("SELECT COUNT(*) AS n FROM raw_pulls WHERE source='jobs_greenhouse'")[0]["n"] == 1


def test_lever():
    wh, n = run(jobs_lever)
    rows = wh.query("SELECT * FROM job_posts ORDER BY post_id")
    assert n == 2 and rows[0]["ats"] == "lever" and rows[0]["mentions_ai_prototyping"] and rows[0]["mentions_figma"]
    assert rows[0]["published_on"] == dt.datetime.fromtimestamp(1790000000, dt.timezone.utc).date()
    assert not rows[1]["mentions_figma"]


def test_ashby():
    wh, n = run(jobs_ashby)
    r = wh.query("SELECT * FROM job_posts")[0]
    assert n == 1 and r["signal_id"] == "job:ashby:ash-1" and r["published_on"] == dt.date(2026, 10, 5) and r["mentions_figma"]


def test_wikidata():
    wh, n = run(enrich_wikidata, today=AS_OF)
    r = wh.query("SELECT * FROM enrichment")[0]
    assert n == 1 and r["qid"] == "Q2" and r["employees"] == 850 and r["industry"] == "software industry"
    assert r["country"] == "United States" and r["employees_source"] == "wikidata"
    assert r["employees_source_url"] == "https://www.wikidata.org/wiki/Q2"


def test_website():
    wh, n = run(enrich_website, today=AS_OF)
    rows = wh.query("SELECT * FROM website_meta")
    assert n == 1 and rows[0]["page_title"] == "Acme Design" and rows[0]["ats_hint"] == "boards.greenhouse.io/acme"
    body = wh.query("SELECT body FROM raw_pulls WHERE source='enrich_website'")[0]["body"]
    assert "hello@acme.example" not in body and "[email]" in body


def test_edgar_exact_name_match():
    wh, n = run(funding_edgar, as_of=AS_OF)
    rows = wh.query("SELECT * FROM funding")
    assert n == 1 and rows[0]["filed_on"] == dt.date(2026, 9, 20)
    assert rows[0]["url"] == "https://www.sec.gov/Archives/edgar/data/1234567/000123456726000001/0001234567-26-000001-index.htm"


def test_gdelt():
    wh, n = run(news_gdelt)
    rows = {r["tag"]: r for r in wh.query("SELECT * FROM news")}
    assert n == 2 and rows["funding"]["seen_on"] == dt.date(2026, 10, 1) and rows["launch"]["seen_on"] == dt.date(2026, 9, 20)


def test_hn():
    wh, n = run(mentions_hn)
    r = wh.query("SELECT * FROM mentions")[0]
    assert n == 1 and r["url"] == "https://news.ycombinator.com/item?id=4242" and r["created_on"] == dt.date(2026, 10, 4)


def test_manual_snippets_employee_range():
    wh, _ = setup()
    n = manual_snippets.pull(wh, seeds_dir=SEEDS)
    assert n == 1
    assert wh.query("SELECT employees, employees_source_url FROM enrichment WHERE account_id='bolt'") == \
        [{"employees": 350, "employees_source_url": "https://www.example.com/search-result"}]
    assert manual_snippets.parse_employees("1,001-5,000 employees") == 3000


def test_wikidata_only_entitydata_path_is_requested():
    wh, accts = setup()
    with respx.mock(assert_all_called=False) as r:
        mock_all(r)
        c = make_client(wh)
        enrich_wikidata.pull(wh, accts, None, client=c, seeds_dir=SEEDS, today=AS_OF)
        urls = [str(call.request.url) for call in r.calls]
    assert all("/w/api.php" not in u and "query.wikidata.org" not in u for u in urls)
    assert c.robots_skips == []


def test_manual_employees_fill_only_missing():
    wh, _ = setup()
    wh.load_rows("enrichment", [{"account_id": "acme", "employees": 850, "employees_source": "wikidata"}])
    assert manual_employees.pull(wh, seeds_dir=SEEDS) == 1
    rows = {r["account_id"]: r for r in wh.query("SELECT * FROM enrichment")}
    assert rows["bolt"]["employees"] == 420 and rows["bolt"]["employees_source"] == "manual_public"
    assert rows["bolt"]["employees_source_url"] == "https://bolt.example/about"
    assert rows["acme"]["employees"] == 850


def test_edgar_stops_after_first_403():
    wh, accts = setup()
    with respx.mock(assert_all_called=False) as r:
        r.get(url__regex=r".*/robots\.txt$").mock(return_value=httpx.Response(404))
        route = r.get(url__regex=r"https://efts\.sec\.gov/LATEST/.*").mock(return_value=httpx.Response(403, text="Undeclared"))
        n = funding_edgar.pull(wh, accts, None, client=make_client(wh), seeds_dir=SEEDS, as_of=AS_OF)
    assert n == 0 and route.call_count == 1


def test_vibe_coding_boilerplate_without_design_context_is_ignored():
    from signals.ingest.common import match_flags
    tpm = ("Sr. Technical Program Manager. Build internal tools using AI coding assistants (\u201cvibe coding\u201d). "
           "Follow AI guidance for risk, governance, and safety-by-design.")
    assert match_flags(tpm)["mentions_ai_prototyping"] is False
    assert match_flags("Product Designer: explore ideas with AI prototyping and vibe coding.")["mentions_ai_prototyping"] is True
    assert match_flags("Engineer. Vibe coding prototypes with the design team in Figma.")["mentions_ai_prototyping"] is True
    assert match_flags("Data engineer. AI-prototyping of pipelines.")["mentions_ai_prototyping"] is False  # term is not its own context
    # the second Pinterest boilerplate variant: bare "prototype" is not design context
    tpm2 = "Prototype lightweight AI-powered helpers and tools (\u201cvibe coding\u201d) to improve signal quality monitoring."
    assert match_flags(tpm2)["mentions_ai_prototyping"] is False
    # design context far away from the term does not count
    far = "We partner with designers. " + "x " * 200 + "Use vibe coding for internal dashboards."
    assert match_flags(far)["mentions_ai_prototyping"] is False
