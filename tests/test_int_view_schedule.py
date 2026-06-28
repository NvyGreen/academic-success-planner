"""
Integration test — VIEW SCHEDULE workflow.

After enrolling, a student's schedule must reflect exactly the courses they are
enrolled in. Tests schedule_methods.get_courses_from_list("enrollment", ...),
which is what the schedule/analytics views read from.
"""

import os
import shutil
import sqlite3
import pytest

from tests import TEST_SECRET_KEY


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    src = os.environ["EVAL_SEED_DB"]
    test_db = tmp_path / "sched.db"
    shutil.copy(src, test_db)
    monkeypatch.setenv("SQLITE3_DB", str(test_db))
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET_KEY)
    monkeypatch.setenv("SEED_EMAIL", "sched@uci.edu")
    monkeypatch.setenv("SEED_PWD", "unused")
    from course_reg import create_app
    app = create_app()
    app.config["TESTING"] = True
    c = app.app_context(); c.push()
    yield str(test_db)
    c.pop()


def _new_student(db_path, email="sched_stu@uci.edu"):
    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO student (first_name,last_name,email,password,gpa) VALUES (?,?,?,?,?)",
                ("Sched", "Viewer", email, "x", 3.0))
    uid = con.execute("SELECT student_id FROM student WHERE email=?", (email,)).fetchone()[0]
    con.commit(); con.close()
    return uid


THREE_COURSES = [22320, 30120, 30140]   # three open, no-prereq courses


def test_empty_schedule_is_empty(ctx):
    from course_reg import schedule_methods
    uid = _new_student(ctx)
    assert schedule_methods.get_courses_from_list(uid, "enrollment") == []


def test_schedule_reflects_enrolled_courses(ctx):
    from course_reg import register_methods, schedule_methods
    uid = _new_student(ctx)
    register_methods.register_courses(uid, THREE_COURSES)

    schedule = schedule_methods.get_courses_from_list(uid, "enrollment")

    assert sorted(schedule) == sorted(THREE_COURSES)


def test_schedule_updates_after_drop(ctx):
    from course_reg import register_methods, schedule_methods
    uid = _new_student(ctx)
    register_methods.register_courses(uid, THREE_COURSES)
    register_methods.drop_course(uid, THREE_COURSES[0])

    schedule = schedule_methods.get_courses_from_list(uid, "enrollment")

    assert THREE_COURSES[0] not in schedule
    assert len(schedule) == 2


def test_invalid_table_rejected(ctx):
    """get_courses_from_list guards the table name against injection; a bad table
    must raise, not silently query."""
    import sqlite3 as _sql
    from course_reg import schedule_methods
    uid = _new_student(ctx)
    with pytest.raises(_sql.Error):
        schedule_methods.get_courses_from_list(uid, "course; DROP TABLE student")
