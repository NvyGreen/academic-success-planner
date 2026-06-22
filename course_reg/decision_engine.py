import sqlite3
from typing import NamedTuple
from flask import current_app
from course_reg.db import get_db
from course_reg import register_methods
from course_reg import logic


class BurnoutComparison(NamedTuple):
    course_id: int
    course_name: str
    difficulty: int
    estimated_hours_per_week: float

class WorkloadComparison(NamedTuple):
    course_name: str
    estimated_hours_per_week: float

class ScheduleComparison(NamedTuple):
    workload: float
    burnout: float
    impact: float


def find_highest_burnout(courses: list[int]) -> BurnoutComparison:
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
    
    max_course = BurnoutComparison(0, 'Easy lab', 0, -1.0)
    for course in course_data:
        if course['difficulty_score'] > max_course.difficulty:
            max_course = BurnoutComparison(course['course_id'], f"{course['abbreviation']} {course['course_number']}", course['difficulty_score'], course['estimated_hours_per_week'])
        elif course['difficulty_score'] == max_course.difficulty and course['estimated_hours_per_week'] > max_course.estimated_hours_per_week:
            max_course = BurnoutComparison(course['course_id'], f"{course['abbreviation']} {course['course_number']}", course['difficulty_score'], course['estimated_hours_per_week'])
    
    return max_course


def find_highest_workload(courses: list[int]) -> WorkloadComparison:
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
    
    max_course = WorkloadComparison('Easy lab', -1.0)
    for course in course_data:
        if course['estimated_hours_per_week'] > max_course.estimated_hours_per_week:
            max_course = WorkloadComparison(f"{course['abbreviation']} {course['course_number']}", course['estimated_hours_per_week'])
    
    return max_course


def choose_drop_or_swap(courses: list[int]) -> str:
    workload = logic.total_hours_per_week(courses)
    burnout = logic.calculate_burnout_risk(courses)[0]

    if workload > logic.WORKLOAD_HEAVY_THRESHOLD and burnout > logic.BURNOUT_MEDIUM_THRESHOLD:
        if workload > (10 * burnout - 5):
            return "Drop"
        else:
            return "Swap"
    elif workload > logic.WORKLOAD_HEAVY_THRESHOLD:
        return "Drop"
    elif burnout > logic.BURNOUT_MEDIUM_THRESHOLD:
        return "Swap"
    
    return "Balanced"


def find_course_to_swap(user_id, old_course: BurnoutComparison, courses: list[int]) -> BurnoutComparison:
    course_dep, course_num = old_course.course_name.rsplit(" ", 1)
    cursor = None

    try:
        db = get_db()
        placeholders = ", ".join([f":code_{i}" for i in range(len(courses))])
        query = f"""
            SELECT c.course_id, d.abbreviation, c.course_number, c.difficulty_score, c.estimated_hours_per_week
            FROM course c
            JOIN department d ON c.department_id = d.department_id
            WHERE d.abbreviation = :abbreviation
            AND (c.difficulty_score < :difficulty_score
                OR c.estimated_hours_per_week < :estimated_hours_per_week)
            AND c.course_number <> :course_number
            AND c.credits <> 0
            AND c.course_code NOT IN ({placeholders});
        """

        values = {f"code_{i}": code for i, code in enumerate(courses)}
        values["abbreviation"] = course_dep
        values["difficulty_score"] = old_course.difficulty
        values["estimated_hours_per_week"] = old_course.estimated_hours_per_week
        values["course_number"] = course_num

        cursor = db.execute(query, values)
        course_data = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not find course to swap")
    finally:
        if cursor is not None:
            cursor.close()
    
    if len(course_data) == 0:
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
            
            placeholders = ", ".join([f":code_{i}" for i in range(len(courses))])
            query = f"""
                SELECT c.course_id, d.abbreviation, c.course_number, c.difficulty_score, c.estimated_hours_per_week
                FROM course c
                JOIN department d ON c.department_id = d.department_id
                JOIN school s ON d.school_id = s.school_id
                WHERE s.school_id = :school_id
                AND (c.difficulty_score < :difficulty_score
                    OR c.estimated_hours_per_week < :estimated_hours_per_week)
                AND c.course_number <> :course_number
                AND c.credits <> 0
                AND c.course_code NOT IN ({placeholders});
            """

            values = {f"code_{i}": code for i, code in enumerate(courses)}
            values["school_id"] = school_id
            values["difficulty_score"] = old_course.difficulty
            values["estimated_hours_per_week"] = old_course.estimated_hours_per_week
            values["course_number"] = course_num

            cursor = db.execute(query, values)
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
        prereqs_check = register_methods.check_prereqs(user_id, course["course_id"])
        if len(prereqs_check) == 0:
            potential_swaps[course["course_id"]] = BurnoutComparison(course['course_id'], f"{course['abbreviation']} {course['course_number']}", course['difficulty_score'], course['estimated_hours_per_week'])
    
    try:
        closest = min(potential_swaps.keys(), key=lambda n: abs(n - old_course.course_id))
        return potential_swaps[closest]
    except ValueError:
        raise sqlite3.Error("Error: Could not find course to swap")


def generate_detailed_recommendation(user_id: int, courses: list[int]) -> str:
    rec_type = choose_drop_or_swap(courses)

    if rec_type == "Balanced":
        return "Light/Balanced schedule"
    elif rec_type == "Swap":
        try:
            old_course = find_highest_burnout(courses)
            new_course = find_course_to_swap(user_id, old_course, courses)
            return f"Swap {old_course.course_name} with {new_course.course_name}"
        except sqlite3.Error as e:
            current_app.logger.error(f"Database error: {e}")
        except AttributeError as e:
            current_app.logger.error(f"Attribute Error: {e}")

    try:
        drop_course = find_highest_workload(courses)
        return f"Drop {drop_course.course_name}"
    except AttributeError as e:
        current_app.logger.error(f"Attribute Error: {e}")
        return "No courses added!"


def get_course_codes_from_ids(course_ids: list[int]) -> list[int]:
    if len(course_ids) == 0:
        return []
    
    query = """SELECT course_code FROM course WHERE """
    placeholders = ", ".join([f":id_{i}" for i in range(len(course_ids))])
    query += f"course_id IN ({placeholders})"
    values = {f"id_{i}": course_id for i, course_id in enumerate(course_ids)}
    cursor = None

    try:
        db = get_db()
        cursor = db.execute(query, values)
        courses_raw = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not fetch course codes from IDs")
    finally:
        if cursor is not None:
            cursor.close()
    
    course_codes = []
    for code in courses_raw:
        course_codes.append(code["course_code"])
    
    return course_codes


def swap_course(user_id, old_course: BurnoutComparison, new_course: BurnoutComparison):
    cursor = None
    try:
        db = get_db()        
        query = """SELECT coreq_id FROM corequisite WHERE course_id = :old_id;"""
        cursor = db.execute(query, {"old_id": old_course.course_id})
        old_coreqs = cursor.fetchall()
        old_courses = [old_course.course_id]
        for coreq in old_coreqs:
            old_courses.append(coreq["coreq_id"])
        old_course_codes = get_course_codes_from_ids(old_courses)

        query = """SELECT coreq_id FROM corequisite WHERE course_id = :new_id;"""
        cursor = db.execute(query, {"new_id": new_course.course_id})
        new_coreqs = cursor.fetchall()
        new_courses = [new_course.course_id]
        for coreq in new_coreqs:
            new_courses.append(coreq["coreq_id"])
        new_course_codes = get_course_codes_from_ids(new_courses)

        unreged_courses = register_methods.register_courses(user_id, new_course_codes)
        if isinstance(unreged_courses, dict) and len(unreged_courses) > 0:
            raise sqlite3.Error("Error: Could not swap courses")

        for code in old_course_codes:
            register_methods.drop_course(user_id, code)

    except sqlite3.Error as e:
        db.rollback()
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not swap courses")
    finally:
        if cursor is not None:
            cursor.close()


def get_old_and_new_schedule_stats(user_id: int, courses: list[int], old_course: int, new_course: int=-1) -> tuple[ScheduleComparison, ScheduleComparison]:
    old_schedule = ScheduleComparison(logic.total_hours_per_week(courses), logic.calculate_burnout_risk(courses)[0], logic.calculate_academic_impact(courses, user_id))

    course_ids = [old_course]
    if new_course != -1:
        course_ids.append(new_course)
    course_codes = get_course_codes_from_ids(course_ids)
    new_courses = courses.copy()
    new_courses.remove(course_codes[0])
    if len(course_codes) > 1:
        new_courses.append(course_codes[1])
    
    new_schedule = ScheduleComparison(logic.total_hours_per_week(new_courses), logic.calculate_burnout_risk(new_courses)[0], logic.calculate_academic_impact(new_courses, user_id))

    return old_schedule, new_schedule


def compare_schedules(old_schedule: ScheduleComparison, new_schedule: ScheduleComparison) -> ScheduleComparison:
    return ScheduleComparison(old_schedule.workload - new_schedule.workload, old_schedule.burnout - new_schedule.burnout, old_schedule.impact - new_schedule.impact)


def generate_change_summary(old_schedule: ScheduleComparison, new_schedule: ScheduleComparison):
    difference = compare_schedules(old_schedule, new_schedule)
    old_burnout_cat = logic.estimate_burnout_risk(old_schedule.burnout)
    new_burnout_cat = logic.estimate_burnout_risk(new_schedule.burnout)

    bullet_summary = []
    if difference.workload > 0:
        bullet_summary.append(f"Reduces weekly workload by ~{round(difference.workload, 2)} hours")
    elif difference.workload < 0:
        bullet_summary.append(f"Increases weekly workload by ~{round(difference.workload, 2) * -1} hours")
    
    if difference.burnout > 1 and new_schedule.burnout < logic.BURNOUT_HIGH_THRESHOLD:
        bullet_summary.append(f"Lowers burnout risk from {old_burnout_cat} to {new_burnout_cat}")
    elif difference.burnout < -1 and new_schedule.burnout >= logic.BURNOUT_HIGH_THRESHOLD:
        bullet_summary.append(f"Increases burnout risk from {old_burnout_cat} to {new_burnout_cat}")

    if difference.impact < 0:
        bullet_summary.append("Improves academic impact")
    elif difference.impact > 0:
        bullet_summary.append("Decreases academic impact")


    table_summary = [["Metric", "Current Schedule", "With Recommendation", "Change"]]

    table_summary.append(["Workload", f"{old_schedule.workload} hrs/week", f"{new_schedule.workload} hrs/week", f"{difference.workload * -1:+} hrs"])

    table_summary.append(["Burnout Risk", f"{old_burnout_cat} ({old_schedule.burnout})", f"{new_burnout_cat} ({new_schedule.burnout})", f"{difference.burnout * -1:+}"])

    old_impact_cat = logic.classify_academic_impact(old_schedule.impact)
    new_impact_cat = logic.classify_academic_impact(new_schedule.impact)
    table_summary.append(["Academic", f"{old_impact_cat} ({old_schedule.impact})", f"{new_impact_cat} ({new_schedule.impact})", f"{difference.impact * -1:+}"])

    return bullet_summary, table_summary