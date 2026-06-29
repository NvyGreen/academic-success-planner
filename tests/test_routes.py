"""
Request-level tests for routes.py using Flask's in-process test client.

These exercise the full server pipeline (routing -> view -> session -> DB ->
template render) without a browser. CSRF is disabled in the test config so POSTs
go through, and auth is established via the real /login form so the session is set
up the way the routes expect. Each test runs against a disposable seeded DB copy.
"""

import os
import shutil
import sqlite3
import pytest
from passlib.hash import pbkdf2_sha256

from tests import TEST_SECRET_KEY

EMAIL = "rt@uci.edu"
PWD = "secret123"
ENROLLED = [22320, 30120]        # two easy courses the test user is enrolled in
OPEN_CODE = 30140                # a real, open course not in the schedule


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    src = os.environ["EVAL_SEED_DB"]
    test_db = tmp_path / "routes.db"
    shutil.copy(src, test_db)
    monkeypatch.setenv("SQLITE3_DB", str(test_db))
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET_KEY)
    monkeypatch.setenv("SEED_EMAIL", "seed@uci.edu")
    monkeypatch.setenv("SEED_PWD", "unused")
    from course_reg import create_app
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return app.test_client(), str(test_db)


def _make_user(db_path, email=EMAIL):
    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO student (first_name,last_name,email,password,gpa) VALUES (?,?,?,?,?)",
                ("Route", "Tester", email, pbkdf2_sha256.hash(PWD), 3.0))
    uid = con.execute("SELECT student_id FROM student WHERE email=?", (email,)).fetchone()[0]
    con.commit()
    con.close()
    return uid


def _enroll(db_path, uid, codes):
    con = sqlite3.connect(db_path)
    for code in codes:
        cid = con.execute("SELECT course_id FROM course WHERE course_code=?", (code,)).fetchone()[0]
        con.execute("INSERT INTO enrollment (student_id, course_id) VALUES (?,?)", (uid, cid))
    con.commit()
    con.close()


def _insert_metric(db_path, uid, rec_type="Balanced", status="Viewed",
                   why="improves workload balance", bullet="Lowers burnout",
                   table="Workload,30,20,-10"):
    con = sqlite3.connect(db_path)
    con.execute(
        """INSERT INTO metric (student_id, workload_score, burnout_score, burnout_explanation,
               impact_score, impact_explanation, recommendation, rec_type, bullet_summary,
               why_summary, table_summary, old_course_id, new_course_id, status, timestamp)
           VALUES (?, 20.0, 2.0, 'b', 1.0, 'i', 'Swap A with B', ?, ?, ?, ?, 1, 2, ?, '2099-01-01T00:00:00')""",
        (uid, rec_type, bullet, why, table, status))
    mid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.commit()
    con.close()
    return mid


@pytest.fixture
def auth(app_client):
    client, db = app_client
    uid = _make_user(db)
    _enroll(db, uid, ENROLLED)
    resp = client.post("/login", data={"email": EMAIL, "password": PWD})
    assert resp.status_code == 302
    return client, db, uid


# --- auth / login_required -----------------------------------------------------

def test_login_required_redirects_anonymous(app_client):
    client, _ = app_client
    resp = client.get("/courses")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_login_get(app_client):
    client, _ = app_client
    assert client.get("/login").status_code == 200


def test_login_success(app_client):
    client, db = app_client
    _make_user(db)
    resp = client.post("/login", data={"email": EMAIL, "password": PWD})
    assert resp.status_code == 302
    assert "/courses" in resp.headers["Location"]


def test_login_wrong_password(app_client):
    client, db = app_client
    _make_user(db)
    # a bad password falls through and re-renders the login page (no redirect)
    resp = client.post("/login", data={"email": EMAIL, "password": "nope"})
    assert resp.status_code == 200


def test_login_unknown_email(app_client):
    client, _ = app_client
    resp = client.post("/login", data={"email": "nobody@uci.edu", "password": PWD})
    assert resp.status_code == 302


def test_login_when_already_logged_in(auth):
    client, _, _ = auth
    resp = client.get("/login")
    assert resp.status_code == 302       # bounced to index


# --- schedule / view pages -----------------------------------------------------

def test_index_redirects_to_courses(auth):
    client, _, _ = auth
    resp = client.get("/")
    assert resp.status_code == 302 and "/courses" in resp.headers["Location"]


@pytest.mark.parametrize("path", [
    "/courses", "/finals", "/quarter", "/waitlists", "/drop-courses",
    "/filter-courses", "/filter-courses/advanced",
    "/preview/courses", "/preview/finals", "/preview/quarter",
    "/analytics", "/analytics/history",
])
def test_get_pages_render(auth, path):
    client, _, _ = auth
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path, location", [
    ("/cancel-filter", "/courses"),
    ("/cancel-waitlist", "/waitlists"),
    ("/cancel-select", "/filter-courses"),
])
def test_cancel_routes_redirect(auth, path, location):
    client, _, _ = auth
    resp = client.get(path)
    assert resp.status_code == 302 and location in resp.headers["Location"]


# --- filter search -------------------------------------------------------------

def test_filter_courses_post_redirects_to_listings(auth):
    client, _, _ = auth
    resp = client.post("/filter-courses", data={
        "gen_cat": "1", "department": "2", "course_num": "", "course_code": "",
        "course_level": "all", "instructor": "", "submit": "See Courses",
    })
    assert resp.status_code == 302 and "/listings" in resp.headers["Location"]


def test_filter_courses_advanced_post(auth):
    client, _, _ = auth
    resp = client.post("/filter-courses/advanced", data={
        "gen_cat": "1", "department": "2", "course_num": "", "course_code": "",
        "course_level": "all", "instructor": "",
        "modality": "nomode", "days": "", "starts_after": "nopref", "ends_before": "nopref",
        "course_full_option": "nopref", "cancel_option": "excl",
        "building_code": "", "room_no": "", "credits": "",
    })
    assert resp.status_code == 302 and "/listings" in resp.headers["Location"]


def test_listings_without_filter_redirects(auth):
    client, _, _ = auth
    resp = client.get("/listings")
    assert resp.status_code == 302 and "/filter-courses" in resp.headers["Location"]


def test_listings_with_filter_renders(auth):
    client, _, _ = auth
    with client.session_transaction() as sess:
        sess["filter_criteria"] = ["Department: I&C SCI"]
        # 13-element row: idx 0 = action status, idx 11 = open/waitlist status, idx 12 = code
        sess["filter_courses"] = [["Neither", "I&C SCI 31", "Lec", "MWF", "10-11",
                                   "Smith", "Online", "4", "0 / 100", "DBH", "1100",
                                   "Open", OPEN_CODE]]
    assert client.get("/listings").status_code == 200


# --- POST course actions -------------------------------------------------------

def test_add_course(auth):
    client, _, _ = auth
    with client.session_transaction() as sess:
        sess["filter_courses"] = [["Neither", OPEN_CODE]]
    resp = client.post(f"/add-course/{OPEN_CODE}", data={"current_page": "/listings"})
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert OPEN_CODE in sess["temp_courses"]


def test_drop_course_from_schedule(auth):
    client, db, uid = auth
    resp = client.post(f"/drop-course/{ENROLLED[0]}", data={"current_page": "/courses"})
    assert resp.status_code == 302
    con = sqlite3.connect(db)
    still = con.execute(
        "SELECT 1 FROM enrollment e JOIN course c ON e.course_id=c.course_id "
        "WHERE e.student_id=? AND c.course_code=?", (uid, ENROLLED[0])).fetchone()
    con.close()
    assert still is None             # the drop hit the DB


def test_wait_course_then_drop_wait(auth):
    client, db, uid = auth
    with client.session_transaction() as sess:
        sess["filter_courses"] = [["Neither", OPEN_CODE]]
    assert client.post(f"/wait-course/{OPEN_CODE}", data={"current_page": "/listings"}).status_code == 302
    with client.session_transaction() as sess:
        assert OPEN_CODE in sess["user_waitlist"]

    assert client.post(f"/drop-wait/{OPEN_CODE}", data={"current_page": "/waitlists"}).status_code == 302
    with client.session_transaction() as sess:
        assert OPEN_CODE not in sess["user_waitlist"]


def test_confirm_schedule_registers_temp_courses(auth):
    client, db, uid = auth
    with client.session_transaction() as sess:
        sess["temp_courses"] = [OPEN_CODE]
    resp = client.get("/confirm-schedule")
    assert resp.status_code == 302 and "/courses" in resp.headers["Location"]
    con = sqlite3.connect(db)
    enrolled = con.execute(
        "SELECT 1 FROM enrollment e JOIN course c ON e.course_id=c.course_id "
        "WHERE e.student_id=? AND c.course_code=?", (uid, OPEN_CODE)).fetchone()
    con.close()
    assert enrolled is not None


# --- recommendations -----------------------------------------------------------

def test_apply_recommendation(auth):
    client, db, uid = auth
    mid = _insert_metric(db, uid, rec_type="Balanced", status="Viewed")
    resp = client.post(f"/apply-recommendation/{mid}", data={"current_page": "/analytics"})
    assert resp.status_code == 302
    con = sqlite3.connect(db)
    status = con.execute("SELECT status FROM metric WHERE metric_id=?", (mid,)).fetchone()[0]
    con.close()
    assert status == "Applied"


def test_dismiss_recommendation(auth):
    client, db, uid = auth
    mid = _insert_metric(db, uid, status="Viewed")
    resp = client.post(f"/dismiss-recommendation/{mid}", data={"current_page": "/analytics"})
    assert resp.status_code == 302
    con = sqlite3.connect(db)
    status = con.execute("SELECT status FROM metric WHERE metric_id=?", (mid,)).fetchone()[0]
    con.close()
    assert status == "Dismissed"


# --- analytics branches --------------------------------------------------------

def test_analytics_with_active_recommendation(auth):
    client, db, uid = auth
    _insert_metric(db, uid, rec_type="Swap", status="Viewed",
                   why="improves workload balance,reduces burnout risk",
                   bullet="Lowers burnout,Improves impact", table="Workload,30,20,-10")
    assert client.get("/analytics").status_code == 200


# --- error-string display branches --------------------------------------------

def _raise_db_error(*_a, **_k):
    raise sqlite3.Error("boom")


def test_pages_flash_session_error_strings(auth):
    """When schedule data in the session is an error string, pages flash it and
    fall back to an empty schedule instead of crashing."""
    client, _, _ = auth
    with client.session_transaction() as sess:
        sess["user_courses"] = "db is down"
        sess["user_waitlist"] = "db is down"
        sess["old_courses"] = "stale error"
        sess["unreged_courses"] = "ok"
    for path in ["/courses", "/finals", "/quarter", "/waitlists",
                 "/preview/courses", "/preview/finals", "/preview/quarter"]:
        with client.session_transaction() as sess:
            sess["user_courses"] = "db is down"      # /courses resets some keys; re-set
            sess["user_waitlist"] = "db is down"
        assert client.get(path).status_code == 200


def test_courses_flashes_unregistered_courses(auth):
    client, _, _ = auth
    with client.session_transaction() as sess:
        sess["unreged_courses"] = {"ICS 33": "missing prereq"}
    assert client.get("/courses").status_code == 200


def test_drop_course_from_temp_only(auth):
    client, _, _ = auth
    with client.session_transaction() as sess:
        sess["temp_courses"] = [OPEN_CODE]
        sess["filter_courses"] = [["Registered", OPEN_CODE]]
    resp = client.post(f"/drop-course/{OPEN_CODE}", data={"current_page": "/listings"})
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert OPEN_CODE not in sess["temp_courses"]


def test_wait_and_drop_wait_with_waitlist_error_string(auth):
    client, _, _ = auth
    with client.session_transaction() as sess:
        sess["user_waitlist"] = "db is down"
    assert client.post(f"/wait-course/{OPEN_CODE}", data={"current_page": "/x"}).status_code == 302
    with client.session_transaction() as sess:
        sess["user_waitlist"] = "db is down"
    assert client.post(f"/drop-wait/{OPEN_CODE}", data={"current_page": "/x"}).status_code == 302


# --- DB-error fallbacks (analytics + POST actions) ----------------------------

def test_analytics_db_error_branch(auth, monkeypatch):
    client, _, _ = auth
    from course_reg import analytics
    monkeypatch.setattr(analytics, "get_num_schedules", _raise_db_error)
    assert client.get("/analytics").status_code == 200


def test_analytics_history_db_error_branch(auth, monkeypatch):
    client, _, _ = auth
    from course_reg import analytics
    monkeypatch.setattr(analytics, "get_num_schedules", _raise_db_error)
    assert client.get("/analytics/history").status_code == 200


def test_drop_courses_db_error_redirects(auth, monkeypatch):
    client, _, _ = auth
    from course_reg import filter_methods
    monkeypatch.setattr(filter_methods, "get_courses_from_codes", _raise_db_error)
    assert client.get("/drop-courses").status_code == 302


def test_waitlists_db_error_redirects(auth, monkeypatch):
    client, _, _ = auth
    from course_reg import filter_methods
    monkeypatch.setattr(filter_methods, "get_user_waitlist", _raise_db_error)
    assert client.get("/waitlists").status_code == 302


def test_filter_courses_prep_error_redirects(auth, monkeypatch):
    client, _, _ = auth
    from course_reg import filter_methods
    monkeypatch.setattr(filter_methods, "prep_ge", _raise_db_error)
    assert client.get("/filter-courses").status_code == 302


def test_filter_courses_advanced_prep_error_redirects(auth, monkeypatch):
    client, _, _ = auth
    from course_reg import filter_methods
    monkeypatch.setattr(filter_methods, "prep_ge", _raise_db_error)
    assert client.get("/filter-courses/advanced").status_code == 302


def test_drop_course_db_error(auth, monkeypatch):
    client, _, _ = auth
    from course_reg import register_methods
    monkeypatch.setattr(register_methods, "drop_course", _raise_db_error)
    resp = client.post(f"/drop-course/{ENROLLED[0]}", data={"current_page": "/courses"})
    assert resp.status_code == 302


def test_wait_course_db_error(auth, monkeypatch):
    client, _, _ = auth
    from course_reg import register_methods
    monkeypatch.setattr(register_methods, "waitlist_course", _raise_db_error)
    resp = client.post(f"/wait-course/{OPEN_CODE}", data={"current_page": "/x"})
    assert resp.status_code == 302


def test_drop_wait_db_error(auth, monkeypatch):
    client, _, _ = auth
    from course_reg import register_methods
    monkeypatch.setattr(register_methods, "drop_waitlist", _raise_db_error)
    with client.session_transaction() as sess:
        sess["user_waitlist"] = [OPEN_CODE]
    resp = client.post(f"/drop-wait/{OPEN_CODE}", data={"current_page": "/x"})
    assert resp.status_code == 302


def test_apply_recommendation_db_error(auth, monkeypatch):
    client, _, _ = auth
    from course_reg import decision_engine
    monkeypatch.setattr(decision_engine, "apply_rec", _raise_db_error)
    resp = client.post("/apply-recommendation/1", data={"current_page": "/analytics"})
    assert resp.status_code == 302


def test_dismiss_recommendation_db_error(auth, monkeypatch):
    client, _, _ = auth
    from course_reg import analytics
    monkeypatch.setattr(analytics, "edit_rec_status", _raise_db_error)
    resp = client.post("/dismiss-recommendation/1", data={"current_page": "/analytics"})
    assert resp.status_code == 302


def test_confirm_schedule_db_error(auth, monkeypatch):
    client, _, _ = auth
    from course_reg import register_methods
    monkeypatch.setattr(register_methods, "register_courses", _raise_db_error)
    with client.session_transaction() as sess:
        sess["temp_courses"] = [OPEN_CODE]
    assert client.get("/confirm-schedule").status_code == 302


def test_confirm_schedule_refetch_db_error(auth, monkeypatch):
    client, _, _ = auth
    from course_reg import schedule_methods
    monkeypatch.setattr(schedule_methods, "get_courses_from_list", _raise_db_error)
    assert client.get("/confirm-schedule").status_code == 302


def test_safe_redirect_rejects_external_url(auth):
    """A current_page pointing off-site is rejected in favour of the safe fallback."""
    client, _, _ = auth
    with client.session_transaction() as sess:
        sess["filter_courses"] = [["Neither", OPEN_CODE]]
    resp = client.post(f"/add-course/{OPEN_CODE}",
                       data={"current_page": "http://evil.example.com/steal"})
    assert resp.status_code == 302
    assert "evil.example.com" not in resp.headers["Location"]


# --- analytics recommendation-type variants -----------------------------------

@pytest.mark.parametrize("rec_type, why", [
    ("Balanced", "the schedule is already well balanced"),
    ("Drop", "reduces weekly workload,lowers burnout risk"),
])
def test_analytics_recommendation_variants(auth, rec_type, why):
    client, db, uid = auth
    _insert_metric(db, uid, rec_type=rec_type, status="Viewed", why=why)
    assert client.get("/analytics").status_code == 200


def test_analytics_hides_non_viewed_recommendation(auth):
    client, db, uid = auth
    _insert_metric(db, uid, rec_type="Swap", status="Applied")
    assert client.get("/analytics").status_code == 200


def test_analytics_with_empty_user_courses(auth):
    client, _, _ = auth
    with client.session_transaction() as sess:
        sess["user_courses"] = ""
    assert client.get("/analytics").status_code == 200


# --- session-key cleanup + filter display update ------------------------------

def test_drop_course_updates_filter_display(auth):
    client, _, _ = auth
    with client.session_transaction() as sess:
        sess["filter_courses"] = [["Registered", ENROLLED[0]]]
    resp = client.post(f"/drop-course/{ENROLLED[0]}", data={"current_page": "/listings"})
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess["filter_courses"][0][0] == "Neither"


def test_index_clears_stale_filter_keys(auth):
    client, _, _ = auth
    with client.session_transaction() as sess:
        sess["filter_courses"] = [["Neither", OPEN_CODE]]
        sess["filter_criteria"] = ["something"]
    client.get("/")
    with client.session_transaction() as sess:
        assert "filter_courses" not in sess and "filter_criteria" not in sess


def test_login_clears_stale_filter_keys(app_client):
    client, db = app_client
    _make_user(db)
    with client.session_transaction() as sess:
        sess["filter_courses"] = [["Neither", OPEN_CODE]]
        sess["filter_criteria"] = ["x"]
    resp = client.post("/login", data={"email": EMAIL, "password": PWD})
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert "filter_courses" not in sess and "filter_criteria" not in sess


# --- before_request: check_dirty_metrics --------------------------------------

def test_check_dirty_metrics_recomputes_and_history(auth):
    client, db, uid = auth
    with client.session_transaction() as sess:
        sess["metrics_dirty"] = True
        sess["user_courses"] = ENROLLED        # a real list -> add_new_schedule runs
    # any page triggers the before_request hook
    assert client.get("/quarter").status_code == 200
    with client.session_transaction() as sess:
        assert sess["metrics_dirty"] is False
    # now there is activity -> the history donut path runs with total_activities > 0
    assert client.get("/analytics/history").status_code == 200
