"""
Unit/integration tests for register_methods — the enrollment / waitlist engine.

Targets the functions the existing integration tests don't reach: get_course_description,
check_coreqs, check_prereqs, the waitlist lifecycle (waitlist_course / drop_waitlist),
and the waitlist-promotion path (enroll_from_waitlist / promote_waitlist).

Seed facts used (verified): course_code 33201 = course_id 1 (open 4/12, no coreqs or
prereqs); corequisite pair course 3 -> 4; prerequisite pair course 2 -> 1; the seed
ships with an empty waitlist and empty enrollment.
"""

import os
import shutil
import sqlite3
import pytest

from tests import TEST_SECRET_KEY

OPEN_CODE = 33201          # course_id 1, open, no coreqs/prereqs


@pytest.fixture
def app_ctx(tmp_path, monkeypatch):
    src = os.environ["EVAL_SEED_DB"]
    test_db = tmp_path / "register.db"
    shutil.copy(src, test_db)
    monkeypatch.setenv("SQLITE3_DB", str(test_db))
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET_KEY)
    monkeypatch.setenv("SEED_EMAIL", "rm@uci.edu")
    monkeypatch.setenv("SEED_PWD", "unused")
    from course_reg import create_app
    app = create_app()
    app.config["TESTING"] = True
    ctx = app.app_context()
    ctx.push()
    yield str(test_db)
    ctx.pop()


def _new_student(db_path, email):
    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO student (first_name,last_name,email,password,gpa) VALUES (?,?,?,?,?)",
                ("Reg", "Ister", email, "x", 3.0))
    uid = con.execute("SELECT student_id FROM student WHERE email=?", (email,)).fetchone()[0]
    con.commit()
    con.close()
    return uid


# --- get_course_description ----------------------------------------------------

def test_get_course_description(app_ctx):
    from course_reg import register_methods
    desc = register_methods.get_course_description(1)   # course_id 1
    assert isinstance(desc, str)
    assert desc.endswith(")") and "(" in desc           # "DEPT NUM (TYPE)"


# --- check_coreqs --------------------------------------------------------------

def test_check_coreqs_none(app_ctx):
    from course_reg import register_methods
    assert register_methods.check_coreqs(1, [1]) == []  # course 1 has no coreqs


def test_check_coreqs_unsatisfied(app_ctx):
    from course_reg import register_methods
    # course 3 co-requires course 4; without 4 in the batch it's unsatisfied
    unfilled = register_methods.check_coreqs(3, [3])
    assert len(unfilled) == 1


def test_check_coreqs_satisfied(app_ctx):
    from course_reg import register_methods
    assert register_methods.check_coreqs(3, [3, 4]) == []


# --- check_prereqs -------------------------------------------------------------

def test_check_prereqs_none(app_ctx):
    from course_reg import register_methods
    uid = _new_student(app_ctx, "pre_none@uci.edu")
    assert register_methods.check_prereqs(uid, 1) == []  # course 1 has no prereqs


def test_check_prereqs_unsatisfied(app_ctx):
    from course_reg import register_methods
    uid = _new_student(app_ctx, "pre_no@uci.edu")        # no prev_enrollment
    unfilled = register_methods.check_prereqs(uid, 2)    # course 2 needs course 1
    assert len(unfilled) == 1


def test_check_prereqs_satisfied(app_ctx):
    from course_reg import register_methods
    uid = _new_student(app_ctx, "pre_yes@uci.edu")
    con = sqlite3.connect(app_ctx)
    con.execute("INSERT INTO prev_enrollment (student_id, course_id) VALUES (?, 1)", (uid,))
    con.commit()
    con.close()
    assert register_methods.check_prereqs(uid, 2) == []  # course 1 already taken


# --- waitlist lifecycle --------------------------------------------------------

def test_waitlist_then_drop(app_ctx):
    from course_reg import register_methods, schedule_methods
    uid = _new_student(app_ctx, "wl_drop@uci.edu")

    register_methods.waitlist_course(uid, OPEN_CODE)
    assert schedule_methods.get_courses_from_list(uid, "student_waitlist") == [OPEN_CODE]

    register_methods.drop_waitlist(uid, OPEN_CODE)
    assert schedule_methods.get_courses_from_list(uid, "student_waitlist") == []


# --- enroll_from_waitlist / promote_waitlist -----------------------------------

def test_enroll_from_waitlist_promotes_front_of_line(app_ctx):
    from course_reg import register_methods, schedule_methods
    uid = _new_student(app_ctx, "ewl@uci.edu")
    register_methods.waitlist_course(uid, OPEN_CODE)     # open course, so a seat is free

    promoted = register_methods.enroll_from_waitlist()

    assert uid in promoted
    assert OPEN_CODE in schedule_methods.get_courses_from_list(uid, "enrollment")
    assert OPEN_CODE not in schedule_methods.get_courses_from_list(uid, "student_waitlist")


def test_enroll_from_waitlist_noop_when_no_waitlist(app_ctx):
    from course_reg import register_methods
    # nobody is waitlisted -> nothing promoted
    assert register_methods.enroll_from_waitlist() == []


def test_promote_waitlist_enrolls_and_records(app_ctx):
    from course_reg import register_methods, schedule_methods, analytics
    uid = _new_student(app_ctx, "pw@uci.edu")
    register_methods.waitlist_course(uid, OPEN_CODE)

    register_methods.promote_waitlist()

    assert OPEN_CODE in schedule_methods.get_courses_from_list(uid, "enrollment")
    # promote_waitlist also writes a metric snapshot for the promoted student
    assert analytics.get_latest_metric(uid) is not None
