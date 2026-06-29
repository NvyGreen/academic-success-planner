"""
Unit/integration tests for filter_methods — the course-search query builder and
row formatter behind the Filter Courses / Listings pages.

Covers prep_ge / prep_departments, get_courses (+ get_courses_common branches),
get_courses_adv (advanced filters), get_courses_from_codes, get_user_waitlist
(+ clean_wait / clean_common), and the get_criteria / get_criteria_adv summaries.

Seed facts used (verified): course_code 33201 = course_id 1, department_id 2,
GE category 2, course_number "50", level "lower", 4 credits, building HG room 2310,
open (4/12), no coreqs/prereqs.
"""

import os
import shutil
import sqlite3
import pytest

from tests import TEST_SECRET_KEY
from course_reg import models

SAMPLE_CODE = 33201
SAMPLE_DEPT = 2
SAMPLE_GE = 2


@pytest.fixture
def app_ctx(tmp_path, monkeypatch):
    src = os.environ["EVAL_SEED_DB"]
    test_db = tmp_path / "filter.db"
    shutil.copy(src, test_db)
    monkeypatch.setenv("SQLITE3_DB", str(test_db))
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET_KEY)
    monkeypatch.setenv("SEED_EMAIL", "fm@uci.edu")
    monkeypatch.setenv("SEED_PWD", "unused")
    from course_reg import create_app
    app = create_app()
    app.config["TESTING"] = True
    ctx = app.app_context()
    ctx.push()
    yield str(test_db)
    ctx.pop()


def _filters(ge_cat=1, department=0, course_num="", course_code=None, course_level="all", instructor=""):
    return models.Filters(ge_cat, department, course_num, course_code, course_level, instructor)


def _adv(ge_cat=1, department=0, course_num="", course_code=None, course_level="all", instructor="",
         modality="nomode", days="", starts_after="nopref", ends_before="nopref",
         course_full_option="nopref", cancel_option="excl", building_code="", room_no="", credits=0):
    return models.AdvancedFilters(ge_cat, department, course_num, course_code, course_level, instructor,
                                  modality, days, starts_after, ends_before, course_full_option,
                                  cancel_option, building_code, room_no, credits)


def _new_student(db_path, email):
    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO student (first_name,last_name,email,password,gpa) VALUES (?,?,?,?,?)",
                ("Fil", "Ter", email, "x", 3.0))
    uid = con.execute("SELECT student_id FROM student WHERE email=?", (email,)).fetchone()[0]
    con.commit()
    con.close()
    return uid


# --- dropdown prep -------------------------------------------------------------

def test_prep_ge(app_ctx):
    from course_reg import filter_methods
    ge = filter_methods.prep_ge()
    assert (1, " ") in ge                       # NO_GE_CAT renders blank
    assert len(ge) > 1
    assert any(label.startswith("GE ") for _, label in ge)


def test_prep_departments(app_ctx):
    from course_reg import filter_methods
    deps = filter_methods.prep_departments()
    assert deps[0] == ("0", " ")
    assert len(deps) > 1
    assert all(isinstance(key, str) for key, _ in deps)


# --- get_courses + get_courses_common -----------------------------------------

def test_get_courses_by_code_returns_one(app_ctx):
    from course_reg import filter_methods
    courses = filter_methods.get_courses(_filters(course_code=SAMPLE_CODE), [], [], [])
    assert len(courses) == 1
    assert courses[0][-1] == SAMPLE_CODE        # course_code is last
    assert courses[0][0] == "Neither"           # not added / waitlisted


def test_get_courses_added_and_waitlisted_flags(app_ctx):
    from course_reg import filter_methods
    added = filter_methods.get_courses(_filters(course_code=SAMPLE_CODE), [SAMPLE_CODE], [], [])
    assert added[0][0] == "Registered"
    waited = filter_methods.get_courses(_filters(course_code=SAMPLE_CODE), [], [], [SAMPLE_CODE])
    assert waited[0][0] == "Waitlisted"


def test_get_courses_all_common_branches(app_ctx):
    from course_reg import filter_methods
    # every get_courses_common branch fires, incl. the "else: add AND" paths
    f = _filters(ge_cat=SAMPLE_GE, department=SAMPLE_DEPT, course_num="50",
                 course_code=SAMPLE_CODE, course_level="lower")
    courses = filter_methods.get_courses(f, [], [], [])
    assert SAMPLE_CODE in [c[-1] for c in courses]


def test_get_courses_instructor_branch(app_ctx):
    from course_reg import filter_methods
    # exercises the EXISTS-instructor branch; nobody is named "Nobody"
    assert filter_methods.get_courses(_filters(instructor="Nobody"), [], [], []) == []


def test_get_courses_by_department(app_ctx):
    from course_reg import filter_methods
    courses = filter_methods.get_courses(_filters(department=SAMPLE_DEPT), [], [], [])
    assert len(courses) >= 1
    assert SAMPLE_CODE in [c[-1] for c in courses]


# --- get_courses_adv -----------------------------------------------------------

def test_get_courses_adv_minimal(app_ctx):
    from course_reg import filter_methods
    courses = filter_methods.get_courses_adv(_adv(course_code=SAMPLE_CODE), [], [], [])
    assert len(courses) == 1 and courses[0][-1] == SAMPLE_CODE


def test_get_courses_adv_all_branches(app_ctx):
    from course_reg import filter_methods
    # kitchen sink: modality / days / start+end time / full-option / building / room / credits
    f = _adv(modality="inperson", days="M,W", starts_after="08:00", ends_before="23:00",
             course_full_option="open_only", cancel_option="excl",
             building_code="HG", room_no="2310", credits=4)
    assert isinstance(filter_methods.get_courses_adv(f, [], [], []), list)


def test_get_courses_adv_online_and_cancel_variants(app_ctx):
    from course_reg import filter_methods
    f = _adv(modality="online", course_full_option="full_only", cancel_option="only_cancel")
    assert isinstance(filter_methods.get_courses_adv(f, [], [], []), list)


# --- get_courses_from_codes ----------------------------------------------------

def test_get_courses_from_codes_empty(app_ctx):
    from course_reg import filter_methods
    assert filter_methods.get_courses_from_codes([]) == []


def test_get_courses_from_codes(app_ctx):
    from course_reg import filter_methods
    courses = filter_methods.get_courses_from_codes([SAMPLE_CODE])
    assert len(courses) == 1
    assert courses[0][0] == "Registered"        # from_codes marks added=True
    assert courses[0][-1] == SAMPLE_CODE


# --- get_user_waitlist + clean_wait -------------------------------------------

def test_get_user_waitlist_empty(app_ctx):
    from course_reg import filter_methods
    assert filter_methods.get_user_waitlist(1, []) == []


def test_get_user_waitlist_with_position(app_ctx):
    from course_reg import filter_methods, register_methods
    uid = _new_student(app_ctx, "wl@uci.edu")
    register_methods.waitlist_course(uid, SAMPLE_CODE)
    rows = filter_methods.get_user_waitlist(uid, [SAMPLE_CODE])
    assert len(rows) == 1
    assert rows[0][-1] == SAMPLE_CODE
    assert rows[0][-2] == 1                      # waitlist position (first in line)


# --- criteria summaries --------------------------------------------------------

def test_get_criteria(app_ctx):
    from course_reg import filter_methods
    f = _filters(ge_cat=SAMPLE_GE, department=SAMPLE_DEPT, course_num="50",
                 course_code=SAMPLE_CODE, course_level="upper", instructor="Smith")
    joined = " | ".join(filter_methods.get_criteria(f))
    assert "General Education Category" in joined
    assert "Department:" in joined
    assert "Course Number Range: 50" in joined
    assert f"Course Code: {SAMPLE_CODE}" in joined
    assert "Upper Division only" in joined
    assert "Instructor: Smith" in joined
    assert "Exclude cancelled courses" in joined


def test_get_criteria_adv(app_ctx):
    from course_reg import filter_methods
    f = _adv(modality="inperson", days="M,W", starts_after="09:00", ends_before="17:00",
             course_full_option="open_only", cancel_option="excl",
             building_code="HG", room_no="2310", credits=4)
    joined = " | ".join(filter_methods.get_criteria_adv(f))
    assert "Modality: In-person" in joined
    assert "Meeting Days: M,W" in joined
    assert "meets on or after" in joined
    assert "finishes by" in joined
    assert "Don't show full courses" in joined
    assert "HG, room 2310" in joined
    assert "Number of credits: 4" in joined
