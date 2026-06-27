"""
Integration test — ADD / DROP course workflow.

Tests the registration/drop LOGIC end-to-end against the seeded DB:
register_courses (enrollment insert, num_enrolled bump, idempotency, prereq
rejection) and drop_course (enrollment delete, num_enrolled decrement).

These exercise the same functions the routes call. We test at the function level
rather than driving the Flask session state machine (temp_courses/filter_courses),
because that machinery is UI plumbing; the meaningful behavior and DB effects live
in register_methods. Each test runs in an app context against a per-test copy of
the seed DB (handled by the fixture), so nothing leaks between tests.
"""

import os
import shutil
import sqlite3
import pytest


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    src = os.environ["EVAL_SEED_DB"]
    test_db = tmp_path / "addrop.db"
    shutil.copy(src, test_db)
    monkeypatch.setenv("SQLITE3_DB", str(test_db))
    monkeypatch.setenv("SECRET_KEY", "t")
    monkeypatch.setenv("SEED_EMAIL", "addrop@uci.edu")
    monkeypatch.setenv("SEED_PWD", "unused")
    from course_reg import create_app
    app = create_app()
    app.config["TESTING"] = True
    c = app.app_context(); c.push()
    yield str(test_db)
    c.pop()


def _new_student(db_path, email="addrop_stu@uci.edu"):
    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO student (first_name,last_name,email,password,gpa) VALUES (?,?,?,?,?)",
                ("Add", "Drop", email, "x", 3.0))
    uid = con.execute("SELECT student_id FROM student WHERE email=?", (email,)).fetchone()[0]
    con.commit(); con.close()
    return uid


def _enrolled_codes(db_path, uid):
    con = sqlite3.connect(db_path)
    rows = con.execute(
        "SELECT c.course_code FROM enrollment e JOIN course c ON c.course_id=e.course_id "
        "WHERE e.student_id=?", (uid,)).fetchall()
    con.close()
    return [r[0] for r in rows]


def _num_enrolled(db_path, code):
    con = sqlite3.connect(db_path)
    n = con.execute("SELECT num_enrolled FROM course WHERE course_code=?", (code,)).fetchone()[0]
    con.close()
    return n


OPEN_COURSE = 22320           # capacity 180, has open seats, no prereq
PREREQ_COURSE = 33301         # requires prereq_id 1 (a fresh student has not met it)


def test_register_open_course_enrolls(ctx):
    from course_reg import register_methods
    uid = _new_student(ctx)
    before = _num_enrolled(ctx, OPEN_COURSE)

    result = register_methods.register_courses(uid, [OPEN_COURSE])

    assert result == "Success"
    assert OPEN_COURSE in _enrolled_codes(ctx, uid)
    assert _num_enrolled(ctx, OPEN_COURSE) == before + 1


def test_register_is_idempotent(ctx):
    """Registering the same course twice must not double-enroll or double-count."""
    from course_reg import register_methods
    uid = _new_student(ctx)
    register_methods.register_courses(uid, [OPEN_COURSE])
    after_first = _num_enrolled(ctx, OPEN_COURSE)

    register_methods.register_courses(uid, [OPEN_COURSE])  # again

    assert _enrolled_codes(ctx, uid).count(OPEN_COURSE) == 1
    assert _num_enrolled(ctx, OPEN_COURSE) == after_first  # no second bump


def test_register_rejects_unmet_prereq(ctx):
    """A course with an unmet prerequisite must NOT enroll the student; it should
    come back in the unregistered dict with a prereq reason."""
    from course_reg import register_methods
    uid = _new_student(ctx)

    result = register_methods.register_courses(uid, [PREREQ_COURSE])

    # not enrolled
    assert PREREQ_COURSE not in _enrolled_codes(ctx, uid)
    # reported as unregistered (result is a dict when something failed)
    assert isinstance(result, dict) and len(result) >= 1


def test_drop_course_unenrolls_and_decrements(ctx):
    from course_reg import register_methods
    uid = _new_student(ctx)
    register_methods.register_courses(uid, [OPEN_COURSE])
    after_add = _num_enrolled(ctx, OPEN_COURSE)

    register_methods.drop_course(uid, OPEN_COURSE)

    assert OPEN_COURSE not in _enrolled_codes(ctx, uid)
    assert _num_enrolled(ctx, OPEN_COURSE) == after_add - 1


def test_drop_course_not_enrolled_is_noop(ctx):
    """Dropping a course the student isn't in should not change num_enrolled."""
    from course_reg import register_methods
    uid = _new_student(ctx)
    before = _num_enrolled(ctx, OPEN_COURSE)

    register_methods.drop_course(uid, OPEN_COURSE)  # never enrolled

    assert _num_enrolled(ctx, OPEN_COURSE) == before
