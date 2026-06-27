"""
Pytest bootstrap for the whole test suite.

Living at the project root, this puts the root on sys.path so `import course_reg`
works regardless of where pytest is invoked from.

SEED STRATEGY (portable, no binary DB committed)
------------------------------------------------
The DB-backed tests need a populated catalog (220 courses, prereqs, etc.). Rather
than copy a binary .db, we build a fresh SQLite database per test session from a
human-readable text fixture:

    tests/fixtures/seed.sql   <- readable INSERTs (full catalog + synthetic students)

The schema itself is created by the app's own course_reg.db.init_db, so the test
DB always matches the real schema (no duplicated DDL to drift out of sync). The
fixture only supplies DATA.

Resolution order for the seed DB the tests run against:
  1. If EVAL_SEED_DB is set AND points at an existing file -> use it as-is
     (lets you run against a specific real DB when you want to).
  2. Otherwise -> build a fresh temp DB from tests/fixtures/seed.sql once per
     session and point EVAL_SEED_DB at it.

Either way, individual DB-backed tests copy EVAL_SEED_DB to their own temp file,
so nothing is mutated across tests and your real working DB is never touched.
"""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent
_SEED_SQL = _ROOT / "tests" / "fixtures" / "seed.sql"


def _build_seed_db_from_sql() -> str:
    """Create a fresh SQLite DB, build the schema via the app's init_db, then load
    the text seed fixture. Returns the path to the new DB file."""
    from course_reg import db as database

    fd, path = tempfile.mkstemp(suffix="_seed.db", prefix="testseed_")
    os.close(fd)

    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        database.init_db(con)          # real schema, no duplicated DDL
        con.commit()
        sql = _SEED_SQL.read_text()
        con.executescript(sql)         # load readable INSERTs
        con.commit()
    finally:
        con.close()
    return path


def pytest_configure(config):
    """Resolve EVAL_SEED_DB once, before any test runs."""
    existing = os.environ.get("EVAL_SEED_DB")
    if existing and Path(existing).exists():
        # Honor an explicitly provided, existing DB.
        return

    if not _SEED_SQL.exists():
        raise RuntimeError(
            f"Seed fixture not found at {_SEED_SQL}. "
            "Expected a text seed file to build the test database from."
        )

    os.environ["EVAL_SEED_DB"] = _build_seed_db_from_sql()