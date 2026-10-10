"""§6 synthetic usage proxy, seeded deterministically from REAL dated signals. Every row is is_proxy=TRUE."""
from __future__ import annotations

import datetime as dt
import math
import random

from .config import ga_date, scoring_config

WEEKS = 8
MULT = {"job_make": 0.60, "job_figma": 0.20, "funding": 0.50, "news_funding": 0.50,
        "news_launch": 0.20, "hn": 0.10, "news_layoffs": -0.40}
CAP, FLOOR = 1.5, -0.6
VELOCITY_PENALTY = -0.30
SEED = 20261006
VIEWERS = 3


def rhalf(x: float) -> int:
    return int(math.floor(x + 0.5))


def paid_seats_for(employees: int | None) -> tuple[int, bool]:
    if employees is None:
        return 20, True
    return max(5, min(400, rhalf(employees * 0.02))), False


def distribute(events: int, days: list[dt.date], seats: list[str]) -> list[tuple[dt.date, str, int]]:
    """Appendix A rule 3: cells = days asc × seats asc (day first); deal events round-robin. Exact sums."""
    cells = [(d, s) for d in days for s in seats]
    if not cells:
        assert events == 0, "events with no cells"
        return []
    assert events >= len(cells), f"events {events} < cells {len(cells)}"
    q, r = divmod(events, len(cells))
    return [(d, s, q + (1 if i < r else 0)) for i, (d, s) in enumerate(cells)]


def week_bounds(as_of: dt.date, k: int) -> tuple[dt.date, dt.date]:
    end = as_of - dt.timedelta(days=7 * k)
    return end - dt.timedelta(days=6), end


def multipliers(signals: list[dict], as_of: dt.date) -> tuple[list[float], list[list[str]]]:
    raw = [0.0] * WEEKS
    drivers: list[list[str]] = [[] for _ in range(WEEKS)]
    for s in signals:
        d, kind = s["signal_date"], s["kind"]
        if d is None or kind not in MULT or d > as_of:
            continue
        k = (as_of - d).days // 7
        if k >= WEEKS:
            continue
        raw[k] += MULT[kind]
        drivers[k].append(s["signal_id"])
        if k - 1 >= 0:  # following week at half strength
            raw[k - 1] += MULT[kind] / 2
            drivers[k - 1].append(s["signal_id"])
    return raw, drivers


def hiring_velocity_drop(post_dates: list[dt.date], as_of: dt.date) -> tuple[bool, int, int]:
    recent = sum(1 for d in post_dates if d and as_of - dt.timedelta(days=13) <= d <= as_of)
    prior = sum(1 for d in post_dates if d and as_of - dt.timedelta(days=27) <= d <= as_of - dt.timedelta(days=14))
    return (prior >= 4 and recent <= 0.5 * prior), recent, prior


def plan_account(acct: dict, employees: int | None, signals: list[dict], post_dates: list[dt.date],
                 as_of: dt.date, ga: dt.date) -> dict:
    paid, fit_unknown = paid_seats_for(employees)
    base_active = rhalf(0.5 * paid)
    base_events = base_active * 20
    raw, drivers = multipliers(signals, as_of)
    drop, recent, prior = hiring_velocity_drop(post_dates, as_of)
    if drop:
        raw[0] += VELOCITY_PENALTY
    mult = [max(FLOOR, min(CAP, m)) for m in raw]
    products = (acct.get("products_mentioned") or "").lower()
    make_ai = sorted(s["signal_date"] for s in signals if s["kind"] == "job_make" and s["signal_date"])
    evidence = any(p in products for p in ("make", "ai", "mcp")) or bool(make_ai)
    first_agent = None
    if evidence:
        after = [d for d in make_ai if d >= ga]
        first_agent = max(ga, after[0]) if after else ga + dt.timedelta(days=3)
        if first_agent > as_of:
            first_agent = None
    weeks = []
    for k in range(WEEKS):
        start, end = week_bounds(as_of, k)
        m = mult[k]
        active = max(1, min(paid, rhalf(base_active * (1 + 0.5 * m))))
        make_events = rhalf(base_events * (1 + m))
        agent_seats = agent_events = 0
        if first_agent and end >= first_agent:
            agent_seats = math.ceil(0.25 * active)
            agent_events = 10 * agent_seats
        weeks.append({"k": k, "start": start, "end": end, "multiplier": round(m, 4), "active": active,
                      "make_events": make_events, "agent_seats": agent_seats, "agent_events": agent_events,
                      "drivers": sorted(set(drivers[k])) + (["hiring_velocity_drop"] if k == 0 and drop else [])})
    return {"account_id": acct["account_id"], "paid_seats": paid, "fit_unknown": fit_unknown, "first_agent": first_agent,
            "evidence": evidence, "velocity": {"drop": drop, "recent_14d": recent, "prior_14_28d": prior}, "weeks": weeks}


def rows_for_plan(plan: dict) -> tuple[list[dict], list[dict], list[dict]]:
    aid = plan["account_id"]
    paid_ids = [f"{aid}-S{i:03d}" for i in range(1, plan["paid_seats"] + 1)]
    rng = random.Random(SEED)
    viewer_ids = [f"{aid}-V{i:03d}" for i in range(1, VIEWERS + 1)]
    rng.shuffle(viewer_ids)  # seed used only for seat-id shuffles (§6)
    seats = [{"account_id": aid, "seat_id": s, "seat_type": "paid", "is_proxy": True} for s in paid_ids]
    seats += [{"account_id": aid, "seat_id": s, "seat_type": "viewer", "is_proxy": True} for s in sorted(viewer_ids)]
    usage, weeks = [], []
    for w in plan["weeks"]:
        days = [w["start"] + dt.timedelta(days=i) for i in range(7)]
        active = paid_ids[: w["active"]]
        drv = ",".join(w["drivers"]) or None
        for d, s, e in distribute(w["make_events"], days, active):
            usage.append({"account_id": aid, "seat_id": s, "usage_date": d, "product": "make", "events": e,
                          "minutes": e * 3, "is_proxy": True, "driver_signal_ids": drv})
        if w["agent_seats"]:
            adays = [d for d in days if d >= plan["first_agent"]]
            for d, s, e in distribute(w["agent_events"], adays, active[: w["agent_seats"]]):
                usage.append({"account_id": aid, "seat_id": s, "usage_date": d, "product": "agent", "events": e,
                              "minutes": e * 3, "is_proxy": True, "driver_signal_ids": drv})
        weeks.append({"account_id": aid, "week_end": w["end"], "multiplier": w["multiplier"], "active_seats": w["active"],
                      "make_events": w["make_events"], "agent_seats": w["agent_seats"], "agent_events": w["agent_events"],
                      "driver_signal_ids": drv, "is_proxy": True})
    return seats, usage, weeks


def build(wh, as_of: dt.date, cfg: dict | None = None) -> dict:
    cfg = cfg or scoring_config()
    ga = ga_date(cfg)
    accts = wh.query("SELECT account_id, account_name, products_mentioned FROM accounts ORDER BY account_id")
    emp = {r["account_id"]: r["employees"] for r in wh.query("SELECT account_id, employees FROM enrichment")}
    sigs = wh.query("SELECT signal_id, account_id, kind, signal_date FROM signals")
    posts = wh.query("SELECT account_id, COALESCE(published_on, updated_on) AS d FROM job_posts")
    for t in ("seats", "usage_daily", "proxy_weeks"):
        wh.execute(f"DELETE FROM {t}")
    plans = {}
    for a in accts:
        aid = a["account_id"]
        plan = plan_account(a, emp.get(aid), [s for s in sigs if s["account_id"] == aid],
                            [p["d"] for p in posts if p["account_id"] == aid], as_of, ga)
        seats, usage, weeks = rows_for_plan(plan)
        wh.load_rows("seats", seats)
        wh.load_rows("usage_daily", usage)
        wh.load_rows("proxy_weeks", weeks)
        plans[aid] = plan
    return plans
