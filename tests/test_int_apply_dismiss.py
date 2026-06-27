"""
Integration test — APPLY / DISMISS recommendation workflow.

Reviewed behavior (decision_engine.apply_rec, analytics.edit_rec_status):
  APPLY actually executes the change:
    - rec_type "Swap" -> swap_course(old_id -> new_id): old course removed,
      new course enrolled.
    - rec_type "Drop" -> drop_course(old course): course removed.
    - status set to "Applied".
  DISMISS is status-only:
    - status set to "Dismissed", enrollment UNCHANGED.

Tests seed a metric row directly (via analytics.save_metrics) plus the matching
enrollment, then call apply_rec / edit_rec_status and assert the DB end-state.
"""

import os
import shutil
import sqlite3
import pytest


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    src = os.environ["EVAL_SEED_DB"]
    test_db = tmp_path / "applydismiss.db"
    shutil.copy(src, test_db)
    monkeypatch.setenv("SQLITE3_DB", str(test_db))
    monkeypatch.setenv("SECRET_KEY", "t")
    monkeypatch.setenv("SEED_EMAIL", "ad@uci.edu")
    monkeypatch.setenv("SEED_PWD", "unused")
    from course_reg import create_app
    app = create_app()
    app.config["TESTING"] = True
    c = app.app_context(); c.push()
    yield str(test_db)
    c.pop()


def _new_student(db_path, email="ad_stu@uci.edu"):
    con = sqlite3.connect(db_path)
    con.execute("INSERT INTO student (first_name,last_name,email,password,gpa) VALUES (?,?,?,?,?)",
                ("Apply", "Dismiss", email, "x", 3.0))
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


def _course_id(db_path, code):
    con = sqlite3.connect(db_path)
    cid = con.execute("SELECT course_id FROM course WHERE course_code=?", (code,)).fetchone()[0]
    con.close()
    return cid


def _metric_status(db_path, metric_id):
    con = sqlite3.connect(db_path)
    s = con.execute("SELECT status FROM metric WHERE metric_id=?", (metric_id,)).fetchone()[0]
    con.close()
    return s


def _seed_metric(db_path, uid, rec_type, old_id, new_id):
    """Insert a metric row via the app's own save_metrics, return metric_id."""
    from course_reg import analytics
    analytics.save_metrics(
        student_id=uid, workload_score=30.0, burnout_score=6,
        burnout_explanation="x", impact_score=1.0, impact_explanation="x",
        recommendation="test", rec_type=rec_type,
        bullet_summary="x", why_summary="x", table_summary="x",
        old_course_id=old_id, new_course_id=new_id, status="Active",
    )
    con = sqlite3.connect(db_path)
    mid = con.execute("SELECT MAX(metric_id) FROM metric WHERE student_id=?", (uid,)).fetchone()[0]
    con.close()
    return mid


OLD_CODE = 22320      # enrolled, then dropped/swapped out
NEW_CODE = 30120      # swapped in


def test_apply_drop_removes_course_and_marks_applied(ctx):
    from course_reg import register_methods, decision_engine
    uid = _new_student(ctx)
    register_methods.register_courses(uid, [OLD_CODE])
    assert OLD_CODE in _enrolled_codes(ctx, uid)

    mid = _seed_metric(ctx, uid, "Drop", _course_id(ctx, OLD_CODE), -1)
    decision_engine.apply_rec(mid)

    assert OLD_CODE not in _enrolled_codes(ctx, uid)      # course dropped
    assert _metric_status(ctx, mid) == "Applied"


def test_apply_swap_replaces_course_and_marks_applied(ctx):
    from course_reg import register_methods, decision_engine
    uid = _new_student(ctx)
    register_methods.register_courses(uid, [OLD_CODE])

    mid = _seed_metric(ctx, uid, "Swap",
                       _course_id(ctx, OLD_CODE), _course_id(ctx, NEW_CODE))
    decision_engine.apply_rec(mid)

    enrolled = _enrolled_codes(ctx, uid)
    assert OLD_CODE not in enrolled                       # old removed
    assert NEW_CODE in enrolled                           # new added
    assert _metric_status(ctx, mid) == "Applied"


def test_dismiss_marks_dismissed_and_leaves_enrollment(ctx):
    from course_reg import register_methods, analytics
    uid = _new_student(ctx)
    register_methods.register_courses(uid, [OLD_CODE])
    before = _enrolled_codes(ctx, uid)

    mid = _seed_metric(ctx, uid, "Drop", _course_id(ctx, OLD_CODE), -1)
    analytics.edit_rec_status(mid, "Dismissed")

    assert _metric_status(ctx, mid) == "Dismissed"
    assert _enrolled_codes(ctx, uid) == before            # enrollment untouched
