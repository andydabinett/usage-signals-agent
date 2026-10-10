"""Criterion 7."""
import pytest

from signals.warehouse import SnowflakeAdapter


def test_raises_without_env(monkeypatch):
    for k in SnowflakeAdapter.REQUIRED:
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(RuntimeError, match="SNOWFLAKE_ACCOUNT.*uv sync --extra snowflake"):
        SnowflakeAdapter()


def test_passes_sql_and_params_through(monkeypatch):
    for k in SnowflakeAdapter.REQUIRED:
        monkeypatch.setenv(k, "x")
    calls = []

    class Cur:
        description = [("A",)]
        def execute(self, sql, params):
            calls.append((sql, params))
        def fetchall(self):
            return [(1,)]

    class Con:
        def cursor(self):
            return Cur()
        def close(self):
            pass

    class Connector:
        @staticmethod
        def connect(**kw):
            return Con()

    sf = SnowflakeAdapter(connector=Connector)
    sql = "SELECT 1 AS a WHERE x = %(as_of)s"
    assert sf.query(sql, {"as_of": "2026-10-10"}) == [{"a": 1}]
    assert calls == [(sql, {"as_of": "2026-10-10"})]
