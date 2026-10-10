"""Static, self-contained out/index.html (no external assets, no JS)."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment

from . import handoff as ho

TPL = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Usage Signals Agent — {{ as_of }}</title>
<style>
body{font:14px/1.45 system-ui,sans-serif;margin:24px auto;max-width:980px;color:#1b1b1f}
h1{margin:0 0 4px}.sub{color:#666;margin-bottom:16px}
.legend span{display:inline-block;margin-right:16px}.sw{display:inline-block;width:14px;height:10px;vertical-align:middle;margin-right:4px}
.real{background:#2f6fde}.proxy{background:repeating-linear-gradient(45deg,#c58a00 0 3px,#ffe2a0 3px 6px)}
.card{border:1px solid #ddd;border-radius:8px;padding:14px 16px;margin:14px 0}
.bar{display:flex;height:14px;border-radius:3px;overflow:hidden;background:#eee;margin:6px 0 10px;width:100%}
.bar div{height:100%}.badge{font-size:11px;padding:1px 6px;border-radius:9px;background:#ffe2a0;color:#6b4a00;margin-left:4px}
.rbadge{font-size:11px;padding:1px 6px;border-radius:9px;background:#dce8ff;color:#123d8a;margin-left:4px}
table{border-collapse:collapse}td,th{padding:2px 8px;text-align:left;border-bottom:1px solid #eee;vertical-align:top}
.h{background:#fafafa;border-left:3px solid #2f6fde;padding:8px 12px;margin-top:8px}
</style></head><body>
{% if demo %}<div style="background:#b00020;color:#fff;padding:10px 14px;font-weight:bold;border-radius:6px">SYNTHETIC DEMO SCENARIO: one synthetic spike was injected on {{ demo_accounts|join(', ') }}. Rows marked SYNTHETIC are not real. See README "Live result vs demo scenario".</div>{% endif %}
<h1>Usage Signals Agent{% if demo %} (SYNTHETIC demo scenario){% else %} (live){% endif %}</h1>
<div class="sub">Snapshot date (AS_OF): <b>{{ as_of }}</b> · Accounts: real public companies from Figma customer stories ·
Seats and usage are a <b>synthetic proxy</b> seeded from real signal dates.</div>
<div class="legend"><span><i class="sw real"></i>Real public signal</span><span><i class="sw proxy"></i>Synthetic proxy</span></div>
<h2>Flagged ({{ flagged|length }})</h2>
{% for r in flagged %}<div class="card"><b>{{ r.account_name }}</b> <code>{{ r.account_id }}</code> — total <b>{{ r.total }}</b>/100
<div class="bar" title="growth (proxy) · breadth (proxy) · agent (proxy) · fit (real) · intent (real)">
<div class="proxy" style="width:{{ r.growth_pts }}%"></div><div class="proxy" style="width:{{ r.breadth_pts }}%;opacity:.75"></div>
<div class="proxy" style="width:{{ r.agent_pts }}%;opacity:.55"></div><div class="real" style="width:{{ r.fit_pts }}%"></div>
<div class="real" style="width:{{ r.intent_pts }}%;opacity:.7"></div></div>
<table><tr><th>Usage growth WoW</th><td>{{ r.growth_pts }} pts ({{ (r.g*100)|round|int }}%)<span class="badge">proxy</span></td>
<th>Seat breadth</th><td>{{ r.breadth_pts }} pts ({{ r.active_w0 }}/{{ r.paid_seats }})<span class="badge">proxy</span></td></tr>
<tr><th>Agent adoption</th><td>{{ r.agent_pts }} pts ({{ r.agent_seats_w0 }} seats)<span class="badge">proxy</span></td>
<th>Fit</th><td>{{ r.fit_pts }} pts ({{ r.employees or 'unknown' }} employees)<span class="rbadge">real</span></td></tr>
<tr><th>Public intent</th><td colspan=3>{{ r.intent_pts }} pts ({{ r.make_roles }} Make/AI roles, {{ r.figma_roles }} Figma roles, 30d)<span class="rbadge">real</span></td></tr></table>
<p><b>Signals</b>:</p><ul>{% for s in r.signals %}<li>{% if s.is_synthetic %}<b style="color:#b00020">SYNTHETIC</b> · {% endif %}{{ s.signal_date }} · {{ s.kind }} · <a href="{{ s.url }}">{{ s.title }}</a></li>{% endfor %}</ul>
{% if r.handoff %}<div class="h"><b>{{ r.handoff.output.addressed_to }}</b><br>
<b>Why this account:</b> {{ r.handoff.output.why_this_account }}<br><b>Why now:</b> {{ r.handoff.output.why_now }}<br>
<b>Who:</b> {% for w in r.handoff.output.who_to_contact %}<a href="{{ w.source_url }}">{{ w.role_title }}</a> — {{ w.angle }}{% if not loop.last %}; {% endif %}{% endfor %}<br>
<b>First line:</b> {{ r.handoff.output.suggested_first_line }}<br>
{% for c in r.handoff.output.citations %}[{{ c.n }}] <a href="{{ c.url }}">{{ c.url }}</a><br>{% endfor %}
<small>mode: {{ r.handoff.mode }} · grounding: {{ 'pass' if r.handoff.grounding.ok else 'FAIL' }}</small></div>
{% else %}<p><i>No cached handoff.</i></p>{% endif %}</div>{% endfor %}
<h2>At risk ({{ at_risk|length }})</h2><ul>{% for r in at_risk %}<li>{{ r.account_name }} — WoW {{ (r.g*100)|round|int }}%<span class="badge">proxy</span></li>{% else %}<li>None</li>{% endfor %}</ul>
<h2>All accounts</h2><table><tr><th>account</th><th>total</th><th>growth<span class="badge">proxy</span></th><th>breadth<span class="badge">proxy</span></th><th>agent<span class="badge">proxy</span></th><th>fit<span class="rbadge">real</span></th><th>intent<span class="rbadge">real</span></th><th>real signals 30d</th></tr>
{% for r in rows %}<tr><td>{{ r.account_name }}{% if r.account_id in demo_accounts %} <b style="color:#b00020">SYNTHETIC spike</b>{% endif %}</td><td>{{ r.total }}</td><td>{{ r.growth_pts }}</td><td>{{ r.breadth_pts }}</td><td>{{ r.agent_pts }}</td><td>{{ r.fit_pts }}</td><td>{{ r.intent_pts }}</td><td>{{ r.real_signals_30d }}</td></tr>{% endfor %}</table>
<p class="sub">No personal data. Contacts are public role titles only. owner_rep is always NULL (D9).</p>
</body></html>"""


def render(wh, rows: list[dict], as_of, out_path: Path) -> Path:
    flagged = []
    for r in rows:
        if not r["flagged"]:
            continue
        r = dict(r)
        r["signals"] = wh.query("SELECT signal_date, kind, title, url, is_synthetic FROM signals WHERE account_id = %(a)s AND signal_date <= %(d)s "
                                "ORDER BY signal_date DESC LIMIT 8", {"a": r["account_id"], "d": as_of})
        r["handoff"] = ho.cached(wh, r["account_id"])
        flagged.append(r)
    from .demo import mode_of
    demo = mode_of(wh) == "demo"
    demo_accounts = [r["account_id"] for r in wh.query("SELECT DISTINCT account_id FROM signals WHERE is_synthetic")] if demo else []
    html = Environment(autoescape=True).from_string(TPL).render(
        demo=demo, demo_accounts=demo_accounts, as_of=as_of, rows=rows, flagged=flagged, at_risk=[r for r in rows if r["at_risk"]])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    return out_path
