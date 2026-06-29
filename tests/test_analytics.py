"""
Unit/integration tests for analytics — the metric/activity persistence layer that
backs the Insights and Activity History pages.

Covers save_metrics / get_latest_metric, the count and list getters, save_activity
(including the version-numbering logic), edit_rec_status, and get_improvement_summary
(including its empty/no-data path). Each test runs against a disposable copy of the
seeded DB and a fresh synthetic student.
"""

import os
import shutil
import sqlite3
import pytest

from tests import TEST_SECRET_KEY


@pytest.fixture
def app_ctx(tmp_path, monkeypatch):
    src = os.environ["EVAL_SEED_DB"]
    test_db = tmp_path / "analytics.db"
    shutil.copy(src, test_db)
    monkeypatch.setenv("SQLITE3_DB", str(test_db))
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET_KEY)
    monkeypatch.setenv("SEED_EMAIL", "an@uci.edu")
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
    con.execute(
        "INSERT INTO student (first_name,last_name,email,password,gpa) VALUES (?,?,?,?,?)",
        ("An", "Alytics", email, "x", 3.0),
    )
    uid = con.execute("SELECT student_id FROM student WHERE email=?", (email,)).fetchone()[0]
    con.commit()
    con.close()
    return uid


def _save_metric(uid, workload=20.0, burnout=2.0, impact=1.0, status="Viewed",
                 rec="Swap A with B", rec_type="Swap"):
    from course_reg import analytics
    return analytics.save_metrics(
        uid, workload, burnout, "burnout why", impact, "impact why",
        rec, rec_type, "bullet", "why", "table", 5, 7, status,
    )


# --- save_metrics / get_latest_metric -----------------------------------------

def test_save_metrics_returns_id(app_ctx):
    uid = _new_student(app_ctx, "save1@uci.edu")
    mid = _save_metric(uid)
    assert isinstance(mid, int) and mid > 0


def test_get_latest_metric_roundtrip(app_ctx):
    from course_reg import analytics
    uid = _new_student(app_ctx, "latest@uci.edu")
    _save_metric(uid, workload=11.1, burnout=3.0, rec="older")
    _save_metric(uid, workload=22.2, burnout=4.0, rec="newer")     # newest
    latest = analytics.get_latest_metric(uid)
    assert latest is not None
    assert round(latest["workload_score"], 1) == 22.2
    assert latest["recommendation"] == "newer"
    assert latest["status"] == "Viewed"


def test_get_latest_metric_none_for_new_student(app_ctx):
    from course_reg import analytics
    uid = _new_student(app_ctx, "nometrics@uci.edu")
    assert analytics.get_latest_metric(uid) is None


# --- count getters -------------------------------------------------------------

def test_recommendation_counts_by_status(app_ctx):
    from course_reg import analytics
    uid = _new_student(app_ctx, "counts@uci.edu")
    _save_metric(uid, status="Viewed")
    _save_metric(uid, status="Applied")
    _save_metric(uid, status="Dismissed")
    assert analytics.get_num_recommendations(uid) == 3
    assert analytics.get_num_recommendations_by_status(uid, "Applied") == 1
    assert analytics.get_num_recommendations_by_status(uid, "Viewed") == 1
    assert analytics.get_num_recommendations_by_status(uid, "Dismissed") == 1


def test_get_num_schedules_counts_only_evaluations(app_ctx):
    from course_reg import analytics
    uid = _new_student(app_ctx, "sched@uci.edu")
    assert analytics.get_num_schedules(uid) == 0
    analytics.save_activity(uid, None, "Evaluation", "Schedule Version ", "details", "impact")
    analytics.save_activity(uid, None, "Viewed", "a rec", "details", "impact")
    assert analytics.get_num_schedules(uid) == 1   # only the Evaluation counts


# --- list getters --------------------------------------------------------------

def test_all_score_lists_ordered(app_ctx):
    from course_reg import analytics
    uid = _new_student(app_ctx, "lists@uci.edu")
    _save_metric(uid, workload=10.0, burnout=1.0, impact=0.5)
    _save_metric(uid, workload=30.0, burnout=5.0, impact=1.5)
    assert analytics.get_all_workloads(uid) == [10.0, 30.0]
    assert analytics.get_all_burnout_scores(uid) == [1.0, 5.0]
    assert analytics.get_all_impact_scores(uid) == [0.5, 1.5]
    assert len(analytics.get_all_dates(uid)) == 2


def test_get_all_recommendations(app_ctx):
    from course_reg import analytics
    uid = _new_student(app_ctx, "recs@uci.edu")
    _save_metric(uid, rec="first", status="Viewed")
    _save_metric(uid, rec="second", status="Applied")
    recs = analytics.get_all_recommendations(uid)
    assert len(recs) == 2
    # newest first; each tuple = (recommendation, rec_type, why, status, date)
    assert recs[0][0] == "second" and recs[0][3] == "Applied"
    assert all(len(t) == 5 for t in recs)


# --- save_activity version logic + get_latest_activities -----------------------

def test_activity_version_numbering(app_ctx):
    from course_reg import analytics
    uid = _new_student(app_ctx, "ver@uci.edu")
    analytics.save_activity(uid, None, "Evaluation", "Schedule Version ", "d", "i")   # v1
    analytics.save_activity(uid, None, "Viewed", "a rec", "d", "i")                    # reuses v1
    analytics.save_activity(uid, None, "Evaluation", "Schedule Version ", "d", "i")   # v2

    acts = analytics.get_latest_activities(uid)
    assert len(acts) == 3
    versions = [a[5] for a in acts]      # "V{n}", newest first
    assert versions[0] == "V2"
    descs = [a[2] for a in acts]
    assert "Schedule Version 2" in descs and "Schedule Version 1" in descs


def test_get_latest_activities_caps_at_five(app_ctx):
    from course_reg import analytics
    uid = _new_student(app_ctx, "cap@uci.edu")
    for _ in range(7):
        analytics.save_activity(uid, None, "Evaluation", "Schedule Version ", "d", "i")
    assert len(analytics.get_latest_activities(uid)) == 5


# --- edit_rec_status -----------------------------------------------------------

def test_edit_rec_status_updates_metric_and_activity(app_ctx):
    from course_reg import analytics
    uid = _new_student(app_ctx, "edit@uci.edu")
    mid = _save_metric(uid, status="Viewed")
    analytics.save_activity(uid, mid, "Viewed", "a rec", "d", "i")

    analytics.edit_rec_status(mid, "Applied")

    latest = analytics.get_latest_metric(uid)
    assert latest["status"] == "Applied"
    # the linked activity's type is flipped too
    con = sqlite3.connect(app_ctx)
    types = [r[0] for r in con.execute("SELECT type FROM activity WHERE metric_id=?", (mid,))]
    con.close()
    assert types == ["Applied"]


# --- get_improvement_summary ---------------------------------------------------

def test_get_improvement_summary_with_changes(app_ctx):
    from course_reg import analytics
    uid = _new_student(app_ctx, "imp@uci.edu")
    analytics.save_activity(uid, None, "Viewed", "a rec", "d", "i",
                            workload_change=5.0, burnout_change=1.0, impact_change=-0.5)
    summary = analytics.get_improvement_summary(uid)
    assert summary["workload_change"] == 5.0
    assert summary["burnout_change"] == 1.0
    assert summary["impact_change"] == -0.5


def test_get_improvement_summary_no_data_returns_null_row(app_ctx):
    from course_reg import analytics
    uid = _new_student(app_ctx, "noimp@uci.edu")
    summary = analytics.get_improvement_summary(uid)
    # the no-data path builds a Row of Nones rather than returning None
    assert summary is not None
    assert summary["workload_change"] is None
    assert summary["burnout_change"] is None
    assert summary["impact_change"] is None
