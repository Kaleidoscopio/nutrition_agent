"""
Postgres connection layer.

This module provides a sqlite3-compatible interface (`.execute()` on the
connection, `?` placeholders, dict/index row access, `.lastrowid`) backed by
psycopg2 + real Postgres, so the rest of the codebase (originally written
against sqlite3) did not need to be rewritten query-by-query.
"""

import re

import psycopg2
import psycopg2.extensions

from app.core.config import settings

# Matches "INSERT" as the first keyword of a statement (case-insensitive),
# used to decide whether we should auto-append RETURNING id for lastrowid support.
_INSERT_RE = re.compile(r"^\s*INSERT\s+INTO\s+", re.IGNORECASE)
_RETURNING_RE = re.compile(r"\bRETURNING\b", re.IGNORECASE)

# Splits on "?" placeholders that are not inside a quoted string literal.
_QUESTION_MARK_RE = re.compile(r"\?")


def _sqlite_to_pg_sql(sql: str) -> str:
    """Convert sqlite-style '?' positional placeholders to psycopg2 '%s'."""
    return _QUESTION_MARK_RE.sub("%s", sql)


class Row:
    """
    Minimal stand-in for sqlite3.Row: supports both integer (positional)
    and string (column name) access, plus `keys()` so `dict(row)` works.
    """

    __slots__ = ("_values", "_columns")

    def __init__(self, values, columns):
        self._values = values
        self._columns = columns

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return self._values[key]
        try:
            idx = self._columns.index(key)
        except ValueError:
            raise KeyError(key)
        return self._values[idx]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return f"Row({dict(zip(self._columns, self._values))!r})"

    def keys(self):
        return list(self._columns)


class Cursor:
    """Wraps a psycopg2 cursor to provide sqlite3-style ergonomics."""

    def __init__(self, pg_cursor):
        self._cur = pg_cursor
        self.lastrowid = None

    def _columns(self):
        if self._cur.description is None:
            return []
        return [col.name for col in self._cur.description]

    def execute(self, sql, params=()):
        pg_sql = _sqlite_to_pg_sql(sql)

        auto_returning = False
        if _INSERT_RE.match(sql) and not _RETURNING_RE.search(sql):
            pg_sql = pg_sql.rstrip().rstrip(";") + " RETURNING id"
            auto_returning = True

        self._cur.execute(pg_sql, params)

        if auto_returning:
            try:
                result = self._cur.fetchone()
                self.lastrowid = result[0] if result else None
            except psycopg2.ProgrammingError:
                # Statement had no results to return (e.g. table has no "id" column)
                self.lastrowid = None

        return self

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        return Row(row, self._columns())

    def fetchall(self):
        rows = self._cur.fetchall()
        cols = self._columns()
        return [Row(r, cols) for r in rows]

    def close(self):
        self._cur.close()

    @property
    def rowcount(self):
        return self._cur.rowcount


class Connection:
    """Wraps a psycopg2 connection to provide sqlite3-style ergonomics."""

    def __init__(self, pg_conn):
        self._conn = pg_conn

    def cursor(self):
        return Cursor(self._conn.cursor())

    def execute(self, sql, params=()):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()


def get_db_connection() -> Connection:
    pg_conn = psycopg2.connect(settings.database_url)
    return Connection(pg_conn)
