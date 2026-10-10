"""Open each manual employee-count source (robots.txt-checked, polite client) and look for the recorded number.
Prints a table: confirmed (number found on page) / unconfirmed (fetch blocked, failed, or number not found) with context.
Human then marks 'corrected' where the page shows a different figure. Usage: uv run python scripts/confirm_employees.py"""
import csv, os, re, subprocess, sys, tempfile
from signals.http import PoliteClient
from signals import ROOT

rows = list(csv.DictReader(open(ROOT / "seeds" / "manual_employees.csv")))
c = PoliteClient(contact_email=os.environ.get("CONTACT_EMAIL"))
for r in rows:
    n = int(r["employees"]); url = r["source_url"]
    variants = {f"{n:,}", str(n)}
    try:
        resp = c.get(url, source="confirm")
    except Exception as e:  # denylist etc.
        print(f"{r['account_id']}\t{n}\tunconfirmed\t{type(e).__name__}: {e}\t{url}"); continue
    if resp is None:
        why = "robots.txt disallows" if url in c.robots_skips else "fetch failed"
        print(f"{r['account_id']}\t{n}\tunconfirmed\t{why}\t{url}"); continue
    if resp.status_code != 200:
        print(f"{r['account_id']}\t{n}\tunconfirmed\tHTTP {resp.status_code}\t{url}"); continue
    if resp.content[:4] == b"%PDF":
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(resp.content); f.flush()
            text = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True).stdout
    else:
        text = re.sub(r"<[^>]+>", " ", resp.text)
    text = re.sub(r"\s+", " ", text)
    hit = None
    for v in variants:
        for m in re.finditer(r"(?<![\d,])" + re.escape(v) + r"(?![\d,])", text):
            ctx = text[max(0, m.start() - 90): m.end() + 60]
            if re.search(r"employ|team|people|staff|FTE|headcount|teammate", ctx, re.I):
                hit = ctx; break
        if hit: break
    if hit:
        print(f"{r['account_id']}\t{n}\tconfirmed\t…{hit}…\t{url}")
    else:
        m = re.search(r".{0,80}\b(employees|team members|FTEs|headcount)\b.{0,40}", text, re.I)
        print(f"{r['account_id']}\t{n}\tunconfirmed\tnumber not found; nearest: {m.group(0) if m else '-'}\t{url}")
