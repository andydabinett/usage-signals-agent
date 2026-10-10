"""Criterion 6: every sql/*.sql parses as Snowflake and uses no banned D4 token."""
import re

import pytest
import sqlglot

from signals import SQL_DIR
from signals.warehouse import split_statements

BANNED = [r"\bDATEADD\b", r"\bdate_add\b", r"\bINTERVAL\b", r"::", r"\bQUALIFY\b", r"\bILIKE\b", r"\bCURRENT_DATE\b",
          r"\$\w", r"\bSTRUCT\b", r"\bLIST\b", r"\[\]", r"\bMAP\b"]
FILES = sorted(SQL_DIR.glob("*.sql"))


def test_have_sql():
    assert {f.name for f in FILES} >= {"schema.sql", "score_accounts.sql", "signals_view.sql"}


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_parses_as_snowflake(path):
    for stmt in split_statements(path.read_text()):
        sqlglot.parse_one(re.sub(r"%\((\w+)\)s", r":\1", stmt), read="snowflake")


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_no_banned_tokens(path):
    text = path.read_text()
    for pat in BANNED:
        assert not re.search(pat, text, re.I), f"{path.name}: banned token {pat}"
