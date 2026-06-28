"""
Remove all load-test data created by seed_students.py + a Locust run.

Deletes every row belonging to loadtest*@uci.edu accounts and the accounts
themselves, and restores course.num_enrolled to baseline by undoing any leftover
enrollments. Safe to run repeatedly.

FK-safe ordering matters: the `activity` table references metric.metric_id, so it
must be deleted before `metric`. This script deletes children before parents and
tolerates tables that don't exist (so it survives further schema changes).

Usage (from project root, venv active):
    python cleanup_loadtest.py
"""

import os
import sqlite3

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "course_reg", ".env"))


def main():
    db_path = os.environ.get("SQLITE3_DB")
    if not db_path:
        raise SystemExit("No DB path. Set SQLITE3_DB in course_reg/.env.")

    db = sqlite3.connect(db_path)
    db.execute("PRAGMA foreign_keys = ON;")

    ids = [r[0] for r in db.execute(
        "SELECT student_id FROM student WHERE email LIKE 'loadtest%@uci.edu'"
    ).fetchall()]
    if not ids:
        print("No loadtest accounts found — nothing to clean.")
        db.close()
        return
    ph = ",".join("?" * len(ids))

    # Undo num_enrolled for any enrollments these students still hold, so the
    # counter returns to its pre-test baseline (decrement by rows actually held).
    for course_id, n in db.execute(
        f"SELECT course_id, COUNT(*) FROM enrollment WHERE student_id IN ({ph}) GROUP BY course_id",
        ids,
    ).fetchall():
        db.execute("UPDATE course SET num_enrolled = num_enrolled - ? WHERE course_id = ?", (n, course_id))
        print(f"restored num_enrolled -{n} on course_id {course_id}")

    # Children before parents. `activity` first (it FKs to metric AND student),
    # then the student-owned tables, then the student rows last.
    existing = {r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    for tbl in ("activity", "metric", "enrollment", "student_waitlist", "prev_enrollment"):
        if tbl in existing:
            n = db.execute(f"DELETE FROM {tbl} WHERE student_id IN ({ph})", ids).rowcount
            print(f"deleted {n} from {tbl}")
    n = db.execute("DELETE FROM student WHERE email LIKE 'loadtest%@uci.edu'").rowcount
    print(f"deleted {n} from student")

    db.commit()
    remaining = db.execute("SELECT COUNT(*) FROM student WHERE email LIKE 'loadtest%'").fetchone()[0]
    db.close()
    print(f"done — {remaining} loadtest accounts remain.")


if __name__ == "__main__":
    main()
