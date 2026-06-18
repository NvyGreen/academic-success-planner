import sqlite3
from collections import namedtuple
from flask import current_app
from course_reg.db import get_db
from course_reg.register_methods import check_prereqs
from course_reg import logic

BurnoutComparison = namedtuple('BurnoutComparison', ['course_id','course_name', 'difficulty', 'estimated_hours_per_week'])
WorkloadComparison = namedtuple('WorkloadComparison', ['course_name', 'estimated_hours_per_week'])

def find_highest_burnout(courses):
    if not courses:
        return
    
    cursor = None
    try:
        db = get_db()
        placeholders = ", ".join([f":code_{i}" for i in range(len(courses))])
        query = f"""SELECT c.course_id, d.abbreviation, c.course_number, c.difficulty_score, c.estimated_hours_per_week FROM course c JOIN department d ON c.department_id = d.department_id WHERE course_code IN ({placeholders})"""
        values = {f"code_{i}": code for i, code in enumerate(courses)}
        cursor = db.execute(query, values)
        course_data = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not find course with highest burnout risk")
    finally:
        if cursor is not None:
            cursor.close()
    
    max_course = BurnoutComparison(0, 'Easy lab', 1, 0.0)
    for course in course_data:
        if course['difficulty'] > max_course.difficulty:
            max_course = BurnoutComparison(course['course_id'], f"{course['abbreviation']} {course['course_number']}", course['difficulty'], course['estimated_hours_per_week'])
        elif course['difficulty'] == max_course.difficulty and course['estimated_hours_per_week'] == max_course.estimated_hours_per_week:
            max_course = BurnoutComparison(course['course_id'], f"{course['abbreviation']} {course['course_number']}", course['difficulty'], course['estimated_hours_per_week'])
    
    return max_course


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
    
    return max_course


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


def find_course_to_swap(user_id, old_course: BurnoutComparison):
    course_dep, course_num = old_course.course_name.split()
    cursor = None

    try:
        db = get_db()
        query = """
            SELECT c.course_id, d.abbreviation, c.course_number
            FROM course c
            JOIN department d ON c.department_id = d.department_id
            WHERE d.abbreviation = :abbreviation
            AND (c.difficulty_score < :difficulty_score
                OR c.estimated_hours_per_week < :estimated_hours_per_week)
            AND c.course_number <> :course_number
            AND c.credits <> 0;
        """
        cursor = db.execute(query, {"abbreviation": course_dep, "difficulty_score": old_course.difficulty, "estimated_hours_per_week": old_course.estimated_hours_per_week, "course_number": course_num})
        course_data = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not find course to swap")
    finally:
        if cursor is not None:
            cursor.close()
    
    if len(course_data == 0):
        # TODO: Check school next
        try:
            db = get_db()
            query = """
                SELECT s.school_id
                FROM course c
                JOIN department d ON c.department_id = d.department_id
                JOIN school s ON d.school_id = s.school_id
                WHERE d.abbreviation = :abbreviation
                AND c.course_number = :course_number;
            """
            cursor = db.execute(query, {"abbreviation": course_dep, "course_number": course_num})
            school_id = cursor.fetchone()
            if school_id is not None:
                school_id = school_id[0]
            else:
                raise sqlite3.Error("Could not find school")
            
            query = """
                SELECT c.course_id, d.abbreviation, c.course_number
                FROM course c
                JOIN department d ON c.department_id = d.department_id
                WHERE s.school_id = :school_id
                AND (c.difficulty_score < :difficulty_score
                    OR c.estimated_hours_per_week < :estimated_hours_per_week)
                AND c.course_number <> :course_number
                AND c.credits <> 0;
            """
            cursor = db.execute(query, {"school_id": school_id, "difficulty_score": old_course.difficulty, "estimated_hours_per_week": old_course.estimated_hours_per_week, "course_number": course_num})
            course_data = cursor.fetchall()

            if len(course_data) == 0:
                raise sqlite3.Error("Error: Could not find course to swap")
        except sqlite3.Error as e:
            current_app.logger.error(f"Database error: {e}")
            raise sqlite3.Error("Error: Could not find course to swap")
        finally:
            if cursor is not None:
                cursor.close()
    
    potential_swaps = {}
    for course in course_data:
        prereqs_check = check_prereqs(user_id, course["course_id"])
        if len(prereqs_check) == 0:
            potential_swaps[course["course_id"]] = f"{course["abbreviation"]} {course["course_number"]}"
    
    closest = min(prereqs_check.keys(), key=lambda n: abs(n - old_course.course_id))
    return potential_swaps[closest]


def generate_detailed_recommendation(user_id, courses):
    rec_type = choose_drop_or_swap(courses)

    if rec_type == "Balanced":
        return "Light/Balanced schedule"
    elif rec_type == "Swap":
        try:
            old_course = find_highest_burnout(courses)
            new_course = find_course_to_swap(user_id, old_course)
            return f"Swap {old_course.course_name} with {new_course}"
        except sqlite3.Error as e:
            pass

    drop_course = find_highest_workload(courses)
    return f"Drop {drop_course.course_name}"