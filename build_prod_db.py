"""Build the production SQLite database for deployment.

One-time setup script. Run it once in a PythonAnywhere Bash console (or locally)
after configuring .env. It:

  1. creates the schema via the app's own course_reg.db.init_db (so the prod DB
     always matches the real schema — no duplicated DDL to drift),
  2. loads the full course catalog from tests/fixtures/seed.sql,
  3. recreates the estimated_hours triggers (which live in seed_db, not init_db),
  4. seeds one demo login with a password you enter interactively.

The demo password is read with getpass: it is never written to .env, passed on
the command line, or stored in shell history. The script hashes it and prints
ready-to-paste SEED_EMAIL/SEED_PWD lines for your .env — create_app() requires
those to boot, and using the demo account's hash means a wiped DB would re-seed
the same login rather than a stranger.

Usage (from the repo root, with .env present):
    python build_prod_db.py                  # refuses to clobber an existing catalog
    python build_prod_db.py --force          # delete and rebuild from scratch
    python build_prod_db.py --email me@x.com # demo login email (default demo@example.com)

Reads SQLITE3_DB from .env / the environment: the absolute path of the DB to build.
"""
import argparse
import getpass
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv
from passlib.hash import pbkdf2_sha256

from course_reg import db as database

_ROOT = Path(__file__).resolve().parent
_SEED_SQL = _ROOT / "tests" / "fixtures" / "seed.sql"

# Triggers live in seed_db (not init_db); recreate them so future course edits
# keep estimated_hours_per_week in sync. Created AFTER loading seed.sql so the
# fixture's explicit values are preserved (re-deriving credits * 1.5 is identical).
_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS sync_estimated_hours
AFTER INSERT ON course
BEGIN
    UPDATE course SET estimated_hours_per_week = NEW.credits * 1.5
    WHERE course_id = NEW.course_id;
END;
CREATE TRIGGER IF NOT EXISTS sync_estimated_hours_on_update
AFTER UPDATE OF credits ON course
BEGIN
    UPDATE course SET estimated_hours_per_week = NEW.credits * 1.5
    WHERE course_id = NEW.course_id;
END;
"""


def _db_has_catalog(db_path):
    """True if db_path exists and already holds a populated course catalog."""
    if not Path(db_path).exists():
        return False
    con = sqlite3.connect(db_path)
    try:
        row = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='course'"
        ).fetchone()
        if row is None:
            return False
        return con.execute("SELECT COUNT(*) FROM course").fetchone()[0] > 0
    finally:
        con.close()


def _remove_db_files(db_path):
    """Delete the DB and any WAL/SHM sidecars so --force rebuilds cleanly."""
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()


def build(db_path, email, password):
    """Create schema, load the catalog, add triggers, seed the demo login.

    Returns (course_count, password_hash). Assumes db_path is clear to write.
    """
    pwd_hash = pbkdf2_sha256.hash(password)
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON;")
    try:
        database.init_db(con)                        # schema (matches the app)
        con.commit()
        con.executescript(_SEED_SQL.read_text())     # full catalog
        con.commit()
        if con.execute("SELECT 1 FROM student WHERE email = ?", (email,)).fetchone():
            raise SystemExit(
                f"A student with email {email} already exists in the catalog. "
                "Re-run with --email to pick a different demo login."
            )
        con.executescript(_TRIGGERS)                 # estimated_hours triggers
        con.execute(
            'INSERT INTO "student" '
            '("first_name", "last_name", "email", "password", "gpa", "schedule_preference") '
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("Demo", "User", email, pwd_hash, 3.5, "balanced"),
        )
        con.commit()
        con.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        course_count = con.execute("SELECT COUNT(*) FROM course").fetchone()[0]
    finally:
        con.close()
    return course_count, pwd_hash


def _prompt_password():
    """Read the demo password twice via getpass (never echoed or stored)."""
    while True:
        pwd = getpass.getpass("Demo account password: ")
        if not pwd:
            print("  Password cannot be empty.", file=sys.stderr)
            continue
        if pwd != getpass.getpass("Confirm password: "):
            print("  Passwords did not match, try again.", file=sys.stderr)
            continue
        return pwd


def main():
    parser = argparse.ArgumentParser(description="Build the production database.")
    parser.add_argument("--email", default="demo@example.com",
                        help="demo login email (default: demo@example.com)")
    parser.add_argument("--force", action="store_true",
                        help="delete and rebuild even if a populated DB exists")
    args = parser.parse_args()

    # Load .env by absolute path (not cwd-dependent), same as the WSGI does.
    load_dotenv(_ROOT / ".env")
    db_path = os.environ.get("SQLITE3_DB")
    if not db_path:
        sys.exit("SQLITE3_DB is not set. Add it to .env (absolute path) and retry.")
    if not _SEED_SQL.exists():
        sys.exit(f"Seed fixture not found at {_SEED_SQL}.")

    if _db_has_catalog(db_path):
        if not args.force:
            sys.exit(
                f"{db_path} already has a course catalog. "
                "Re-run with --force to delete and rebuild it."
            )
        _remove_db_files(db_path)

    password = _prompt_password()
    course_count, pwd_hash = build(db_path, args.email, password)

    print()
    print(f"Built {db_path}")
    print(f"  courses    : {course_count}")
    print(f"  demo login : {args.email}")
    print()
    print("Add these two lines to your .env (create_app needs them to boot):")
    print(f"  SEED_EMAIL={args.email}")
    print(f"  SEED_PWD={pwd_hash}")


if __name__ == "__main__":
    main()
