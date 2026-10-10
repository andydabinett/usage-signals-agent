# snapshot/ — FROZEN 2026-10-10 (as_of 2026-10-10)

Frozen with `signals freeze` after Chief of Staff - Coding approved the manual review (Oct 10, 2026).
Flagged: okta, affirm, zapier. At risk: brex. `tests/test_snapshot.py` (criteria 3–4) and the snapshot halves of the
PII (12) and handoff (13) tests now run (no skips).

Compaction: `raw_pulls.body` (already `[email]`-redacted at ingest) is cut to 2,000 chars to keep the file small; the full
body's sha256 stays in the row. Cached handoffs are kept only for flagged accounts.
