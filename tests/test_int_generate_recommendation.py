"""
Integration test — GENERATE RECOMMENDATION workflow.

decision_engine.generate_detailed_recommendation(user_id, courses) returns
(description, rec_type, old_course_id, new_course_id). It must:
  - return a rec_type consistent with choose_drop_or_swap for the schedule,
  - for a Swap, name a real old course and a real, valid new course,
  - for a Drop, name a course from the schedule,
  - for a light/balanced schedule, return Balanced with no course ids.

Scenarios use real seeded courses with verified properties.
"""

import os
import shutil
import sqlite3
import pytest


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    src = os.environ["EVAL_SEED_DB"]
    test_db = tmp_path / "rec.db"
    shutil.copy(src, test_db)
    monkeypatch.setenv("SQLITE3_DB", str(test_db))
    monkeypatch.setenv("SECRET_KEY", "t")
    monkeypatch.setenv("SEED_EMAIL", "rec@uci.edu")
    monkeypatch.setenv("SEED_PWD", "unused")
    from course_reg import create_app
    app = create_app()
    app.config["TESTING"] = True
    c = app.app_context(); c.push()
    yield str(test_db)
    c.pop()


def _new_student(db_path, email="rec_stu@uci.edu"):
    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO student (first_name,last_name,email,password,gpa) VALUES (?,?,?,?,?)",
                ("Rec", "Tester", email, "x", 3.0))
    uid = con.execute("SELECT student_id FROM student WHERE email=?", (email,)).fetchone()[0]
    con.commit(); con.close()
    return uid


# Verified scenarios (same as the Option B unit tests, reused here end-to-end):
SCEN_BALANCED = [33201, 36045]                       # light -> Balanced
SCEN_HARDMIX_SWAP = [36570, 36360]                   # hard mix, low hours -> Swap
SCEN_SEVERE_DROP = [36570, 36360, 36050, 37204]      # burnout>=6 -> Drop


def test_recommendation_type_matches_chooser(ctx):
    """generate_detailed_recommendation's rec_type must agree with
    choose_drop_or_swap for the same schedule."""
    from course_reg import decision_engine
    uid = _new_student(ctx)
    for scenario in (SCEN_BALANCED, SCEN_HARDMIX_SWAP, SCEN_SEVERE_DROP):
        expected = decision_engine.choose_drop_or_swap(scenario)
        _, rec_type, _, _ = decision_engine.generate_detailed_recommendation(uid, scenario)
        assert rec_type == expected, f"{scenario}: {rec_type} != {expected}"


def test_balanced_returns_no_course_ids(ctx):
    from course_reg import decision_engine
    uid = _new_student(ctx)
    desc, rec_type, old_id, new_id = decision_engine.generate_detailed_recommendation(uid, SCEN_BALANCED)
    assert rec_type == "Balanced"
    assert old_id == -1 and new_id == -1


def test_swap_names_real_old_and_new(ctx):
    """A Swap must identify a real course to remove and a real replacement, and
    the replacement must not already be in the schedule."""
    from course_reg import decision_engine
    uid = _new_student(ctx)
    desc, rec_type, old_id, new_id = decision_engine.generate_detailed_recommendation(uid, SCEN_HARDMIX_SWAP)
    assert rec_type == "Swap"
    assert old_id > 0 and new_id > 0
    assert old_id != new_id
    # new course must be a valid course_id and not already enrolled in the schedule
    con = sqlite3.connect(ctx)
    new_code = con.execute("SELECT course_code FROM course WHERE course_id=?", (new_id,)).fetchone()
    con.close()
    assert new_code is not None
    assert new_code[0] not in SCEN_HARDMIX_SWAP


def test_drop_names_a_course_from_schedule(ctx):
    from course_reg import decision_engine
    uid = _new_student(ctx)
    desc, rec_type, old_id, new_id = decision_engine.generate_detailed_recommendation(uid, SCEN_SEVERE_DROP)
    assert rec_type == "Drop"
    assert old_id > 0 and new_id == -1
    con = sqlite3.connect(ctx)
    old_code = con.execute("SELECT course_code FROM course WHERE course_id=?", (old_id,)).fetchone()[0]
    con.close()
    assert old_code in SCEN_SEVERE_DROP
