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
    p: dict = dict(windows(as_of))
    p["ga_date"] = dt.date.fromisoformat(str(cfg["ga_date"]))
    p["intent_start"] = as_of - dt.timedelta(days=int(cfg["intent"]["window_days"]))
    p["funding_cutoff"] = as_of - dt.timedelta(days=int(cfg["fit"]["funding_days"]))
    for section in ("growth", "breadth", "agent", "fit", "intent", "flag", "at_risk"):
        for k, v in cfg[section].items():
            p[f"{section}_{k}"] = v
    return p
