"""Clearly labeled DEMO SCENARIO: the same pipeline on a COPY of the live warehouse, with ONE synthetic spike injected on a
real account. Every synthetic row carries is_synthetic=TRUE, a 'SYNTHETIC:' signal_id, a '[SYNTHETIC]' title prefix and a
non-resolvable example.invalid URL; snapshot_meta.mode='demo'. Live warehouses must never contain synthetic rows."""
from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

from . import proxy
from .warehouse import open_wh

LABEL = "[SYNTHETIC]"
PREFIX = "SYNTHETIC:"


class SyntheticInLiveError(RuntimeError):
    pass


def mode_of(wh) -> str:
    rows = wh.query("SELECT mode FROM snapshot_meta")
    return (rows[0]["mode"] if rows and rows[0]["mode"] else "live")


def assert_live_clean(wh) -> None:
    """Raise if a live-mode warehouse contains any synthetic row."""
    if mode_of(wh) == "demo":
        return
    n = wh.query("SELECT COUNT(*) AS n FROM job_posts WHERE is_synthetic = TRUE OR signal_id LIKE 'SYNTHETIC:%'")[0]["n"]
    if n:
        raise SyntheticInLiveError(f"{n} synthetic row(s) found in a live-mode warehouse")


def build(live_db: Path, demo_db: Path, account_id: str, as_of: dt.date, days_ago: int = 3) -> dict:
    demo_db.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(live_db, demo_db)
    wh = open_wh(demo_db)
    d = as_of - dt.timedelta(days=days_ago)
    sid = f"{PREFIX}job:demo:{account_id}"
    wh.execute("DELETE FROM job_posts WHERE signal_id = %(s)s", {"s": sid})
    wh.load_rows("job_posts", [{
        "signal_id": sid, "account_id": account_id, "ats": "synthetic", "post_id": f"demo-{account_id}",
        "title": f"{LABEL} Demo scenario: Senior Product Designer, Figma Make prototyping",
        "url": f"https://example.invalid/synthetic/{account_id}", "published_on": d, "updated_on": d,
        "mentions_figma": True, "mentions_figma_make": True, "mentions_ai_prototyping": True,
        "excerpt": f"{LABEL} Injected for the demo scenario; not a real job post.", "is_synthetic": True}])
    from . import qualify as _q
    _q.apply(wh)
    proxy.build(wh, as_of)
    wh.execute("UPDATE snapshot_meta SET mode = 'demo'")
    wh.close()
    return {"signal_id": sid, "date": d.isoformat(), "account_id": account_id, "db": str(demo_db)}
