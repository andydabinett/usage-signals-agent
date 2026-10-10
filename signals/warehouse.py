"""Warehouse protocol + DuckDB adapter (local Snowflake stand-in) + Snowflake adapter stub."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Iterable, Protocol

from . import SQL_DIR

_PARAM = re.compile(r"%\((\w+)\)s")


class Warehouse(Protocol):
    def query(self, sql: str, params: dict | None = None) -> list[dict]: ...
    def execute(self, sql: str, params: dict | None = None) -> None: ...
    def load_rows(self, table: str, rows: Iterable[dict]) -> int: ...
    def close(self) -> None: ...


def split_statements(sql: str) -> list[str]:
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


class DuckDBAdapter:
    def __init__(self, path: str | Path = ":memory:", read_only: bool = False):
        import duckdb

        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(self.path, read_only=read_only)

    @staticmethod
    def rewrite(sql: str) -> str:
        """pyformat %(name)s -> DuckDB $name."""
        return _PARAM.sub(lambda m: "$" + m.group(1), sql)

    def _params(self, sql: str, params: dict | None) -> dict:
        names = set(_PARAM.findall(sql))
        return {k: v for k, v in (params or {}).items() if k in names}

    def query(self, sql: str, params: dict | None = None) -> list[dict]:
        cur = self.con.execute(self.rewrite(sql), self._params(sql, params))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def execute(self, sql: str, params: dict | None = None) -> None:
        self.con.execute(self.rewrite(sql), self._params(sql, params))

    def executescript(self, sql: str) -> None:
        for stmt in split_statements(sql):
            self.con.execute(stmt)

    def load_rows(self, table: str, rows: Iterable[dict]) -> int:
        rows = list(rows)
        if not rows:
            return 0
        cols = list(rows[0].keys())
        ph = ", ".join("?" for _ in cols)
        self.con.executemany(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({ph})", [[r.get(c) for c in cols] for r in rows]
        )
        return len(rows)

    def close(self) -> None:
        self.con.close()


class SnowflakeAdapter:
    """Stub showing the swap. Reads SNOWFLAKE_* env, lazily imports the connector, passes SQL/params through unchanged
    (snowflake-connector-python natively supports pyformat %(name)s)."""

    REQUIRED = ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD")

    def __init__(self, connector: Any | None = None):
        missing = [k for k in self.REQUIRED if not os.environ.get(k)]
        if missing:
            raise RuntimeError(
                "SnowflakeAdapter needs env " + ", ".join(missing) + " and the extra: uv sync --extra snowflake"
            )
        if connector is None:
            try:
                import snowflake.connector as connector  # type: ignore
            except ImportError as e:  # pragma: no cover
                raise RuntimeError("SnowflakeAdapter needs the extra: uv sync --extra snowflake") from e
        kw = {k.removeprefix("SNOWFLAKE_").lower(): v for k, v in os.environ.items() if k.startswith("SNOWFLAKE_") and v}
        self.con = connector.connect(**kw)

    def query(self, sql: str, params: dict | None = None) -> list[dict]:
        cur = self.con.cursor()
        cur.execute(sql, params or {})
        cols = [d[0].lower() for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def execute(self, sql: str, params: dict | None = None) -> None:
        self.con.cursor().execute(sql, params or {})

    def load_rows(self, table: str, rows: Iterable[dict]) -> int:
        rows = list(rows)
        if not rows:
            return 0
        cols = list(rows[0].keys())
        sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('%(' + c + ')s' for c in cols)})"
        self.con.cursor().executemany(sql, rows)
        return len(rows)

    def close(self) -> None:
        self.con.close()


def init_schema(wh: DuckDBAdapter) -> None:
    wh.executescript((SQL_DIR / "schema.sql").read_text())
    wh.executescript((SQL_DIR / "signals_view.sql").read_text())


def open_wh(path: str | Path, read_only: bool = False) -> DuckDBAdapter:
    wh = DuckDBAdapter(path, read_only=read_only)
    if not read_only:
        init_schema(wh)
    return wh
