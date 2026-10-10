"""Criteria 8 + 9: polite client."""
import httpx
import pytest
import respx

from conftest import make_client
from signals.http import ForbiddenHost, Robots, user_agent


def test_robots_disallowed_url_never_requested():
    with respx.mock(assert_all_called=False) as r:
        r.get("https://ex.test/robots.txt").mock(return_value=httpx.Response(200, text="User-agent: *\nDisallow: /private/*.json$\n"))
        hit = r.get("https://ex.test/private/a.json").mock(return_value=httpx.Response(200, json={}))
        ok = r.get("https://ex.test/private/a.html").mock(return_value=httpx.Response(200, text="hi"))
        c = make_client()
        assert c.get("https://ex.test/private/a.json") is None
        assert not hit.called
        assert c.get("https://ex.test/private/a.html").status_code == 200 and ok.called
        assert c.robots_skips == ["https://ex.test/private/a.json"]


def test_wildcard_matcher_longest_match():
    rb = Robots.parse("User-agent: *\nDisallow: /api/*\nAllow: /api/public/\nDisallow: /community/search?*\n")
    assert not rb.allowed("https://x/api/v1")
    assert rb.allowed("https://x/api/public/x")
    assert not rb.allowed("https://x/community/search?q=1")
    assert rb.allowed("https://x/customers/")


def test_same_host_spacing():
    with respx.mock(assert_all_called=False) as r:
        r.get("https://slow.test/robots.txt").mock(return_value=httpx.Response(404))
        r.get(url__regex=r"https://slow\.test/p\d").mock(return_value=httpx.Response(200, text="ok"))
        c = make_client(host_delays={"slow.test": 5.0})
        for i in range(3):
            c.get(f"https://slow.test/p{i}")
        times = [t for u, t in c.request_log if "/p" in u]
        assert all(b - a >= 5.0 for a, b in zip(times, times[1:]))


def test_user_agent_has_repo_and_email():
    with respx.mock(assert_all_called=False) as r:
        r.get("https://ua.test/robots.txt").mock(return_value=httpx.Response(404))
        route = r.get("https://ua.test/x").mock(return_value=httpx.Response(200))
        make_client().get("https://ua.test/x")
        ua = route.calls[0].request.headers["user-agent"]
        assert "https://github.com/andydabinett/usage-signals-agent" in ua and "test@example.com" in ua
        assert "Mozilla" not in ua
    assert user_agent("a@b.co").startswith("usage-signals-agent/0.1 (+https://github.com/andydabinett/usage-signals-agent; a@b.co)")


def test_403_recorded_not_retried():
    with respx.mock(assert_all_called=False) as r:
        r.get("https://deny.test/robots.txt").mock(return_value=httpx.Response(404))
        route = r.get("https://deny.test/x").mock(return_value=httpx.Response(403, text="Request blocked"))
        c = make_client()
        resp = c.get("https://deny.test/x")
        assert resp.status_code == 403 and route.call_count == 1
        assert any(e.startswith("403") for e in c.errors)


def test_429_backoff():
    with respx.mock(assert_all_called=False) as r:
        r.get("https://busy.test/robots.txt").mock(return_value=httpx.Response(404))
        route = r.get("https://busy.test/x").mock(side_effect=[httpx.Response(429), httpx.Response(429), httpx.Response(200, text="ok")])
        c = make_client()
        t0 = c._fake_time["now"]
        assert c.get("https://busy.test/x").status_code == 200
        assert route.call_count == 3
        assert c._fake_time["now"] - t0 >= 2.0 + 4.0  # exponential backoff slept


@pytest.mark.parametrize("url", ["https://www.figma.com/customers/", "https://figma.com/community", "https://api.figma.com/v1/x",
                                 "https://www.linkedin.com/company/x", "https://linkedin.com/in/x"])
def test_denylist_raises(url):
    with respx.mock(assert_all_called=False) as r:
        route = r.route().mock(return_value=httpx.Response(200))
        with pytest.raises(ForbiddenHost):
            make_client().get(url)
        assert not route.called


def test_redirect_into_denylist_blocked():
    with respx.mock(assert_all_called=False) as r:
        r.get("https://hop.test/robots.txt").mock(return_value=httpx.Response(404))
        r.get("https://hop.test/x").mock(return_value=httpx.Response(302, headers={"location": "https://www.figma.com/"}))
        with pytest.raises(ForbiddenHost):
            make_client().get("https://hop.test/x")


def test_wikidata_robots_entitydata_allowed_api_disallowed():
    from conftest import HTTP
    rb = Robots.parse((HTTP / "wikidata_robots.txt").read_text())
    assert rb.allowed("https://www.wikidata.org/wiki/Special:EntityData/Q2.json")
    assert not rb.allowed("https://www.wikidata.org/wiki/Special:EntityData/Q2")
    assert not rb.allowed("https://www.wikidata.org/w/api.php?action=wbsearchentities&search=x")
    assert not rb.allowed("https://www.wikidata.org/wiki/Special:Search")


def test_sec_user_agent_override_only_for_sec(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "Test Person test@example.com")
    with respx.mock(assert_all_called=False) as r:
        r.get(url__regex=r".*/robots\.txt$").mock(return_value=httpx.Response(404))
        sec = r.get("https://efts.sec.gov/x").mock(return_value=httpx.Response(200, json={}))
        other = r.get("https://ua.test/x").mock(return_value=httpx.Response(200))
        c = make_client()
        c.get("https://efts.sec.gov/x"); c.get("https://ua.test/x")
        assert sec.calls[0].request.headers["user-agent"] == "Test Person test@example.com"
        assert "usage-signals-agent" in other.calls[0].request.headers["user-agent"]
