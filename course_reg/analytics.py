import sqlite3
from datetime import datetime
from flask import current_app
from course_reg.db import get_db



def save_metrics(student_id, workload_score, burnout_score, impact_score, recommendation_count):
    cursor = None
    try:
        db = get_db()
        query = """INSERT INTO metric (student_id, workload_score, burnout_score, impact_score, recommendations, timestamp) VALUES (:student_id, :workload_score, :burnout_score, :impact_score, :timestamp);"""
        cursor = db.execute(query, {"student_id": student_id, "workload_score": workload_score, "burnout_score": burnout_score, "impact_score": impact_score, "recommendations": recommendation_count, "timestamp": datetime.isoformat(datetime.now())})
        db.commit()
    except sqlite3.Error as e:
        db.rollback()
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not save metrics")
    finally:
        if cursor is not None:
            cursor.close()


def get_metrics(student_id):
    cursor = None
    try:
        db = get_db()
        query = """SELECT COUNT(*) FROM metric WHERE student_id = :student_id;"""
        cursor = db.execute(query, {"student_id": student_id})
        num_schedules = cursor.fetchone()[0]

        query = """SELECT workload_score, burnout_score, impact_score, recommendations, timestamp FROM metric WHERE student_id = :student_id;"""
        cursor = db.execute(query, {"student_id": student_id})
        overtime_data = cursor.fetchall()

        return (num_schedules, overtime_data)
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not fetch metrics")
    finally:
        if cursor is not None:
            cursor.close()