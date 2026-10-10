"""Criterion 5: synthetic_12 scoring math matches the §7 table; weights live in YAML."""
import copy

from conftest import AS_OF, FIX
from signals.config import scoring_config
from signals.scoring import score, summary
from signals.warehouse import open_wh

EXPECTED = {  # id: (growth, breadth, agent, fit, total)
    "A01": (25, 20, 20, 20, 85), "A09": (25, 20, 20, 8, 73), "A08": (25, 20, 20, 0, 65), "A10": (10, 12, 20, 20, 62),
    "A02": (18, 12, 20, 10, 60), "A03": (18, 4, 4, 20, 46), "A12": (0, 12, 12, 20, 44), "A04": (0, 20, 4, 10, 34),
    "A05": (0, 20, 0, 10, 30), "A06": (0, 4, 4, 5, 13), "A07": (0, 4, 0, 5, 9), "A11": (0, 0, 0, 5, 5),
}


def _wh():
    wh = open_wh(":memory:")
    wh.executescript((FIX / "synthetic_12.sql").read_text())
    return wh


def test_fixture_table_exact():
    rows = score(_wh(), AS_OF)
    got = {r["account_id"]: (r["growth_pts"], r["breadth_pts"], r["agent_pts"], r["fit_pts"], r["total"]) for r in rows}
    assert got == EXPECTED
    assert all(r["intent_pts"] == 0 and r["real_signals_30d"] == 1 for r in rows)
    s = summary(rows, AS_OF)
    assert s["flagged"] == ["A01", "A09", "A10", "A02"]
    assert s["at_risk"] == ["A06", "A07"]


def test_weight_change_needs_no_sql_edit():
    cfg = copy.deepcopy(scoring_config())
    cfg["growth"]["p1"] = 30
    rows = {r["account_id"]: r for r in score(_wh(), AS_OF, cfg)}
    assert rows["A01"]["total"] == 90 and rows["A09"]["total"] == 78 and rows["A02"]["total"] == 60
