from __future__ import annotations

import datetime as dt
import json
import socket
from pathlib import Path

import httpx
import pytest
import respx

from signals.warehouse import open_wh

FIX = Path(__file__).parent / "fixtures"
HTTP = FIX / "http"
SEEDS = FIX / "seeds"
AS_OF = dt.date(2026, 10, 10)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Socket guard: any real connection attempt fails the test (criterion 2)."""
    def guard(*a, **k):
        raise RuntimeError("network access attempted during tests")
    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket.socket, "connect_ex", guard)
    monkeypatch.setattr(socket, "create_connection", guard)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


def jload(name):
    return json.loads((HTTP / name).read_text())


def mock_all(router: respx.Router) -> None:
    router.get("https://www.wikidata.org/robots.txt").mock(return_value=httpx.Response(200, text=(HTTP / "wikidata_robots.txt").read_text()))
    router.get(url__regex=r".*/robots\.txt$").mock(return_value=httpx.Response(404))
    for q in ("Q1", "Q2", "Q30", "Q880371"):
        router.get(f"https://www.wikidata.org/wiki/Special:EntityData/{q}.json").mock(
            return_value=httpx.Response(200, json=jload(f"wikidata_entity_{q}.json")))
    router.get(url__regex=r"https://boards-api\.greenhouse\.io/v1/boards/acme/jobs.*").mock(return_value=httpx.Response(200, json=jload("greenhouse_jobs.json")))
    router.get(url__regex=r"https://api\.lever\.co/v0/postings/bolt.*").mock(return_value=httpx.Response(200, json=jload("lever_postings.json")))
    router.get(url__regex=r"https://api\.ashbyhq\.com/posting-api/job-board/acme.*").mock(return_value=httpx.Response(200, json=jload("ashby_jobs.json")))
    router.get("https://acme.example/").mock(return_value=httpx.Response(200, text=(HTTP / "website_home.html").read_text(), headers={"content-type": "text/html"}))
    router.get(url__regex=r"https://efts\.sec\.gov/LATEST/search-index.*Acme.*").mock(return_value=httpx.Response(200, json=jload("edgar_formd.json")))
    router.get(url__regex=r"https://efts\.sec\.gov/.*").mock(return_value=httpx.Response(200, json={"hits": {"hits": []}}))
    router.get(url__regex=r"https://api\.gdeltproject\.org/.*Acme.*").mock(return_value=httpx.Response(200, json=jload("gdelt_artlist.json")))
    router.get(url__regex=r"https://api\.gdeltproject\.org/.*").mock(return_value=httpx.Response(200, json={}))
    router.get(url__regex=r"https://hn\.algolia\.com/.*Acme.*").mock(return_value=httpx.Response(200, json=jload("hn_search.json")))
    router.get(url__regex=r"https://hn\.algolia\.com/.*").mock(return_value=httpx.Response(200, json={"hits": []}))
    router.route().mock(return_value=httpx.Response(404))


def make_client(wh=None, **kw):
    from signals.http import PoliteClient
    t = {"now": 0.0}
    def clock():
        return t["now"]
    def sleep(s):
        t["now"] += s
    c = PoliteClient(wh=wh, contact_email="test@example.com", sleep=sleep, clock=clock, **kw)
    c._fake_time = t
    return c


@pytest.fixture
def fixture_db(tmp_path):
    """A full warehouse built offline from recorded fixtures (seed + every ingest module + proxy)."""
    from signals.pipeline import refresh
    path = tmp_path / "wh.duckdb"
    wh = open_wh(path)
    with respx.mock(assert_all_called=False) as router:
        mock_all(router)
        refresh(wh, AS_OF, client=make_client(wh), log=lambda m: None, seeds_dir=SEEDS)
    wh.close()
    return path
