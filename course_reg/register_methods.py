import sqlite3
from flask import current_app
from course_reg.db import get_db
import course_reg.schedule_methods as schedule_methods
import course_reg.logic as logic
import course_reg.analytics as analytics


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

        if len(prereqs_check) > 0:
            course_desc = get_course_description(course_id)
            prereqs = "Following prerequisites not satisfied: " + ", ".join(prereqs_check)
            unreged_courses[course_desc] = prereqs
        elif len(coreqs_check) > 0:
            course_desc = get_course_description(course_id)
            coreqs = "Following corequisites not satisfied: " + ", ".join(coreqs_check)
            unreged_courses[course_desc] = coreqs
        else:
            try:
                db = get_db()
                # INSERT OR IGNORE makes re-registration idempotent: the UNIQUE
                # index on (student_id, course_id) drops a duplicate, and we only
                # bump num_enrolled when a row was actually inserted.
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


# def get_students():
#     cursor = None
#     try:
#         db = get_db()
#         query = """SELECT student_id FROM student;"""
#         cursor = db.execute(query)
#         ids_raw = cursor.fetchall()

#         ids = []
#         for raw_id in ids_raw:
#             ids.append(raw_id[0])
        
#         return ids
#     except sqlite3.Error as e:
#         current_app.logger.error(f"Database error: {e}")
#         raise sqlite3.Error("Error: Could not get student IDs")
#     finally:
#         if cursor is not None:
#             cursor.close()


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
            workload = logic.total_hours_per_week(courses)
            burnout_data = logic.calculate_burnout_risk(courses)
            burnout = burnout_data[0]
            burnout_explanation = logic.generate_burnout_explanation(burnout_data[1])
            impact = logic.calculate_academic_impact(courses, student)
            impact_explanation = logic.generate_impact_explanation(logic.classify_academic_impact(impact))
            recommendation = logic.generate_recommendation(workload, burnout, impact)
            analytics.save_metrics(student, workload, burnout, burnout_explanation, impact, impact_explanation, recommendation)
        except sqlite3.Error as e:
            current_app.logger.error(f"Database error: {e}")