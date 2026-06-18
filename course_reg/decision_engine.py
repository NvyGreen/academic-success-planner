import sqlite3
from collections import namedtuple
from flask import current_app
from course_reg.db import get_db
from course_reg import logic

BurnoutComparison = namedtuple('BurnoutComparison', ['course_name', 'difficulty', 'estimated_hours_per_week'])
WorkloadComparison = namedtuple('WorkloadComparison', ['course_name', 'estimated_hours_per_week'])

def find_highest_burnout(courses):
    if not courses:
        return
    
    cursor = None
    try:
        db = get_db()
        placeholders = ", ".join([f":code_{i}" for i in range(len(courses))])
        query = f"""SELECT d.abbreviation, c.course_number, c.difficulty_score, c.estimated_hours_per_week FROM course c JOIN department d ON c.department_id = d.department_id WHERE course_code IN ({placeholders})"""
        values = {f"code_{i}": code for i, code in enumerate(courses)}
        cursor = db.execute(query, values)
        course_data = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not find course with highest burnout risk")
    finally:
        if cursor is not None:
            cursor.close()
    
    max_course = BurnoutComparison('Easy lab', 1, 0.0)
    for course in course_data:
        if course['difficulty'] > max_course.difficulty:
            max_course = BurnoutComparison(f"{course['abbreviation']} {course['course_number']}", course['difficulty'], course['estimated_hours_per_week'])
        elif course['difficulty'] == max_course.difficulty and course['estimated_hours_per_week'] == max_course.estimated_hours_per_week:
            max_course = BurnoutComparison(f"{course['abbreviation']} {course['course_number']}", course['difficulty'], course['estimated_hours_per_week'])
    
    return max_course.course_name


def find_highest_workload(courses):
    if not courses:
        return

    cursor = None
    try:
        db = get_db()
        placeholders = ", ".join([f":code_{i}" for i in range(len(courses))])
        query = f"""SELECT d.abbreviation, c.course_number, c.estimated_hours_per_week FROM course c JOIN department d ON c.department_id = d.department_id WHERE course_code IN ({placeholders})"""
        values = {f"code_{i}": code for i, code in enumerate(courses)}
        cursor = db.execute(query, values)
        course_data = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not find course with highest workload")
    finally:
        if cursor is not None:
            cursor.close()
    
    max_course = WorkloadComparison('Easy lab', 0.0)
    for course in course_data:
        if course['estimated_hours_per_week'] > max_course.estimated_hours_per_week:
            max_course = WorkloadComparison(f"{course['abbreviation']} {course['course_number']}", course['estimated_hours_per_week'])
    
    return max_course.course_name


def choose_drop_or_swap(courses):
    workload = logic.total_hours_per_week(courses)
    burnout = logic.calculate_burnout_risk(courses)

    if workload > logic.WORKLOAD_HEAVY_THRESHOLD and burnout > logic.BURNOUT_COURSES_HIGH_THRESHOLD:
        if workload > (10 * burnout - 5):
            return "Drop"
        else:
            return "Swap"
    elif workload > logic.WORKLOAD_HEAVY_THRESHOLD:
        return "Drop"
    elif burnout > logic.BURNOUT_COURSES_HIGH_THRESHOLD:
        return "Swap"
    
    return "Balanced"