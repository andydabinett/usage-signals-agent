"""Criteria 3 + 4. PENDING until Chief of Staff - Coding approves the manual review and `signals freeze` is run."""
import json

import pytest

from signals import EXPECTED_JSON, SNAPSHOT_DB
from signals.scoring import as_of_from, score, summary
from signals.warehouse import open_wh

pending = pytest.mark.skipif(not (SNAPSHOT_DB.exists() and EXPECTED_JSON.exists()),
                             reason="PENDING: snapshot/ not frozen yet — freeze only after the manual review is approved")


@pending
def test_score_json_equals_expected():
    exp = json.loads(EXPECTED_JSON.read_text())
    wh = open_wh(SNAPSHOT_DB, read_only=True)
    a = as_of_from(wh)
    got = summary(score(wh, a), a)
    assert {k: got[k] for k in ("flagged", "at_risk", "totals", "as_of")} == {k: exp[k] for k in ("flagged", "at_risk", "totals", "as_of")}


@pending
def test_every_flag_has_recent_real_job_or_funding_signal():
    import datetime as dt
    exp = json.loads(EXPECTED_JSON.read_text())
    wh = open_wh(SNAPSHOT_DB, read_only=True)
    a = dt.date.fromisoformat(exp["as_of"])
    for aid in exp["flagged"]:
        sigs = wh.query("SELECT kind, url FROM signals WHERE account_id = %(a)s AND url IS NOT NULL AND signal_date >= %(s)s "
                        "AND signal_date <= %(d)s", {"a": aid, "s": a - dt.timedelta(days=30), "d": a})
        assert sigs, aid
        assert any(s["kind"] in ("job_make", "job_figma", "job_agent_design", "funding") for s in sigs), aid
