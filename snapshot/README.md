# snapshot/ — PENDING

`warehouse.duckdb` + `expected.json` are written by `signals freeze` **only after** the manual review of the live pull is approved.
Until then `tests/test_snapshot.py` (criteria 3–4) and the snapshot halves of the PII/handoff tests are skipped with a PENDING reason.
