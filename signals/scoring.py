from __future__ import annotations

import datetime as dt

from . import SQL_DIR
from .config import score_params, scoring_config


def as_of_from(wh, override: dt.date | None = None) -> dt.date:
    if override:
        return override
    rows = wh.query("SELECT as_of FROM snapshot_meta ORDER BY as_of DESC LIMIT 1")
    if not rows or rows[0]["as_of"] is None:
        raise RuntimeError("No as_of in snapshot_meta; pass --as-of (never CURRENT_DATE, D3)")
    return rows[0]["as_of"]


def score(wh, as_of: dt.date, cfg: dict | None = None) -> list[dict]:
    from .demo import assert_live_clean
    assert_live_clean(wh)  # synthetic rows may only exist in a demo-mode warehouse
    sql = (SQL_DIR / "score_accounts.sql").read_text()
    return wh.query(sql, score_params(as_of, cfg or scoring_config()))


def summary(rows: list[dict], as_of: dt.date) -> dict:
    return {
        "as_of": as_of.isoformat(),
        "flagged": [r["account_id"] for r in rows if r["flagged"]],
        "at_risk": [r["account_id"] for r in rows if r["at_risk"]],
        "totals": {r["account_id"]: int(r["total"]) for r in rows},
    }
