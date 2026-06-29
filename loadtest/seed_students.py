"""
Seed extra students into the CourseReg database for load testing.

Idempotent: re-running won't duplicate accounts (email is UNIQUE, and we
INSERT OR IGNORE). Each new student gets a copy of student #1's
prev_enrollment history so the analytics pages have data to render.

Usage (from the project root, with the venv active):
    python seed_students.py                 # 50 students, pwd "loadtest"
    python seed_students.py --count 200 --password hunter2

Creates accounts:  loadtest1@uci.edu ... loadtestN@uci.edu
"""

import argparse
import os
import sqlite3

from dotenv import load_dotenv
from passlib.hash import pbkdf2_sha256

# Pull SQLITE3_DB from .env (same file the app uses).
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=50,
                        help="number of students to create (default: 50)")
    parser.add_argument("--password", default="loadtest",
                        help="plaintext password shared by all seeded users")
    parser.add_argument("--db", default=os.environ.get("SQLITE3_DB"),
                        help="path to the sqlite db (default: $SQLITE3_DB)")
    args = parser.parse_args()

    if not args.db:
        raise SystemExit("No DB path. Set SQLITE3_DB or pass --db.")

    pwd_hash = pbkdf2_sha256.hash(args.password)

    db = sqlite3.connect(args.db)
    db.execute("PRAGMA foreign_keys = ON;")

    # The history rows we'll clone onto each new student (student_id = 1 = John Doe).
    template_courses = [
        row[0] for row in db.execute(
            "SELECT course_id FROM prev_enrollment WHERE student_id = 1"
        ).fetchall()
    ]

    created = 0
    for i in range(1, args.count + 1):
        email = f"loadtest{i}@uci.edu"

        cur = db.execute(
            """INSERT OR IGNORE INTO student
               (first_name, last_name, email, password, gpa, schedule_preference)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("Load", f"Test{i}", email, pwd_hash, 3.5, "balanced"),
        )

        if cur.rowcount:  # a row was actually inserted (not ignored)
            created += 1
            student_id = cur.lastrowid
            db.executemany(
                "INSERT INTO prev_enrollment (student_id, course_id) VALUES (?, ?)",
                [(student_id, cid) for cid in template_courses],
            )

    db.commit()
    total = db.execute(
        "SELECT COUNT(*) FROM student WHERE email LIKE 'loadtest%@uci.edu'"
    ).fetchone()[0]
    db.close()

    print(f"Created {created} new student(s). "
          f"{total} loadtest accounts now exist, all with password '{args.password}'.")


if __name__ == "__main__":
    main()
