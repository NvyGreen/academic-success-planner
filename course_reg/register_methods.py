import sqlite3
from flask import current_app
from course_reg.db import get_db


def get_course_description(course_id):
    query = """SELECT department_id, course_number, type FROM course WHERE course_id = :course_id;"""
    cursor = None
    try:
        db = get_db()
        cursor = db.execute(query, {"course_id": course_id})
        dept_info = cursor.fetchone()
        cursor.close()
        if dept_info is None:
            sqlite3.Error("Error: Could not register for courses")

        query = """SELECT abbreviation FROM department WHERE department_id = :department_id;"""
        cursor = db.execute(query, {"department_id": dept_info["department_id"]})
        abbreviation = cursor.fetchone()
        if abbreviation is None:
            sqlite3.Error("Error: Could not register for courses")
        abbreviation = abbreviation["abbreviation"]
        course_desc = abbreviation + " " + dept_info["course_number"] + " (" + dept_info["type"] + ")"
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not register for courses")
    finally:
        if cursor is not None:
            cursor.close()

    return course_desc


def register_courses(user_id, course_codes):
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
                query = """INSERT INTO enrollment (student_id, course_id) VALUES (:student_id, :course_id);"""
                cursor = db.execute(query, {"student_id": user_id, "course_id": course_id})
                cursor.close()

                query = """UPDATE course SET num_enrolled = num_enrolled + 1 WHERE course_id = :course_id;"""
                cursor = db.execute(query, {"course_id": course_id})

                db.commit()
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error: {e}")
                raise sqlite3.Error("Error: Could not register for courses")
            finally:
                db.rollback()
                cursor.close()
    
    if len(unreged_courses) == 0:
        return "Success"

    return unreged_courses


def check_coreqs(course_id, all_ids):
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


def check_prereqs(user_id, course_id):
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


def drop_course(user_id, course_code):
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
        cursor.close()

        query = """UPDATE course SET num_enrolled = num_enrolled - 1 WHERE course_id = :course_id;"""
        cursor = db.execute(query, {"course_id": course_id})

        db.commit()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not drop course")
    finally:
        db.rollback()
        if cursor is not None:
            cursor.close()


def waitlist_course(user_id, course_code):
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

        query = """SELECT MAX(position) FROM student_waitlist WHERE course_id = :course_id"""
        cursor = db.execute(query, {"course_id": course_id})
        last_pos = cursor.fetchone()
        if last_pos is None:
            raise sqlite3.Error("Error: Could not waitlist course")
        last_pos = last_pos[0]
        cursor.close()

        query = """INSERT INTO student_waitlist (student_id, course_id, position) VALUES (:student_id, :course_id, :position);"""
        if last_pos != None:
            cursor = db.execute(query, {"student_id": user_id, "course_id": course_id, "position": last_pos + 1})
        else:
            cursor = db.execute(query, {"student_id": user_id, "course_id": course_id, "position": 1})
        
        query = """UPDATE course SET waitlist = waitlist + 1 WHERE course_code = :course_code;"""
        cursor = db.execute(query, {"course_code": course_code})
        cursor.close()

        db.commit()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not waitlist course")
    finally:
        db.rollback()
        if cursor is not None:
            cursor.close()


def drop_waitlist(user_id, course_code):
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
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not drop course from waitlist")
    finally:
        db.rollback()
        if cursor is not None:
            cursor.close()


def enroll_from_waitlist():
    cursor = None
    try:
        db = get_db()
        query = """SELECT course_id FROM course WHERE num_enrolled < capacity;"""
        cursor = db.execute(query)
        courses = cursor.fetchall()
        if not courses:
            raise sqlite3.Error("Error: could not enroll in course from waitlist")
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: could not enroll in course from waitlist")
    finally:
        if cursor is not None:
            cursor.close()

    for course in courses:
        course_id = course["course_id"]

        # Check if students in waitlist
        try:
            db = get_db()
            query = """SELECT student_id FROM student_waitlist WHERE course_id = :course_id AND position = 1;"""
            cursor = db.execute(query, {"course_id": course_id})
            student_id = cursor.fetchone()
        except sqlite3.Error as e:
            current_app.logger.error(f"Database error: {e}")
            raise sqlite3.Error("Error: could not enroll in course from waitlist")
        finally:
            cursor.close()

        if student_id:
            student_id = student_id["student_id"]

            try:
                # Drop from waitlist
                db = get_db()

                query = """DELETE FROM student_waitlist WHERE student_id = :student_id AND course_id = :course_id;"""
                cursor = db.execute(query, {"student_id": student_id, "course_id": course_id})
                cursor.close()

                query = """UPDATE course SET waitlist = waitlist - 1 WHERE course_id = :course_id;"""
                cursor = db.execute(query, {"course_id": course_id})
                cursor.close()

                query = """UPDATE student_waitlist SET position = position - 1 WHERE course_id = :course_id;"""
                cursor = db.execute(query, {"course_id": course_id})
                cursor.close()

                # Add to enrollment
                query = """INSERT INTO enrollment (student_id, course_id) VALUES (:student_id, :course_id);"""
                cursor = db.execute(query, {"student_id": student_id, "course_id": course_id})

                query = """UPDATE course SET num_enrolled = num_enrolled + 1 WHERE course_id = :course_id;"""
                cursor = db.execute(query, {"course_id": course_id})
                cursor.close()

                db.commit()
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error: {e}")
                raise sqlite3.Error("Error: could not enroll in course from waitlist")
            finally:
                db.rollback()
                cursor.close()