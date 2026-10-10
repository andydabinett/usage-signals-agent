import datetime as dt

import pytest

from signals import demo as dm
from signals import handoff as ho
from signals.scoring import as_of_from, score
from signals.warehouse import open_wh


def test_live_fixture_has_no_synthetic_rows(fixture_db):
    wh = open_wh(fixture_db, read_only=True)
    assert dm.mode_of(wh) == "live"
    assert wh.query("SELECT COUNT(*) AS n FROM signals WHERE is_synthetic")[0]["n"] == 0
    assert wh.query("SELECT COUNT(*) AS n FROM job_posts WHERE signal_id LIKE 'SYNTHETIC:%'")[0]["n"] == 0


def test_demo_rows_always_labeled_and_live_untouched(fixture_db, tmp_path):
    out = tmp_path / "demo.duckdb"
    live_before = open_wh(fixture_db, read_only=True).query("SELECT COUNT(*) AS n FROM job_posts")[0]["n"]
    wh0 = open_wh(fixture_db, read_only=True); a = as_of_from(wh0); wh0.close()
    dm.build(fixture_db, out, "acme", a)
    wh = open_wh(out, read_only=True)
    assert dm.mode_of(wh) == "demo"
    syn = wh.query("SELECT * FROM job_posts WHERE is_synthetic OR signal_id LIKE 'SYNTHETIC%' OR title LIKE '%SYNTHETIC%'")
    assert len(syn) == 1
    for r in syn:
        assert r["is_synthetic"] is True and r["signal_id"].startswith("SYNTHETIC:")
        assert r["title"].startswith("[SYNTHETIC]") and "example.invalid" in r["url"]
    facts = ho.build_facts(wh, "acme", a)
    assert "SYNTHETIC" in facts["addressed_to"] and any(s.get("synthetic") for s in facts["sources"])
    t = ho.template(facts)
    assert "SYNTHETIC" in t["addressed_to"] and "SYNTHETIC" in t["why_now"] and ho.check(t, facts)["ok"]
    # live warehouse unchanged
    assert open_wh(fixture_db, read_only=True).query("SELECT COUNT(*) AS n FROM job_posts")[0]["n"] == live_before


def test_unlabeled_synthetic_citation_rejected(fixture_db, tmp_path):
    out = tmp_path / "demo.duckdb"
    wh0 = open_wh(fixture_db, read_only=True); a = as_of_from(wh0); wh0.close()
    dm.build(fixture_db, out, "acme", a)
    facts = ho.build_facts(open_wh(out, read_only=True), "acme", a)
    t = ho.template(facts)
    t["why_now"] = t["why_now"].replace("SYNTHETIC demo signal: ", "")
    assert not ho.check(t, facts)["ok"]


def test_synthetic_row_in_live_warehouse_is_refused(fixture_db, tmp_path):
    import shutil
    p = tmp_path / "live.duckdb"; shutil.copyfile(fixture_db, p)
    wh = open_wh(p)
    wh.load_rows("job_posts", [{"signal_id": "SYNTHETIC:job:x", "account_id": "acme", "title": "[SYNTHETIC] x",
                                "url": "https://example.invalid/x", "published_on": dt.date(2026, 10, 1), "is_synthetic": True}])
    with pytest.raises(dm.SyntheticInLiveError):
        score(wh, dt.date(2026, 10, 10))
