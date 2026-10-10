from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer

from . import DATA_DB, EXPECTED_JSON, ROOT, SNAPSHOT_DB
from . import handoff as ho
from . import web as webmod
from .scoring import as_of_from, score, summary
from .warehouse import open_wh

app = typer.Typer(add_completion=False, help="Usage Signals Agent (warehouse-first scoring + cited handoffs)")
DB = typer.Option(None, "--db", help="Warehouse file (default: snapshot/warehouse.duckdb)")
ASOF = typer.Option(None, "--as-of", help="Override AS_OF (YYYY-MM-DD)")


def _db(db: Optional[Path]) -> Path:
    p = db or SNAPSHOT_DB
    if not p.exists():
        typer.echo(f"No warehouse at {p}. Run `signals refresh` (writes {DATA_DB}) and pass --db, or `signals freeze`.", err=True)
        raise typer.Exit(2)
    return p


def _asof(v: Optional[str]) -> Optional[dt.date]:
    return dt.date.fromisoformat(v) if v else None


@app.command()
def refresh(only: Optional[str] = typer.Option(None, "--only"), since: Optional[str] = typer.Option(None, "--since"),
            as_of: Optional[str] = ASOF, db: Path = typer.Option(DATA_DB, "--db")):
    """ONLINE: pull every §5 source through the polite client, then rebuild the proxy. Needs CONTACT_EMAIL."""
    if not os.environ.get("CONTACT_EMAIL"):
        typer.echo("CONTACT_EMAIL is required (SEC fair-access policy). Set it in .env / the environment.", err=True)
        raise typer.Exit(2)
    from .pipeline import refresh as run
    wh = open_wh(db)
    res = run(wh, _asof(as_of) or dt.date.today(), only=only, since=_asof(since))
    wh.close()
    typer.echo(json.dumps(res, indent=1, default=str))


@app.command()
def freeze(db: Path = typer.Option(DATA_DB, "--db")):
    """Copy data/warehouse.duckdb -> snapshot/, write snapshot/expected.json, print a diff. Run only after human review."""
    old = json.loads(EXPECTED_JSON.read_text()) if EXPECTED_JSON.exists() else {}
    wh = open_wh(db)
    a = as_of_from(wh)
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or None
    except OSError:
        sha = None
    meta = wh.query("SELECT source_counts FROM snapshot_meta")[0]
    wh.execute("UPDATE snapshot_meta SET frozen_at = %(t)s, git_sha = %(g)s",
               {"t": dt.datetime.now(dt.timezone.utc).replace(tzinfo=None), "g": sha})
    new = {**summary(score(wh, a), a), "source_counts": json.loads(meta["source_counts"] or "{}")}
    wh.close()
    SNAPSHOT_DB.parent.mkdir(exist_ok=True)
    shutil.copyfile(db, SNAPSHOT_DB)
    EXPECTED_JSON.write_text(json.dumps(new, indent=2, sort_keys=True) + "\n")
    for k in ("flagged", "at_risk"):
        if old.get(k) != new[k]:
            typer.echo(f"{k}: {old.get(k)} -> {new[k]}")
    typer.echo(f"frozen as_of={a}")


@app.command("score")
def score_cmd(all_: bool = typer.Option(False, "--all"), as_json: bool = typer.Option(False, "--json"),
              db: Optional[Path] = DB, as_of: Optional[str] = ASOF):
    """OFFLINE: rules-only score from the warehouse."""
    wh = open_wh(_db(db), read_only=True)
    a = as_of_from(wh, _asof(as_of))
    rows = score(wh, a)
    if as_json:
        typer.echo(json.dumps(summary(rows, a), indent=2, sort_keys=True))
        return
    typer.echo(f"AS_OF {a}   (growth/breadth/agent = proxy; fit/intent = real)")
    typer.echo(f"{'account':<16}{'total':>6}{'grow':>6}{'brdth':>6}{'agent':>6}{'fit':>5}{'int':>5}{'sig30':>6}  status")
    for r in rows:
        st = "FLAG" if r["flagged"] else ("AT RISK" if r["at_risk"] else "")
        if all_ or st:
            typer.echo(f"{r['account_id']:<16}{r['total']:>6}{r['growth_pts']:>6}{r['breadth_pts']:>6}{r['agent_pts']:>6}"
                       f"{r['fit_pts']:>5}{r['intent_pts']:>5}{r['real_signals_30d']:>6}  {st}")


@app.command()
def explain(account_id: str, db: Optional[Path] = DB, as_of: Optional[str] = ASOF):
    """Components, real signals with URLs, proxy lineage and the flag-clause evaluation."""
    from .config import scoring_config
    wh = open_wh(_db(db), read_only=True)
    a = as_of_from(wh, _asof(as_of))
    rows = {r["account_id"]: r for r in score(wh, a)}
    if account_id not in rows:
        typer.echo(f"unknown account {account_id}", err=True)
        raise typer.Exit(1)
    r, cfg = rows[account_id], scoring_config()
    acct = wh.query("SELECT * FROM accounts WHERE account_id = %(a)s", {"a": account_id})[0]
    typer.echo(f"{acct['account_name']} ({account_id})  AS_OF {a}\nStory: {acct['story_title']}\n  {acct['story_url']}")
    typer.echo(f"\nComponents (total {r['total']}):")
    typer.echo(f"  growth  {r['growth_pts']:>3}  [proxy] E0={r['e0']} E1={r['e1']} g={float(r['g']):+.3f}")
    typer.echo(f"  breadth {r['breadth_pts']:>3}  [proxy] active_w0={r['active_w0']} paid={r['paid_seats']} b={float(r['b']):.3f}")
    typer.echo(f"  agent   {r['agent_pts']:>3}  [proxy] agent_seats_w0={r['agent_seats_w0']} first_agent={r['first_agent_date']}")
    typer.echo(f"  fit     {r['fit_pts']:>3}  [real]  employees={r['employees']} last_funding={r['last_funding']}")
    typer.echo(f"  intent  {r['intent_pts']:>3}  [real]  make/ai roles 30d={r['make_roles']} figma roles 30d={r['figma_roles']}")
    sigs = wh.query("SELECT signal_id, kind, signal_date, title, url FROM signals WHERE account_id = %(a)s AND signal_date <= %(d)s "
                    "ORDER BY signal_date DESC", {"a": account_id, "d": a})
    typer.echo(f"\nReal signals ({len(sigs)}):")
    for s in sigs[:25]:
        typer.echo(f"  {s['signal_date']}  {s['kind']:<13} {s['signal_id']}\n      {s['title']}\n      {s['url']}")
    if len(sigs) > 25:
        typer.echo(f"  … {len(sigs) - 25} more")
    typer.echo("\nProxy lineage (weeks; is_proxy=TRUE):")
    for w in wh.query("SELECT * FROM proxy_weeks WHERE account_id = %(a)s ORDER BY week_end", {"a": account_id}):
        typer.echo(f"  week ending {w['week_end']}  mult={w['multiplier']:+.2f} active={w['active_seats']} make={w['make_events']} "
                   f"agent={w['agent_events']}  drivers={w['driver_signal_ids'] or '-'}")
    f = cfg["flag"]
    typer.echo("\nFlag clauses:")
    for name, ok in [(f"total {r['total']} >= {f['min_total']}", r["total"] >= f["min_total"]),
                     (f"growth_pts {r['growth_pts']} >= {f['min_growth']}", r["growth_pts"] >= f["min_growth"]),
                     (f"fit_pts {r['fit_pts']} >= {f['min_fit']}", r["fit_pts"] >= f["min_fit"]),
                     (f"real_signals_30d {r['real_signals_30d']} >= {f['min_real_signals']}", r["real_signals_30d"] >= f["min_real_signals"])]:
        typer.echo(f"  [{'x' if ok else ' '}] {name}")
    typer.echo(f"  => {'FLAGGED' if r['flagged'] else 'not flagged'}{' / AT RISK' if r['at_risk'] else ''}")


@app.command()
def handoff(account_id: Optional[str] = typer.Argument(None), refresh: bool = typer.Option(False, "--refresh"),
            db: Optional[Path] = DB, as_of: Optional[str] = ASOF):
    """Cited handoff(s). Offline from cache; --refresh calls OpenRouter (needs OPENROUTER_API_KEY)."""
    path = _db(db)
    wh = open_wh(path, read_only=not refresh)
    a = as_of_from(wh, _asof(as_of))
    ids = [account_id] if account_id else [r["account_id"] for r in score(wh, a) if r["flagged"]]
    total_cost = 0.0
    for aid in ids:
        if refresh:
            facts = ho.build_facts(wh, aid, a)
            res = ho.generate(facts)
            ho.save(wh, aid, facts, res)
            total_cost += res["cost_usd"]
        h = ho.cached(wh, aid)
        if not h:
            typer.echo(f"{aid}: no cached handoff (run with --refresh online)")
            continue
        typer.echo(f"=== {aid} ===\n{ho.render_text(h)}\ngrounding: {'PASS' if h['grounding']['ok'] else 'FAIL ' + str(h['grounding']['errors'])}\n")
    if refresh:
        typer.echo(f"LLM cost this run: ${total_cost:.4f}")
    wh.close()


@app.command()
def web(db: Optional[Path] = DB, out: Path = typer.Option(ROOT / "out" / "index.html", "--out"), as_of: Optional[str] = ASOF):
    """Write a self-contained out/index.html."""
    wh = open_wh(_db(db), read_only=True)
    a = as_of_from(wh, _asof(as_of))
    p = webmod.render(wh, score(wh, a), a, out)
    typer.echo(f"wrote {p}")


if __name__ == "__main__":
    app()


@app.command()
def demo(account_id: str = typer.Argument(..., help="Real account to receive ONE synthetic spike"),
         db: Path = typer.Option(DATA_DB, "--db", help="Live warehouse to copy (never modified)"),
         out: Path = typer.Option(ROOT / "data" / "demo.duckdb", "--out")):
    """OFFLINE: build a clearly labeled SYNTHETIC demo-scenario warehouse (copy of the live one + one synthetic spike)."""
    from . import demo as dm
    src = open_wh(_db(db), read_only=True)
    a = as_of_from(src, None)
    src.close()
    info = dm.build(_db(db), out, account_id, a)
    typer.echo(f"SYNTHETIC demo scenario written to {out}: {info['signal_id']} dated {info['date']} on {account_id}")


@app.command()
def rematch(db: Path = typer.Option(DATA_DB, "--db")):
    """OFFLINE: re-apply the current AI-prototyping context rule to stored job-post excerpts (no network), then rebuild the proxy.
    Excerpts hold +-150 chars around each AI term, so this equals the ingest-time rule."""
    from . import proxy
    from .ingest.common import ai_prototyping_in_context
    from .scoring import as_of_from as _a
    wh = open_wh(db)
    rows = wh.query("SELECT signal_id, excerpt, mentions_figma, mentions_figma_make FROM job_posts WHERE mentions_ai_prototyping")
    off = [r["signal_id"] for r in rows
           if not ai_prototyping_in_context(r["excerpt"] or "", bool(r["mentions_figma"] or r["mentions_figma_make"]))]
    for sid in off:
        wh.execute("UPDATE job_posts SET mentions_ai_prototyping = FALSE WHERE signal_id = %(s)s", {"s": sid})
    proxy.build(wh, _a(wh, None))
    typer.echo(f"rematch: {len(rows)} AI-prototyping posts checked, {len(off)} dropped as out-of-context: {off}")
