import sqlite3
from datetime import datetime
from flask import current_app
from course_reg.db import get_db


def save_metrics(student_id, workload_score, burnout_score, impact_score):
    cursor = None
    try:
        db = get_db()
        query = """INSERT INTO metric (student_id, workload_score, burnout_score, impact_score, timestamp) VALUES (:student_id, :workload_score, :burnout_score, :impact_score, :timestamp);"""
        cursor = db.execute(query, {"student_id": student_id, "workload_score": workload_score, "burnout_score": burnout_score, "impact_score": impact_score, "timestamp": datetime.isoformat(datetime.now())})
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not save metrics")
    finally:
        db.rollback()
        if cursor is not None:
            cursor.close()