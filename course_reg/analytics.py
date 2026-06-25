import sqlite3
from typing import Optional
from datetime import datetime
from flask import current_app
from course_reg.db import get_db


def save_metrics(student_id: int, workload_score: float, burnout_score: float, burnout_explanation: str, impact_score: float, impact_explanation: str, recommendation: str, rec_type: str, bullet_summary: str, why_summary: str, table_summary: str):
    cursor = None
    try:
        db = get_db()
        query = """INSERT INTO metric (student_id, workload_score, burnout_score, burnout_explanation, impact_score, impact_explanation, recommendation, rec_type, bullet_summary, why_summary, table_summary, status, timestamp) VALUES (:student_id, :workload_score, :burnout_score, :burnout_explanation, :impact_score, :impact_explanation, :recommendation, :rec_type, :bullet_summary, :why_summary, :table_summary, :status, :timestamp);"""
        cursor = db.execute(query, {"student_id": student_id, "workload_score": workload_score, "burnout_score": burnout_score, "burnout_explanation": burnout_explanation, "impact_score": impact_score, "impact_explanation": impact_explanation, "recommendation": recommendation, "rec_type": rec_type, "bullet_summary": bullet_summary, "why_summary": why_summary, "table_summary": table_summary, "status": "Viewed", "timestamp": datetime.isoformat(datetime.now())})
        db.commit()
    except sqlite3.Error as e:
        db.rollback()
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not save metrics")
    finally:
        if cursor is not None:
            cursor.close()


def edit_rec_status(metric_id: int, new_status: str):
    cursor = None
    try:
        db = get_db()
        query = """UPDATE metric SET status = :new_status WHERE metric_id = :metric_id;"""
        cursor = db.execute(query, {"new_status": new_status, "metric_id": metric_id})
        db.commit()
    except sqlite3.Error as e:
        db.rollback()
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: could not edit recommendation status")
    finally:
        if cursor is not None:
            cursor.close()


def get_num_schedules(student_id: int) -> int:
    cursor = None
    try:
        db = get_db()
        query = """SELECT COUNT(*) FROM metric WHERE student_id = :student_id;"""
        cursor = db.execute(query, {"student_id": student_id})
        num_schedules = cursor.fetchone()
        return num_schedules[0]
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not fetch number of schedules")
    finally:
        if cursor is not None:
            cursor.close()


def get_latest_metric(student_id: int) -> Optional[sqlite3.Row]:
    cursor = None
    try:
        db = get_db()
        query = """SELECT workload_score, burnout_score, burnout_explanation, impact_score, impact_explanation, recommendation, rec_type, bullet_summary, why_summary, table_summary, timestamp FROM metric WHERE student_id = :student_id ORDER BY timestamp DESC LIMIT 1;"""
        cursor = db.execute(query, {"student_id": student_id})
        latest_activity = cursor.fetchone()
        return latest_activity
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not fetch latest metrics")
    finally:
        if cursor is not None:
            cursor.close()


def get_all_workloads(student_id: int) -> list[float]:
    cursor = None
    try:
        db = get_db()
        query = """SELECT workload_score FROM metric WHERE student_id = :student_id ORDER BY timestamp;"""
        cursor = db.execute(query, {"student_id": student_id})
        workloads_raw = cursor.fetchall()

        workloads = []
        for score in workloads_raw:
            workloads.append(round(score[0], 2))

        return workloads
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not fetch workloads")
    finally:
        if cursor is not None:
            cursor.close()


def get_all_burnout_scores(student_id: int) -> list[float]:
    cursor = None
    try:
        db = get_db()
        query = """SELECT burnout_score FROM metric WHERE student_id = :student_id ORDER BY timestamp;"""
        cursor = db.execute(query, {"student_id": student_id})
        burnouts_raw = cursor.fetchall()

        burnout_scores = []
        for score in burnouts_raw:
            burnout_scores.append(round(score[0], 2))

        return burnout_scores
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not fetch burnout scores")
    finally:
        if cursor is not None:
            cursor.close()


def get_all_impact_scores(student_id: int) -> list[float]:
    cursor = None
    try:
        db = get_db()
        query = """SELECT impact_score FROM metric WHERE student_id = :student_id ORDER BY timestamp;"""
        cursor = db.execute(query, {"student_id": student_id})
        impacts_raw = cursor.fetchall()

        impact_scores = []
        for score in impacts_raw:
            impact_scores.append(round(score[0], 2))

        return impact_scores
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not fetch impact scores")
    finally:
        if cursor is not None:
            cursor.close()

def get_all_dates(student_id: int) -> list[str]:
    cursor = None
    try:
        db = get_db()
        query = """SELECT timestamp FROM metric WHERE student_id = :student_id ORDER BY timestamp;"""
        cursor = db.execute(query, {"student_id": student_id})
        timestamps_raw = cursor.fetchall()

        dates = []
        for timestamp in timestamps_raw:
            date = datetime.fromisoformat(timestamp[0])
            dates.append(f"{date.strftime('%b')} {date.day}")

        return dates
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not fetch dates")
    finally:
        if cursor is not None:
            cursor.close()


def get_all_recommendations(student_id: int) -> list[tuple[str, str, str, str, str]]:
    cursor = None
    try:
        db = get_db()
        query = """SELECT recommendation, rec_type, why_summary, status, timestamp FROM metric WHERE student_id = :student_id ORDER BY timestamp DESC;"""
        cursor = db.execute(query, {"student_id": student_id})
        recommendations_raw = cursor.fetchall()

        recommendations = []
        for raw_rec in recommendations_raw:
            date = datetime.fromisoformat(raw_rec["timestamp"])
            rec_tup = (raw_rec["recommendation"], raw_rec["rec_type"], raw_rec["why_summary"], raw_rec['status'], f"{date.strftime('%b')} {date.day}, {date.year}")
            recommendations.append(rec_tup)

        return recommendations
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not fetch recommendations")
    finally:
        if cursor is not None:
            cursor.close()