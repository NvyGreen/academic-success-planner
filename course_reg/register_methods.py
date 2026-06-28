import sqlite3
from datetime import datetime
from flask import current_app
from course_reg.db import get_db
from course_reg import schedule_methods, logic, analytics, decision_engine, utility


def get_course_description(course_id: int) -> str:
    query = """SELECT department_id, course_number, type FROM course WHERE course_id = :course_id;"""
    cursor = None
    try:
        db = get_db()
        cursor = db.execute(query, {"course_id": course_id})
        dept_info = cursor.fetchone()
        cursor.close()
        if dept_info is None:
            raise sqlite3.Error("Error: Could not register for courses")

        query = """SELECT abbreviation FROM department WHERE department_id = :department_id;"""
        cursor = db.execute(query, {"department_id": dept_info["department_id"]})
        abbreviation = cursor.fetchone()
        if abbreviation is None:
            raise sqlite3.Error("Error: Could not register for courses")
        abbreviation = abbreviation["abbreviation"]
        course_desc = abbreviation + " " + dept_info["course_number"] + " (" + dept_info["type"] + ")"
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not register for courses")
    finally:
        if cursor is not None:
            cursor.close()

    return course_desc


def register_courses(user_id: int, course_codes: list[int]) -> dict:
    if len(course_codes) == 0:
        return {}
    
    placeholders = ", ".join([f":code_{i}" for i in range(len(course_codes))])
    query = f"SELECT course_id FROM course WHERE course_code IN ({placeholders})"
    values = {f"code_{i}": code for i, code in enumerate(course_codes)}
    cursor = None

    try:
        db = get_db()
        cursor = db.execute(query, values)
        course_ids_raw = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not register for courses")
    finally:
        if cursor is not None:
            cursor.close()
    
    unreged_courses = {}
    course_ids = []
    for raw_id in course_ids_raw:
        course_ids.append(raw_id["course_id"])

    for course_id in course_ids:
        prereqs_check = check_prereqs(user_id, course_id)
        coreqs_check = check_coreqs(course_id, course_ids)
        conflicts_check = check_conflicts(user_id, course_id)

        if len(prereqs_check) > 0:
            course_desc = get_course_description(course_id)
            prereqs = "Following prerequisites not satisfied: " + ", ".join(prereqs_check)
            unreged_courses[course_desc] = prereqs
        elif len(coreqs_check) > 0:
            course_desc = get_course_description(course_id)
            coreqs = "Following corequisites not satisfied: " + ", ".join(coreqs_check)
            unreged_courses[course_desc] = coreqs
        elif len(conflicts_check) > 0:
            course_desc = get_course_description(course_id)
            conflicts = "Time conflict with: " + ", ".join(conflicts_check)
            unreged_courses[course_desc] = conflicts
        else:
            try:
                db = get_db()
                query = """INSERT OR IGNORE INTO enrollment (student_id, course_id) VALUES (:student_id, :course_id);"""
                cursor = db.execute(query, {"student_id": user_id, "course_id": course_id})
                inserted = cursor.rowcount
                cursor.close()

                if inserted:
                    query = """UPDATE course SET num_enrolled = num_enrolled + 1 WHERE course_id = :course_id;"""
                    cursor = db.execute(query, {"course_id": course_id})

                db.commit()
            except sqlite3.Error as e:
                db.rollback()
                current_app.logger.error(f"Database error: {e}")
                raise sqlite3.Error("Error: Could not register for courses")
            finally:
                cursor.close()
    
    if len(unreged_courses) == 0:
        return "Success"

    return unreged_courses


def check_coreqs(course_id: int, all_ids: list[int]) -> list[int]:
    cursor = None
    try:
        db = get_db()
        query = """SELECT coreq_id FROM corequisite WHERE course_id = :course_id;"""
        cursor = db.execute(query, {"course_id": course_id})
        coreqs = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not register for courses")
    finally:
        if cursor is not None:
            cursor.close()

    if len(coreqs) == 0:
        return []

    unfilled_coreqs = []    
    for coreq in coreqs:
        if coreq["coreq_id"] not in all_ids:
            course_desc = get_course_description(coreq["coreq_id"])
            unfilled_coreqs.append(course_desc)
    
    return unfilled_coreqs


def check_prereqs(user_id: int, course_id: int) -> list[int]:
    cursor = None
    try:
        db = get_db()
        query = """SELECT prereq_id FROM prerequisite WHERE course_id = :course_id;"""
        cursor = db.execute(query, {"course_id": course_id})
        prereqs = cursor.fetchall()
        cursor.close()
        
        if len(prereqs) == 0:
            return []
        
        unfilled_prereqs = []
        query = """SELECT course_id FROM prev_enrollment WHERE student_id = :student_id;"""
        cursor = db.execute(query, {"student_id": user_id})
        prev_courses_raw = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not register for courses")
    finally:
        if cursor is not None:
            cursor.close()
    
    prev_courses = []
    for raw_course in prev_courses_raw:
        prev_courses.append(raw_course["course_id"])

    for prereq in prereqs:
        if prereq["prereq_id"] not in prev_courses:
            course_desc = get_course_description(prereq[0])
            unfilled_prereqs.append(course_desc)

    return unfilled_prereqs


DAY_TWO_CHAR = ("Su", "Tu", "Th", "Sa")
DAY_ONE_CHAR = ("M", "W", "F")


def parse_meeting_days(days_str: str) -> set:
    # Days are stored as concatenated tokens like "MWF" or "TuWTh"; split them into a
    # set, matching the two-character tokens (Su/Tu/Th/Sa) before the single ones.
    days = set()
    if not days_str:
        return days
    i = 0
    while i < len(days_str):
        if days_str[i:i + 2] in DAY_TWO_CHAR:
            days.add(days_str[i:i + 2])
            i += 2
        elif days_str[i] in DAY_ONE_CHAR:
            days.add(days_str[i])
            i += 1
        else:
            i += 1
    return days


def check_conflicts(user_id: int, course_id: int) -> list[str]:
    cursor = None
    try:
        db = get_db()
        query = """SELECT days, start_time, end_time FROM course WHERE course_id = :course_id;"""
        cursor = db.execute(query, {"course_id": course_id})
        candidate = cursor.fetchone()
        cursor.close()

        # A course with no scheduled meeting time can't conflict with anything.
        if candidate is None or candidate["days"] is None or candidate["start_time"] is None or candidate["end_time"] is None:
            return []

        # Compare against everything the student is already enrolled in. Because
        # register_courses enrolls accepted courses as it goes, this also catches
        # conflicts between two courses within the same registration batch.
        query = """
            SELECT c.course_id, c.days, c.start_time, c.end_time
            FROM enrollment e
            JOIN course c ON e.course_id = c.course_id
            WHERE e.student_id = :student_id;
        """
        cursor = db.execute(query, {"student_id": user_id})
        enrolled = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not register for courses")
    finally:
        if cursor is not None:
            cursor.close()

    cand_days = parse_meeting_days(candidate["days"])
    cand_start = datetime.fromisoformat(candidate["start_time"]).time()
    cand_end = datetime.fromisoformat(candidate["end_time"]).time()

    conflicts = []
    for course in enrolled:
        # Skip the course itself (re-registration) and anything without a meeting time.
        if course["course_id"] == course_id or course["days"] is None or course["start_time"] is None or course["end_time"] is None:
            continue

        # No shared meeting day means they can never overlap.
        if not (cand_days & parse_meeting_days(course["days"])):
            continue

        other_start = datetime.fromisoformat(course["start_time"]).time()
        other_end = datetime.fromisoformat(course["end_time"]).time()

        # Half-open overlap: no clash if one ends at or before the other starts.
        if cand_start < other_end and other_start < cand_end:
            conflicts.append(get_course_description(course["course_id"]))

    return conflicts


def drop_course(user_id: int, course_code: int):
    cursor = None
    try:
        db = get_db()
        query = """SELECT course_id FROM course WHERE course_code = :course_code;"""
        cursor = db.execute(query, {"course_code": course_code})
        course_id = cursor.fetchone()
        if course_id is None:
            raise sqlite3.Error("Error: Could not drop course")
        course_id = course_id["course_id"]
        cursor.close()
        
        query = """DELETE FROM enrollment WHERE student_id = :student_id AND course_id = :course_id;"""
        cursor = db.execute(query, {"student_id": user_id, "course_id": course_id})
        deleted = cursor.rowcount
        cursor.close()

        if deleted:
            # Decrement by the number of rows actually removed so the counter stays
            # correct even if duplicate enrollments ever slipped in.
            query = """UPDATE course SET num_enrolled = num_enrolled - :deleted WHERE course_id = :course_id;"""
            cursor = db.execute(query, {"course_id": course_id, "deleted": deleted})

        db.commit()
    except sqlite3.Error as e:
        db.rollback()
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not drop course")
    finally:
        if cursor is not None:
            cursor.close()


def waitlist_course(user_id: int, course_code: int):
    cursor = None
    try:
        db = get_db()

        query = """SELECT course_id FROM course WHERE course_code = :course_code;"""
        cursor = db.execute(query, {"course_code": course_code})
        course_id = cursor.fetchone()
        if course_id is None:
            raise sqlite3.Error("Error: Could not waitlist course")
        course_id = course_id["course_id"]
        cursor.close()

        query = """
            INSERT INTO student_waitlist (student_id, course_id, position)
            SELECT :student_id, :course_id, COALESCE(MAX(position), 0) + 1
            FROM student_waitlist
            WHERE course_id = :course_id;
        """
        cursor = db.execute(query, {"student_id": user_id, "course_id": course_id})
        cursor.close()

        query = """UPDATE course SET waitlist = waitlist + 1 WHERE course_code = :course_code;"""
        cursor = db.execute(query, {"course_code": course_code})
        cursor.close()

        db.commit()
    except sqlite3.Error as e:
        db.rollback()
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not waitlist course")
    finally:
        if cursor is not None:
            cursor.close()


def drop_waitlist(user_id: int, course_code: int):
    cursor = None
    try:
        db = get_db()
        query = """UPDATE course SET waitlist = waitlist - 1 WHERE course_code = :course_code;"""
        cursor = db.execute(query, {"course_code": course_code})
        cursor.close()

        query = """SELECT course_id FROM course WHERE course_code = :course_code;"""
        cursor = db.execute(query, {"course_code": course_code})
        course_id = cursor.fetchone()
        if course_id is None:
            raise sqlite3.Error("Error: Could not drop course from waitlist")
        course_id = course_id["course_id"]
        cursor.close()

        query = """SELECT position FROM student_waitlist WHERE student_id = :student_id AND course_id = :course_id;"""
        cursor = db.execute(query, {"student_id": user_id, "course_id": course_id})
        old_pos = cursor.fetchone()
        if old_pos is None:
            raise sqlite3.Error("Error: Could not drop course from waitlist")
        old_pos = old_pos["position"]
        cursor.close()

        query = """DELETE FROM student_waitlist WHERE student_id = :student_id AND course_id = :course_id;"""
        cursor = db.execute(query, {"student_id": user_id, "course_id": course_id})
        cursor.close()

        query = """UPDATE student_waitlist SET position = position - 1 WHERE course_id = :course_id AND position > :position;"""
        cursor = db.execute(query, {"course_id": course_id, "position": old_pos})

        db.commit()
    except sqlite3.Error as e:
        db.rollback()
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not drop course from waitlist")
    finally:
        if cursor is not None:
            cursor.close()


def enroll_from_waitlist():
    cursor = None
    try:
        db = get_db()
        query = """SELECT course_id, num_enrolled, capacity FROM course WHERE num_enrolled < capacity;"""
        cursor = db.execute(query)
        courses = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: could not enroll in course from waitlist")
    finally:
        if cursor is not None:
            cursor.close()

    promoted_students = []
    for course in courses:
        course_id = course["course_id"]
        open_seats = course["capacity"] - course["num_enrolled"]

        # Fill each open seat from the front of the waitlist until the course
        # is full or the waitlist runs out.
        for _ in range(open_seats):
            cursor = None
            try:
                db = get_db()

                query = """SELECT student_id FROM student_waitlist WHERE course_id = :course_id AND position = 1;"""
                cursor = db.execute(query, {"course_id": course_id})
                student_row = cursor.fetchone()
                cursor.close()

                if student_row is None:
                    break  # waitlist empty - nothing more to promote for this course

                student_id = student_row["student_id"]

                # Drop from waitlist and shift everyone behind them up one spot
                query = """DELETE FROM student_waitlist WHERE student_id = :student_id AND course_id = :course_id;"""
                cursor = db.execute(query, {"student_id": student_id, "course_id": course_id})
                cursor.close()

                query = """UPDATE course SET waitlist = waitlist - 1 WHERE course_id = :course_id;"""
                cursor = db.execute(query, {"course_id": course_id})
                cursor.close()

                query = """UPDATE student_waitlist SET position = position - 1 WHERE course_id = :course_id;"""
                cursor = db.execute(query, {"course_id": course_id})
                cursor.close()

                # Add to enrollment (idempotent; only bump the counter on a real insert)
                query = """INSERT OR IGNORE INTO enrollment (student_id, course_id) VALUES (:student_id, :course_id);"""
                cursor = db.execute(query, {"student_id": student_id, "course_id": course_id})
                inserted = cursor.rowcount
                cursor.close()

                if inserted:
                    query = """UPDATE course SET num_enrolled = num_enrolled + 1 WHERE course_id = :course_id;"""
                    cursor = db.execute(query, {"course_id": course_id})
                    cursor.close()

                db.commit()
                promoted_students.append(student_id)
            except sqlite3.Error as e:
                db.rollback()
                current_app.logger.error(f"Database error: {e}")
                raise sqlite3.Error("Error: could not enroll in course from waitlist")
            finally:
                if cursor is not None:
                    cursor.close()

    return promoted_students


def promote_waitlist():    
    promoted_students = enroll_from_waitlist()
    for student in set(promoted_students):
        try:
            courses = schedule_methods.get_courses_from_list(student, "enrollment")
            utility.add_new_schedule(student, courses)
        except sqlite3.Error as e:
            current_app.logger.error(f"Database error: {e}")