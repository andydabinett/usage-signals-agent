from __future__ import annotations

import datetime as dt
from functools import lru_cache
from pathlib import Path

import yaml

from . import CONFIG_DIR


@lru_cache
def load_yaml(name: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / name).read_text())


def scoring_config(path: Path | None = None) -> dict:
    if path is not None:
        return yaml.safe_load(Path(path).read_text())
    return load_yaml("scoring.yaml")


def ga_date(cfg: dict | None = None) -> dt.date:
    cfg = cfg or scoring_config()
    return dt.date.fromisoformat(str(cfg["ga_date"]))


def windows(as_of: dt.date) -> dict[str, dt.date]:
    """W0 = AS_OF-6..AS_OF, W1 = AS_OF-13..AS_OF-7 (D3: never CURRENT_DATE)."""
    return {
        "as_of": as_of,
        "w0_start": as_of - dt.timedelta(days=6),
        "w1_start": as_of - dt.timedelta(days=13),
        "w1_end": as_of - dt.timedelta(days=7),
    }


def score_params(as_of: dt.date, cfg: dict | None = None) -> dict:
    cfg = cfg or scoring_config()
    r = cfg["real"]
    p: dict = dict(windows(as_of))
    p["ga_date"] = dt.date.fromisoformat(str(cfg["ga_date"]))
    p["win_start"] = as_of - dt.timedelta(days=int(r["window_days"]))          # exclusive lower bound of the 30d window
    p["prior_start"] = as_of - dt.timedelta(days=int(r["window_days"]) + int(r["prior_days"]))
    p["prior_months"] = int(r["prior_days"]) / int(r["window_days"])
    p["intent_start"] = as_of - dt.timedelta(days=int(r["intent_days"]))
    p["funding_cutoff"] = as_of - dt.timedelta(days=int(r["funding_days"]))
    for k, v in r["gates"].items():
        p[f"gate_{k}"] = v
    pts = r["points"]
    for k in ("hiring_per_post", "hiring_post_cap", "hiring_make_bonus"):
        p[k] = pts[k]
    for sec in ("momentum", "fit", "intent"):
        for k, v in pts[sec].items():
            p[f"{sec}_{k}"] = v
    for k, v in r["cooling"].items():
        p[f"cooling_{k}"] = v
    for sec, d in cfg["context"].items():
        for k, v in d.items():
            p[f"{sec}_{k}"] = v
    return p
