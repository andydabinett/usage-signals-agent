"""Criterion 11: proxy rows, hand-computed weekly totals, agent gating, lineage."""
import datetime as dt

from conftest import AS_OF
from signals import proxy
from signals.warehouse import open_wh

GA = dt.date(2026, 10, 6)


def _wh():
    wh = open_wh(":memory:")
    wh.load_rows("accounts", [{"account_id": "x", "account_name": "X", "products_mentioned": "Make"},
                              {"account_id": "y", "account_name": "Y", "products_mentioned": "Design"}])
    wh.load_rows("enrichment", [{"account_id": "x", "employees": 1000}])
    wh.load_rows("job_posts", [{"signal_id": "job:gh:1", "account_id": "x", "ats": "gh", "post_id": "1", "title": "Designer", "url": "https://j/1",
                                "published_on": dt.date(2026, 10, 7), "mentions_figma": True, "mentions_figma_make": True, "mentions_ai_prototyping": False}]
                 + [{"signal_id": f"job:gh:y{i}", "account_id": "y", "ats": "gh", "post_id": f"y{i}", "title": "Role", "url": f"https://j/y{i}",
                     "published_on": dt.date(2026, 9, 20) - dt.timedelta(days=i), "mentions_figma": False, "mentions_figma_make": False,
                     "mentions_ai_prototyping": False} for i in range(5)]
                 + [{"signal_id": "job:gh:y9", "account_id": "y", "ats": "gh", "post_id": "y9", "title": "Role", "url": "https://j/y9",
                     "published_on": dt.date(2026, 10, 1), "mentions_figma": False, "mentions_figma_make": False, "mentions_ai_prototyping": False}])
    wh.load_rows("funding", [{"signal_id": "fund:edgar:1", "account_id": "x", "source": "sec", "filed_on": dt.date(2026, 9, 30), "url": "https://sec/1"}])
    from signals import qualify
    qualify.apply(wh)
    proxy.build(wh, AS_OF)
    return wh


def weekly(wh, aid):
    rows = wh.query("SELECT usage_date, events, product FROM usage_daily WHERE account_id = %(a)s", {"a": aid})
    out = {}
    for r in rows:
        k = (AS_OF - r["usage_date"]).days // 7
        out[k] = out.get(k, 0) + r["events"]
    return out


def test_all_rows_are_proxy():
    wh = _wh()
    for t in ("seats", "usage_daily", "proxy_weeks"):
        assert wh.query(f"SELECT COUNT(*) AS n FROM {t} WHERE is_proxy IS NOT TRUE")[0]["n"] == 0
        assert wh.query(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"] > 0


def test_hand_computed_account_x():
    # paid=round(1000*0.02)=20, base_active=10, base_events=200.
    # W0: job_make(+0.6) + funding half(+0.25) = 0.85 -> make 370, active round(14.25)=14, agent ceil(3.5)=4 seats -> 40 events
    # W1: funding +0.5 -> 300 events, active 13 ; older weeks 200
    wh = _wh()
    w = weekly(wh, "x")
    assert w[0] == 370 + 40 and w[1] == 300 and all(w[k] == 200 for k in range(2, 8))
    a0 = wh.query("SELECT COUNT(DISTINCT seat_id) AS n FROM usage_daily WHERE account_id='x' AND usage_date >= '2026-10-04'")[0]["n"]
    assert a0 == 14
    first = wh.query("SELECT MIN(usage_date) AS d FROM usage_daily WHERE account_id='x' AND product='agent'")[0]["d"]
    assert first == dt.date(2026, 10, 7)


def test_hand_computed_account_y_velocity_drop():
    # employees NULL -> paid 20 (fit_unknown), base 10/200. Hiring: 5 roles 14-28d ago, 1 in last 14d -> -0.30 on W0.
    wh = _wh()
    w = weekly(wh, "y")
    assert w[0] == 140 and all(w[k] == 200 for k in range(1, 8))
    assert wh.query("SELECT COUNT(DISTINCT seat_id) AS n FROM usage_daily WHERE account_id='y' AND usage_date >= '2026-10-04'")[0]["n"] == 9


def test_agent_only_with_real_evidence():
    wh = _wh()
    assert wh.query("SELECT DISTINCT account_id FROM usage_daily WHERE product='agent'") == [{"account_id": "x"}]


def test_driver_ids_resolve_to_signals():
    wh = _wh()
    ids = {s for r in wh.query("SELECT DISTINCT driver_signal_ids AS d FROM usage_daily WHERE driver_signal_ids IS NOT NULL")
           for s in r["d"].split(",")}
    ids.discard("hiring_velocity_drop")
    known = {r["signal_id"] for r in wh.query("SELECT signal_id FROM signals")}
    assert ids and ids <= known


def test_distribute_exact():
    d = [dt.date(2026, 10, i) for i in (4, 5)]
    cells = proxy.distribute(7, d, ["s1", "s2"])
    assert sum(e for *_, e in cells) == 7 and cells[0] == (d[0], "s1", 2)
