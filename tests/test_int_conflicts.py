"""
Integration test — TIME-CONFLICT handling in register_courses.

register_courses runs check_conflicts before enrolling each course, in course_id
order. Two courses sharing a meeting day with overlapping times can't both be
enrolled: the first enrolls, the second is rejected with a "Time conflict"
message. Courses on different days/times enroll together.

Pairs are chosen from the seeded catalog (verified against the fixture). Both
courses in the clashing pair are prereq- and coreq-free, so the second is
rejected specifically by the conflict check (not a prereq/coreq check, which run
earlier in register_courses):
  - 33201 (MWF 08:00) + 34130 (MWF 08:00)  -> clash; 34130 (higher id) rejected
  - 22320 (TuTh 09:00) + 30120 (MWF 16:00) -> no shared day, both enroll
"""
import os
import shutil
import sqlite3
import pytest

from tests import TEST_SECRET_KEY

CLASH_FIRST = 33201   # Critical Reading & Rhetoric — MWF 08:00, lower course_id (enrolls)
CLASH_SECOND = 34130  # Compilers and Interpreters — MWF 08:00, same slot (rejected)
NO_CLASH = [22320, 30120]   # TuTh 09:00 + MWF 16:00 — different days


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    src = os.environ["EVAL_SEED_DB"]
    test_db = tmp_path / "conflicts.db"
    shutil.copy(src, test_db)
    monkeypatch.setenv("SQLITE3_DB", str(test_db))
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET_KEY)
    monkeypatch.setenv("SEED_EMAIL", "conflict@uci.edu")
    monkeypatch.setenv("SEED_PWD", "unused")
    from course_reg import create_app
    app = create_app()
    app.config["TESTING"] = True
    c = app.app_context(); c.push()
    yield str(test_db)
    c.pop()


def _new_student(db_path, email="conflict_stu@uci.edu"):
    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO student (first_name,last_name,email,password,gpa) VALUES (?,?,?,?,?)",
                ("Conflict", "Tester", email, "x", 3.0))
    uid = con.execute("SELECT student_id FROM student WHERE email=?", (email,)).fetchone()[0]
    con.commit(); con.close()
    return uid


def test_clashing_courses_only_first_enrolls(ctx):
    from course_reg import register_methods, schedule_methods
    uid = _new_student(ctx)
    result = register_methods.register_courses(uid, [CLASH_FIRST, CLASH_SECOND])
    schedule = schedule_methods.get_courses_from_list(uid, "enrollment")

    # Only the first (lower course_id) of the clashing pair enrolls.
    assert CLASH_FIRST in schedule
    assert CLASH_SECOND not in schedule
    assert len(schedule) == 1
    # The rejection is reported as a time conflict, not silently dropped.
    assert isinstance(result, dict)
    assert len(result) == 1
    assert any("Time conflict" in msg for msg in result.values())


def test_non_conflicting_courses_both_enroll(ctx):
    from course_reg import register_methods, schedule_methods
    uid = _new_student(ctx)
    result = register_methods.register_courses(uid, NO_CLASH)
    schedule = schedule_methods.get_courses_from_list(uid, "enrollment")

    assert sorted(schedule) == sorted(NO_CLASH)
    assert result == "Success"
