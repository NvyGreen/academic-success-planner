"""
Integration test (Deliverable B): swap recommendations must NOT suggest a course
the student has already completed.

Background
----------
`decision_engine.find_course_to_swap` builds its candidate pool from courses in
the same department (then same school) that are easier/shorter than the course
being swapped out. As written, the candidate query excludes:
  - courses in the CURRENT schedule (NOT IN placeholders)
  - the same course_number
  - zero-credit labs
  - courses whose prereqs are unmet
...but it does NOT exclude courses recorded in `prev_enrollment` (already
completed). This test pins that requirement.

Expected state:
  - BEFORE the fix: this test FAILS (a completed course can be returned).
  - AFTER adding a `prev_enrollment` exclusion to the candidate query: it PASSES.

The test talks to the real function against a disposable copy of the seeded DB.
It seeds a throwaway student, gives them a completed course that WOULD otherwise
be a valid swap target, and asserts the engine never returns it.
"""

import os
import shutil
import sqlite3
import tempfile

import pytest

# --- Concrete fixtures chosen from the real catalog -------------------------
# OLD course to swap out: a hard COMPSCI course (difficulty 5).
# COMPLETED course: an easier COMPSCI course (difficulty 4) that satisfies the
# candidate filter (same dept, easier) and therefore WOULD be offered as a swap
# unless completed-course exclusion is implemented.
OLD_COURSE_ID = 55          # COMPSCI 113, difficulty 5
OLD_COURSE_NAME = "COMPSCI 113"
OLD_COURSE_DIFFICULTY = 5
OLD_COURSE_HOURS = 6.0
# The candidate the engine's tiebreaker (closest course_id to old) actually
# returns for OLD_COURSE_ID=55 is course_id 58 (COMPSCI 118). We mark THAT one
# completed, so a missing prev_enrollment exclusion is forced into the open
# instead of being masked by the tiebreaker happening to pick something else.
COMPLETED_COURSE_ID = 58    # COMPSCI 118 — the course the engine would return


@pytest.fixture
def app_with_db(tmp_path, monkeypatch):
    """Build the app pointed at a disposable copy of the seeded DB."""
    src = os.environ.get("EVAL_SEED_DB", "/home/claude/work2.db")
    test_db = tmp_path / "swap_test.db"
    shutil.copy(src, test_db)

    monkeypatch.setenv("SQLITE3_DB", str(test_db))
    monkeypatch.setenv("SECRET_KEY", "test_secret")
    monkeypatch.setenv("SEED_EMAIL", "swaptester@uci.edu")
    monkeypatch.setenv("SEED_PWD", "unused")

    from course_reg import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app, str(test_db)


def _seed_student_with_completed(db_path, completed_course_id):
    """Insert a throwaway student and mark one course completed. Returns user_id."""
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT INTO student (first_name,last_name,email,password,gpa) "
        "VALUES (?,?,?,?,?)",
        ("Swap", "Tester", "swaptester@uci.edu", "x", 3.0),
    )
    user_id = con.execute(
        "SELECT student_id FROM student WHERE email=?",
        ("swaptester@uci.edu",),
    ).fetchone()[0]
    con.execute(
        "INSERT INTO prev_enrollment (student_id, course_id) VALUES (?,?)",
        (user_id, completed_course_id),
    )
    con.commit()
    con.close()
    return user_id


def test_swap_does_not_recommend_completed_course(app_with_db):
    app, db_path = app_with_db
    user_id = _seed_student_with_completed(db_path, COMPLETED_COURSE_ID)

    from course_reg import decision_engine
    from course_reg.decision_engine import BurnoutComparison

    old_course = BurnoutComparison(
        course_id=OLD_COURSE_ID,
        course_name=OLD_COURSE_NAME,
        difficulty=OLD_COURSE_DIFFICULTY,
        estimated_hours_per_week=OLD_COURSE_HOURS,
    )
    # current schedule = just the course being swapped out (by course_code)
    con = sqlite3.connect(db_path)
    old_code = con.execute(
        "SELECT course_code FROM course WHERE course_id=?", (OLD_COURSE_ID,)
    ).fetchone()[0]
    completed_code = con.execute(
        "SELECT course_code FROM course WHERE course_id=?", (COMPLETED_COURSE_ID,)
    ).fetchone()[0]
    con.close()

    with app.app_context():
        suggestion = decision_engine.find_course_to_swap(
            user_id, old_course, [old_code]
        )

    assert suggestion.course_id != COMPLETED_COURSE_ID, (
        f"Swap engine recommended course_id={COMPLETED_COURSE_ID} "
        f"({completed_code}) which the student has ALREADY COMPLETED. "
        f"find_course_to_swap must exclude courses in prev_enrollment."
    )


def test_swap_still_returns_a_valid_alternative(app_with_db):
    """Sanity: excluding completed courses should not break normal swaps —
    a different, valid, not-completed course should still be returned."""
    app, db_path = app_with_db
    user_id = _seed_student_with_completed(db_path, COMPLETED_COURSE_ID)

    from course_reg import decision_engine
    from course_reg.decision_engine import BurnoutComparison

    old_course = BurnoutComparison(
        OLD_COURSE_ID, OLD_COURSE_NAME, OLD_COURSE_DIFFICULTY, OLD_COURSE_HOURS
    )
    con = sqlite3.connect(db_path)
    old_code = con.execute(
        "SELECT course_code FROM course WHERE course_id=?", (OLD_COURSE_ID,)
    ).fetchone()[0]
    con.close()

    with app.app_context():
        suggestion = decision_engine.find_course_to_swap(user_id, old_course, [old_code])

    assert suggestion is not None
    assert suggestion.course_id not in (OLD_COURSE_ID, COMPLETED_COURSE_ID)
