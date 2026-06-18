import sqlite3
from flask import current_app
from course_reg.db import get_db

def find_highest_burnout(courses):
    if not courses:
        return None
    
    cursor = None
    try:
        db = get_db()
        placeholders = ", ".join([f":code_{i}" for i in range(len(courses))])
        query = f"SELECT credits, difficulty_score FROM course WHERE course_code IN ({placeholders})"
        values = {f"code_{i}": code for i, code in enumerate(courses)}
        cursor = db.execute(query, values)
        course_data = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not find course with highest burnout")
    finally:
        if cursor is not None:
            cursor.close()