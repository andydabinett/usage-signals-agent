"""Criteria 14 + 15: offline demo commands with no key and no network (fixture warehouse, sockets blocked)."""
import re

from typer.testing import CliRunner

from signals.cli import app

runner = CliRunner()


def test_offline_commands(fixture_db, tmp_path):
    from signals import handoff as ho
    from signals.warehouse import open_wh
    wh = open_wh(fixture_db)  # cache a template handoff so `handoff` has something to serve offline
    import datetime as dt
    facts = ho.build_facts(wh, "acme", dt.date(2026, 10, 10))
    ho.save(wh, "acme", facts, {"mode": "template", "model": "none", "output": ho.template(facts),
                                "grounding": ho.check(ho.template(facts), facts), "cost_usd": 0.0})
    wh.close()
    db = ["--db", str(fixture_db)]
    r = runner.invoke(app, ["score", "--all", *db]); assert r.exit_code == 0, r.output; assert "acme" in r.output
    r = runner.invoke(app, ["score", "--json", *db]); assert r.exit_code == 0 and '"flagged"' in r.output
    r = runner.invoke(app, ["explain", "acme", *db]); assert r.exit_code == 0, r.output
    assert "boards.greenhouse.io/acme/jobs/101" in r.output and "threshold:" in r.output and "CONTEXT ONLY" in r.output
    r = runner.invoke(app, ["handoff", "acme", *db]); assert r.exit_code == 0, r.output; assert "PLG / unowned queue" in r.output
    out = tmp_path / "index.html"
    r = runner.invoke(app, ["web", *db, "--out", str(out)]); assert r.exit_code == 0, r.output
    html = out.read_text()
    assert "2026-10-10" in html and "Synthetic proxy" in html and 'synthetic stand-in' in html and 'threshold' in html
    assert not re.search(r'<(script|link|img)[^>]+(src|href)="https?://', html)  # self-contained


def test_refresh_requires_contact_email(monkeypatch):
    monkeypatch.delenv("CONTACT_EMAIL", raising=False)
    r = runner.invoke(app, ["refresh"])
    assert r.exit_code == 2 and "CONTACT_EMAIL" in r.output
