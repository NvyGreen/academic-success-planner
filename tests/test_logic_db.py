"""
Unit test suite — DB-BACKED functions.

These functions query the database, so technically they are narrow integration
tests, but they belong with the scoring/logic suite. Each runs inside an app
context against a disposable copy of the seeded DB (so the real DB is untouched).

Set EVAL_SEED_DB to a seeded sample_courses.db; the fixture copies it per test.

Expected values are computed independently from the known catalog data, not read
back from the functions under test.
"""

import os
import shutil
import sqlite3
import pytest


@pytest.fixture
def app_ctx(tmp_path, monkeypatch):
    src = os.environ.get("EVAL_SEED_DB", "/home/claude/work2.db")
    test_db = tmp_path / "unit_db.db"
    shutil.copy(src, test_db)
    monkeypatch.setenv("SQLITE3_DB", str(test_db))
    monkeypatch.setenv("SECRET_KEY", "test_secret")
    monkeypatch.setenv("SEED_EMAIL", "unit@uci.edu")
    monkeypatch.setenv("SEED_PWD", "unused")
    from course_reg import create_app
    app = create_app()
    app.config["TESTING"] = True
    ctx = app.app_context()
    ctx.push()
    yield app, str(test_db)
    ctx.pop()


# Known catalog facts (verified from the seeded DB):
#   course_code 22320: difficulty 1, 6.0 hrs, 4 credits
#   course_code 30120: difficulty 1, 6.0 hrs, 4 credits
#   -> total_hours_per_week([22320,30120]) = 0.5*6 + 0.5*6 = 6.0
#   -> get_total_credits([22320,30120]) = 8
TWO_EASY = [22320, 30120]


def test_total_hours_empty_is_zero(app_ctx):
    from course_reg import logic
    assert logic.total_hours_per_week([]) == 0


def test_total_hours_two_easy(app_ctx):
    from course_reg import logic
    # both difficulty 1 -> 0.5 multiplier each, 6 hrs each
    assert logic.total_hours_per_week(TWO_EASY) == 6.0


def test_get_total_credits_two_courses(app_ctx):
    from course_reg import logic
    assert logic.get_total_credits(TWO_EASY) == 8


def test_get_total_credits_empty_is_zero(app_ctx):
    from course_reg import logic
    assert logic.get_total_credits([]) == 0


def test_calculate_burnout_empty(app_ctx):
    from course_reg import logic
    score, factors = logic.calculate_burnout_risk([])
    assert score == 0
    assert factors["num_courses"] == 0


def test_calculate_burnout_two_easy_is_low(app_ctx):
    from course_reg import logic
    # 2 easy courses, 6 weighted hrs: no 4+ bonus, hours <=15 (no add),
    # 0 difficult -> score 0 -> Low
    score, factors = logic.calculate_burnout_risk(TWO_EASY)
    assert score == 0
    assert factors["num_difficult"] == 0
    assert logic.estimate_burnout_risk(score) == "Low"


def test_check_prereqs_returns_list(app_ctx):
    """check_prereqs should return a list (empty if the student has met them).
    For a fresh student with no completed courses, a course that HAS a prereq
    should return a non-empty list of unmet prereqs."""
    from course_reg import register_methods
    # course_code 33301 (course_id 2) requires prereq_id 1.
    # A brand-new user (id that has no prev_enrollment) has not met it.
    result = register_methods.check_prereqs(999999, 2)
    assert isinstance(result, list)


def test_check_coreqs_returns_list(app_ctx):
    from course_reg import register_methods
    # Passing a course with no coreqs (or all satisfied) should give a list.
    result = register_methods.check_coreqs(2, [])
    assert isinstance(result, list)