"""Criterion 12: no personal-data columns; emails redacted in raw_pulls; snapshot scan."""
import re

import duckdb
import pytest

from signals import SNAPSHOT_DB
from signals.warehouse import open_wh

ALLOWED = {"account_name", "legal_name", "role_title"}
BAD = re.compile(r"name|email|phone|linkedin", re.I)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def columns(con):
    return con.execute("SELECT table_name, column_name FROM information_schema.columns").fetchall()


def test_schema_has_no_personal_columns():
    wh = open_wh(":memory:")
    bad = [(t, c) for t, c in columns(wh.con) if BAD.search(c) and c not in ALLOWED]
    assert bad == []


def scan_for_emails(con):
    hits = []
    for t, c in columns(con):
        typ = con.execute(f"SELECT data_type FROM information_schema.columns WHERE table_name='{t}' AND column_name='{c}'").fetchone()[0]
        if typ != "VARCHAR":
            continue
        for (v,) in con.execute(f'SELECT "{c}" FROM "{t}" WHERE "{c}" LIKE \'%@%\'').fetchall():
            if EMAIL.search(v or ""):
                hits.append((t, c, EMAIL.search(v).group(0)))
    return hits


def test_fixture_warehouse_has_no_emails(fixture_db):
    con = duckdb.connect(str(fixture_db), read_only=True)
    assert scan_for_emails(con) == []
    assert con.execute("SELECT COUNT(*) FROM raw_pulls WHERE body LIKE '%[email]%'").fetchone()[0] >= 1


@pytest.mark.skipif(not SNAPSHOT_DB.exists(), reason="PENDING: snapshot not frozen yet (needs manual review + `signals freeze`)")
def test_snapshot_has_no_emails():
    assert scan_for_emails(duckdb.connect(str(SNAPSHOT_DB), read_only=True)) == []
