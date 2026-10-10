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


def components(r: dict, cfg: dict | None = None) -> list[dict]:
    """Every REAL sub-score with its value, threshold and pass/fail (gates decide the flag; points only rank)."""
    from .config import scoring_config
    g = (cfg or scoring_config())["real"]["gates"]
    return [
        {"name": "AI/design hiring", "kind": "real", "pts": int(r["hiring_pts"]),
         "value": f"{r['hire_30d']} qualifying posts in 30d ({r['hire_make_30d']} Make/AI/agent-design)",
         "threshold": f">= {g['min_hiring_30d']} posts", "ok": bool(r["gate_hiring"])},
        {"name": "Momentum", "kind": "real", "pts": int(r["momentum_pts"]),
         "value": f"30d {r['hire_30d']} vs prior-60d {r['hire_prior60']} ({float(r['baseline_30d']):.1f}/mo); ratio {float(r['momentum_ratio']):.2f}",
         "threshold": f"ratio >= {g['min_momentum_ratio']} (baseline floored at {g['momentum_floor']}/mo)", "ok": bool(r["gate_momentum"])},
        {"name": "Company fit", "kind": "real", "pts": int(r["fit_pts"]),
         "value": f"employees {r['employees'] if r['employees'] is not None else 'unknown'} ({r['employees_source'] or 'no allowed source'})",
         "threshold": f">= {g['min_employees']} (wikidata or manual_public)", "ok": bool(r["gate_fit"])},
        {"name": "Recent cited signal", "kind": "real", "pts": 0,
         "value": f"{r['real_signals_30d']} real cited signals in 30d (latest {r['latest_real_signal'] or '-'})",
         "threshold": f">= {g['min_recent_real_cited']}", "ok": bool(r["gate_recent"])},
        {"name": "Public intent", "kind": "real", "pts": int(r["intent_pts"]),
         "value": f"HN mentions 90d {r['hn_90d']}; Form D 180d {'yes' if r['formd_180d'] else 'no'}",
         "threshold": "ranking only (not a gate)", "ok": None},
    ]


def context(r: dict) -> list[dict]:
    """SYNTHETIC stand-ins: shown for context, never part of total, flag or at-risk."""
    return [
        {"name": "Usage growth WoW", "pts": int(r["growth_pts"]), "value": f"E0={r['e0']} E1={r['e1']} g={float(r['g']):+.2f}"},
        {"name": "Seat breadth", "pts": int(r["breadth_pts"]), "value": f"{r['active_w0']}/{r['paid_seats']} active"},
        {"name": "Agent adoption", "pts": int(r["agent_pts"]), "value": f"{r['agent_seats_w0']} agent seats (first {r['first_agent_date'] or '-'})"},
    ]
