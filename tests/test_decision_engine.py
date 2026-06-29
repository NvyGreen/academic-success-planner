"""
Tests for decision_engine — recommendation selection, schedule-change summaries,
and the id/code helpers.

The summary builders (compare_schedules / generate_change_summary) are pure and
tested directly; the rest are DB-backed and run against a disposable seeded DB.

Seed facts: course codes 22320 & 30120 are easy (difficulty 1, 6 hrs) -> a
light/balanced two-course schedule; 33201 is course_id 1.
"""

import os
import shutil
import sqlite3
import pytest

from tests import TEST_SECRET_KEY
from course_reg.decision_engine import ScheduleComparison, BurnoutComparison, WorkloadComparison

EASY_CODES = [22320, 30120]


@pytest.fixture
def app_ctx(tmp_path, monkeypatch):
    src = os.environ["EVAL_SEED_DB"]
    test_db = tmp_path / "decision.db"
    shutil.copy(src, test_db)
    monkeypatch.setenv("SQLITE3_DB", str(test_db))
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET_KEY)
    monkeypatch.setenv("SEED_EMAIL", "de@uci.edu")
    monkeypatch.setenv("SEED_PWD", "unused")
    from course_reg import create_app
    app = create_app()
    app.config["TESTING"] = True
    ctx = app.app_context()
    ctx.push()
    yield str(test_db)
    ctx.pop()


def _course_id(db_path, code):
    con = sqlite3.connect(db_path)
    cid = con.execute("SELECT course_id FROM course WHERE course_code=?", (code,)).fetchone()[0]
    con.close()
    return cid


# --- compare_schedules (pure) -------------------------------------------------

def test_compare_schedules():
    from course_reg import decision_engine
    diff = decision_engine.compare_schedules(ScheduleComparison(10, 2, 1.0),
                                             ScheduleComparison(4, 1, 0.5))
    assert diff == ScheduleComparison(6, 1, 0.5)


# --- generate_change_summary (pure) -------------------------------------------

def test_change_summary_improving():
    from course_reg import decision_engine
    bullets, why, table = decision_engine.generate_change_summary(
        ScheduleComparison(30, 5, 1.0), ScheduleComparison(20, 2, 1.5))
    joined = " | ".join(bullets)
    assert "Reduces weekly workload" in joined
    assert "Lowers burnout risk" in joined
    assert "Improves academic impact" in joined
    assert set(why) == {"improves workload balance", "reduces burnout risk", "improves academic impact"}
    assert len(table) == 3 and table[0][0] == "Workload"


def test_change_summary_worsening():
    from course_reg import decision_engine
    bullets, why, table = decision_engine.generate_change_summary(
        ScheduleComparison(20, 2, 1.5), ScheduleComparison(30, 5, 1.0))
    joined = " | ".join(bullets)
    assert "Increases weekly workload" in joined
    assert "Increases burnout risk" in joined
    assert "Decreases academic impact" in joined
    assert why == []                       # nothing improved
    assert len(table) == 3


def test_change_summary_no_change():
    from course_reg import decision_engine
    same = ScheduleComparison(20, 2, 1.0)
    bullets, why, table = decision_engine.generate_change_summary(same, same)
    assert bullets == [] and why == []
    assert len(table) == 3


# --- get_course_codes_from_ids ------------------------------------------------

def test_get_course_codes_from_ids_empty():
    from course_reg import decision_engine
    assert decision_engine.get_course_codes_from_ids([]) == []


def test_get_course_codes_from_ids(app_ctx):
    from course_reg import decision_engine
    cid = _course_id(app_ctx, 33201)
    assert decision_engine.get_course_codes_from_ids([cid]) == [33201]


# --- find_highest_burnout / find_highest_workload -----------------------------

def test_find_highest_burnout_empty(app_ctx):
    from course_reg import decision_engine
    assert decision_engine.find_highest_burnout([]) is None


def test_find_highest_burnout(app_ctx):
    from course_reg import decision_engine
    result = decision_engine.find_highest_burnout(EASY_CODES)
    assert isinstance(result, BurnoutComparison)
    assert result.course_id != 0           # a real course replaced the sentinel


def test_find_highest_workload_empty(app_ctx):
    from course_reg import decision_engine
    assert decision_engine.find_highest_workload([]) is None


def test_find_highest_workload(app_ctx):
    from course_reg import decision_engine
    result = decision_engine.find_highest_workload(EASY_CODES)
    assert isinstance(result, WorkloadComparison)
    assert result.estimated_hours_per_week > 0


# --- choose_drop_or_swap / generate_detailed_recommendation -------------------

def test_choose_drop_or_swap_balanced(app_ctx):
    from course_reg import decision_engine
    assert decision_engine.choose_drop_or_swap(EASY_CODES) == "Balanced"


def test_generate_detailed_recommendation_balanced(app_ctx):
    from course_reg import decision_engine
    rec, rec_type, old_c, new_c = decision_engine.generate_detailed_recommendation(1, EASY_CODES)
    assert rec_type == "Balanced"
    assert (old_c, new_c) == (-1, -1)
    assert "Balanced" in rec


# --- get_old_and_new_schedule_stats -------------------------------------------

def test_schedule_stats_unchanged_when_no_swap(app_ctx):
    from course_reg import decision_engine
    old, new = decision_engine.get_old_and_new_schedule_stats(1, EASY_CODES, -1)
    assert old == new                      # old_course == -1 -> no change


def test_schedule_stats_changed_path(app_ctx):
    from course_reg import decision_engine, logic
    courses = list(EASY_CODES)
    old_id = _course_id(app_ctx, courses[0])   # swap out 22320 (in the schedule)
    new_id = _course_id(app_ctx, 33201)        # swap in 33201 (not in the schedule)
    old, new = decision_engine.get_old_and_new_schedule_stats(1, courses, old_id, new_id)
    assert isinstance(old, ScheduleComparison) and isinstance(new, ScheduleComparison)
    # the "new" schedule is computed from the swapped course set, not just echoed back
    assert new.workload == pytest.approx(logic.total_hours_per_week([courses[1], 33201]))
