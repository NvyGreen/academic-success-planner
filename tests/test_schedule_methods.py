"""
Unit/integration tests for schedule_methods — the schedule + calendar builders
behind the "My Courses", finals, and quarter views.

Covers the DB-backed fetchers (get_short_courses / get_short_courses_final) and the
calendar placement logic (create_calendar / add_course_to_calendar /
add_final_to_calendar), including multi-hour SKIP cells and the skip-when-no-time
path. The calendar builders are pure, so those tests don't need an app context.
"""

import os
import shutil
import pytest

from tests import TEST_SECRET_KEY

THREE_COURSES = [22320, 30120, 30140]


@pytest.fixture
def app_ctx(tmp_path, monkeypatch):
    src = os.environ["EVAL_SEED_DB"]
    test_db = tmp_path / "sched_methods.db"
    shutil.copy(src, test_db)
    monkeypatch.setenv("SQLITE3_DB", str(test_db))
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET_KEY)
    monkeypatch.setenv("SEED_EMAIL", "sm@uci.edu")
    monkeypatch.setenv("SEED_PWD", "unused")
    from course_reg import create_app
    app = create_app()
    app.config["TESTING"] = True
    ctx = app.app_context()
    ctx.push()
    yield
    ctx.pop()


# --- get_short_courses (DB-backed) --------------------------------------------

def test_get_short_courses_empty():
    from course_reg import schedule_methods
    assert schedule_methods.get_short_courses([]) == []


def test_get_short_courses_row_per_code(app_ctx):
    from course_reg import schedule_methods
    rows = schedule_methods.get_short_courses(THREE_COURSES)
    assert len(rows) == len(THREE_COURSES)
    for row in rows:
        # [dept+num, name, type, days, time, instructor, location, course_id]
        assert len(row) == 8
        assert isinstance(row[0], str) and " " in row[0]   # "DEPT NUM"
        assert isinstance(row[-1], int)                    # course_id is last


def test_get_short_courses_final_empty():
    from course_reg import schedule_methods
    assert schedule_methods.get_short_courses_final([]) == []


def test_get_short_courses_final_structure(app_ctx):
    from course_reg import schedule_methods
    rows = schedule_methods.get_short_courses_final(THREE_COURSES)
    assert len(rows) >= 1
    for row in rows:
        # [dept+num, name, type, final_str_or_None, location]
        assert len(row) == 5
        assert isinstance(row[0], str)


# --- create_calendar grid shape (pure) ----------------------------------------

def test_create_calendar_grid_shape():
    from course_reg import schedule_methods
    cal = schedule_methods.create_calendar([], "courses")
    assert cal[0] == ["", "Mon", "Tue", "Wed", "Thu", "Fri"]
    assert len(cal) == 17                       # header + 16 time rows
    assert all(len(row) == 6 for row in cal)
    assert cal[1][0] == "7 AM"                  # first time-row label


# --- add_course_to_calendar (pure) --------------------------------------------

def _course_row(abbr="CS 101", days="MWF", time_str="9:00 AM - 9:50 AM"):
    # matches get_short_courses layout: index 0 = abbr, 3 = days, 4 = time
    return [abbr, "name", "Lec", days, time_str, "instr", "loc", 999]


def test_add_course_places_on_each_meeting_day():
    from course_reg import schedule_methods
    cal = schedule_methods.create_calendar([_course_row(days="MWF")], "courses")
    # 9 AM -> SLOT_LOOKUP.index(9)=2 -> start_slot 3 ; M=col1, W=col3, F=col5
    for col in (1, 3, 5):
        cell = cal[3][col]
        assert isinstance(cell, tuple) and cell[0] == "CS 101"
    assert cal[3][2] is None                    # Tuesday untouched


def test_add_course_multi_hour_marks_skip():
    from course_reg import schedule_methods
    # 9:00-10:50 spans ~2 rows -> the following row is a SKIP continuation
    cal = schedule_methods.create_calendar(
        [_course_row(days="M", time_str="9:00 AM - 10:50 AM")], "courses")
    assert isinstance(cal[3][1], tuple)
    assert cal[4][1] == "SKIP"


def test_add_course_skips_when_no_time():
    from course_reg import schedule_methods
    cal = schedule_methods.create_calendar(
        [_course_row(days=None, time_str=None)], "courses")
    assert all(cell is None for row in cal[1:] for cell in row[1:])


def test_create_calendar_unknown_type_places_nothing():
    from course_reg import schedule_methods
    cal = schedule_methods.create_calendar([_course_row()], "neither")
    assert all(cell is None for row in cal[1:] for cell in row[1:])


# --- add_final_to_calendar (pure) ---------------------------------------------

def _final_row(abbr="CS 101", time_str="Tue, 12:30 PM - 1:50 PM"):
    # matches get_short_courses_final layout: index 0 = abbr, 3 = final time
    return [abbr, "name", "Lec", time_str, "loc"]


def test_add_final_places_and_skips():
    from course_reg import schedule_methods
    cal = schedule_methods.create_calendar([_final_row()], "final")
    # 12:30 PM -> SLOT_LOOKUP.index(12)=5 -> start_slot 6 ; Tue=col2
    assert isinstance(cal[6][2], tuple) and cal[6][2][0] == "CS 101"
    assert cal[7][2] == "SKIP"                  # spills into the 1 PM row


def test_add_final_skips_when_no_time():
    from course_reg import schedule_methods
    cal = schedule_methods.create_calendar([_final_row(time_str=None)], "final")
    assert all(cell is None for row in cal[1:] for cell in row[1:])


# --- "can't place it" branches ------------------------------------------------

def test_add_course_outside_grid_hours_skipped():
    from course_reg import schedule_methods
    # 6 AM is before the grid's 7 AM start -> not in SLOT_LOOKUP -> skipped
    cal = schedule_methods.create_calendar(
        [_course_row(days="M", time_str="6:00 AM - 6:50 AM")], "courses")
    assert all(cell is None for row in cal[1:] for cell in row[1:])


def test_add_final_outside_grid_hours_skipped():
    from course_reg import schedule_methods
    cal = schedule_methods.create_calendar(
        [_final_row(time_str="Tue, 6:00 AM - 6:50 AM")], "final")
    assert all(cell is None for row in cal[1:] for cell in row[1:])


def test_add_final_weekend_day_skipped():
    from course_reg import schedule_methods
    # Saturday isn't a column in the Mon-Fri grid -> skipped
    cal = schedule_methods.create_calendar(
        [_final_row(time_str="Sat, 12:30 PM - 1:50 PM")], "final")
    assert all(cell is None for row in cal[1:] for cell in row[1:])
