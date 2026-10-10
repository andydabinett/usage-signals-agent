"""Scoring v2: real gates decide the flag; synthetic_12 proxy math is kept as CONTEXT ONLY and must never move a flag."""
import copy
import random
import shutil

from conftest import AS_OF, FIX
from signals.config import scoring_config
from signals.scoring import components, score, summary
from signals.warehouse import open_wh

CONTEXT = {  # id: (growth, breadth, agent) -- the v1 proxy table, now context only
    "A01": (25, 20, 20), "A09": (25, 20, 20), "A08": (25, 20, 20), "A10": (10, 12, 20),
    "A02": (18, 12, 20), "A03": (18, 4, 4), "A12": (0, 12, 12), "A04": (0, 20, 4),
    "A05": (0, 20, 0), "A06": (0, 4, 4), "A07": (0, 4, 0), "A11": (0, 0, 0),
}


def _wh():
    wh = open_wh(":memory:")
    wh.executescript((FIX / "synthetic_12.sql").read_text())
    return wh


def test_proxy_context_math_unchanged_but_not_in_total():
    rows = score(_wh(), AS_OF)
    assert {r["account_id"]: (r["growth_pts"], r["breadth_pts"], r["agent_pts"]) for r in rows} == CONTEXT
    for r in rows:
        assert r["total"] == r["hiring_pts"] + r["momentum_pts"] + r["fit_pts"] + r["intent_pts"]


def test_synthetic_12_has_no_real_hiring_so_nothing_flags():
    # v1 flagged A01/A09/A10/A02 purely on synthetic usage; under v2 synthetic usage alone can never flag.
    s = summary(score(_wh(), AS_OF), AS_OF)
    assert s["flagged"] == [] and s["at_risk"] == []


def _perturb(path, seed):
    wh = open_wh(path)
    rnd = random.Random(seed)
    wh.execute("UPDATE usage_daily SET events = CAST(events * %(m)s AS INTEGER) + %(a)s", {"m": rnd.uniform(0, 20), "a": rnd.randint(0, 500)})
    if seed % 2:
        wh.execute("DELETE FROM usage_daily WHERE product = 'agent'")
    if seed % 3 == 0:
        wh.execute("DELETE FROM seats")
    return wh


def test_changing_synthetic_values_never_changes_flag_outcome(fixture_db, tmp_path):
    base = {r["account_id"]: (r["flagged"], r["at_risk"], r["total"]) for r in score(open_wh(fixture_db, read_only=True), AS_OF)}
    assert any(f for f, _, _ in base.values()), "fixture should flag at least one account so the invariance test bites"
    for seed in range(6):
        p = tmp_path / f"w{seed}.duckdb"
        shutil.copyfile(fixture_db, p)
        wh = _perturb(p, seed)
        got = {r["account_id"]: (r["flagged"], r["at_risk"], r["total"]) for r in score(wh, AS_OF)}
        assert got == base, seed


def test_every_component_has_value_and_threshold(fixture_db):
    for r in score(open_wh(fixture_db, read_only=True), AS_OF):
        cs = components(r)
        assert [c["name"] for c in cs] == ["AI/design hiring", "Momentum", "Company fit", "Recent cited signal", "Public intent"]
        assert all(c["threshold"] and c["value"] for c in cs)
        assert r["flagged"] == all(c["ok"] for c in cs if c["ok"] is not None)


def test_threshold_change_needs_no_sql_edit(fixture_db):
    cfg = copy.deepcopy(scoring_config())
    cfg["real"]["gates"]["min_hiring_30d"] = 999
    assert not any(r["flagged"] for r in score(open_wh(fixture_db, read_only=True), AS_OF, cfg))
