import sqlite3
from flask import current_app


def get_course_description(course_id):
    query = """SELECT department_id, course_number, type FROM course WHERE course_id = :course_id;"""
    try:
        cursor = current_app.db.execute(query, {"course_id": course_id})
        dept_info = cursor.fetchone()

        query = """SELECT abbreviation FROM department WHERE department_id = :department_id;"""
        cursor = current_app.db.execute(query, {"department_id": dept_info[0]})
        course_desc = cursor.fetchone()[0] + " " + dept_info[1] + " (" + dept_info[2] + ")"
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        return "Error: Could not register for courses"
    finally:
        cursor.close()

    return course_desc


def register_courses(user_id, course_codes):
    if len(course_codes) == 0:
        return {}
    
    placeholders = ", ".join([f":code_{i}" for i in range(len(course_codes))])
    query = f"SELECT course_id FROM course WHERE course_code IN ({placeholders})"
    values = {f"code_{i}": code for i, code in enumerate(course_codes)}

    try:
        cursor = current_app.db.execute(query, values)
        course_ids = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        return "Error: Could not register for courses"
    finally:
        cursor.close()
    unreged_courses = {}

    for course_id in course_ids:
        prereqs_check = check_prereqs(user_id, course_id[0])
        coreqs_check = check_coreqs(user_id, course_id[0])
        if type(prereqs_check) == str or type(coreqs_check) == str:
            return "Error: Could not register for courses"

        if len(prereqs_check) > 0:
            course_desc = get_course_description(course_id[0])
            if course_desc.startswith("Error"):
                return "Error: Could not register for courses"
            prereqs = "Following prerequisites not satisfied: " + ", ".join(prereqs_check)
            unreged_courses[course_desc] = prereqs
        elif len(coreqs_check) > 0:
            course_desc = get_course_description(course_id[0])
            if course_desc.startswith("Error"):
                return "Error: Could not register for courses"
            coreqs = "Following corequisites not satisfied: " + ", ".join(coreqs_check)
            unreged_courses[course_desc] = coreqs
        else:
            try:
                query = """INSERT INTO enrollment (student_id, course_id) VALUES (:student_id, :course_id);"""
                cursor = current_app.db.execute(query, {"student_id": user_id, "course_id": course_id[0]})

                query = """UPDATE course SET num_enrolled = num_enrolled + 1 WHERE course_id = :course_id;"""
                cursor = current_app.db.execute(query, {"course_id": course_id[0]})

                current_app.db.commit()
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error: {e}")
                return "Error: Could not register for courses"
            finally:
                cursor.close()
    
    if len(unreged_courses) == 0:
        unreged_courses["Success"] = "Success"

    return unreged_courses


def check_coreqs(course_id, all_ids):
    try:
        query = """SELECT coreq_id FROM corequisite WHERE course_id = :course_id;"""
        cursor = current_app.db.execute(query, {"course_id": course_id})
        coreqs = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        return "Error: Could not register for courses"
    finally:
        cursor.close()

    if len(coreqs) == 0:
        return []

    unfilled_coreqs = []    
    for coreq in coreqs:
        if coreq not in all_ids:
            course_desc = get_course_description(coreq[0])
            if course_desc.startswith("Error"):
                return "Error: Could not register for courses"
            unfilled_coreqs.append(course_desc)
    
    return unfilled_coreqs


def check_prereqs(user_id, course_id):
    try:
        query = """SELECT prereq_id FROM prerequisite WHERE course_id = :course_id;"""
        cursor = current_app.db.execute(query, {"course_id": course_id})
        prereqs = cursor.fetchall()
        
        if len(prereqs) == 0:
            return []
        
        unfilled_prereqs = []
        query = """SELECT course_id FROM prev_enrollment WHERE student_id = :student_id;"""
        cursor = current_app.db.execute(query, {"student_id": user_id})
        prev_courses = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        return "Error: Could not register for courses"
    finally:
        cursor.close()

    for prereq in prereqs:
        if prereq not in prev_courses:
            course_desc = get_course_description(prereq[0])
            if course_desc.startswith("Error"):
                return "Error: Could not register for courses"
            unfilled_prereqs.append(course_desc)
    
    return unfilled_prereqs


def drop_course(user_id, course_code):
    try:
        query = """SELECT course_id FROM course WHERE course_code = :course_code;"""
        cursor = current_app.db.execute(query, {"course_code": course_code})
        course_id = cursor.fetchone()[0]
        
        query = """DELETE FROM enrollment WHERE student_id = :student_id AND course_id = :course_id;"""
        cursor = current_app.db.execute(query, {"student_id": user_id, "course_id": course_id})

        query = """UPDATE course SET num_enrolled = num_enrolled - 1 WHERE course_id = :course_id;"""
        cursor = current_app.db.execute(query, {"course_id": course_id})

        current_app.db.commit()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        return "Error: Could not drop course"
    finally:
        cursor.close()


def waitlist_course(user_id, course_code):
    try:
        query = """UPDATE course SET waitlist = waitlist + 1 WHERE course_code = :course_code;"""
        cursor = current_app.db.execute(query, {"course_code": course_code})

        query = """SELECT course_id FROM course WHERE course_code = :course_code;"""
        cursor = current_app.db.execute(query, {"course_code": course_code})
        course_id = cursor.fetchone()[0]

        query = """SELECT MAX(position) FROM student_waitlist WHERE course_id = :course_id"""
        cursor = current_app.db.execute(query, {"course_id": course_id})
        last_pos = cursor.fetchone()[0]

        query = """INSERT INTO student_waitlist (student_id, course_id, position) VALUES (:student_id, :course_id, :position);"""
        if last_pos != None:
            cursor = current_app.db.execute(query, {"student_id": user_id, "course_id": course_id, "position": last_pos + 1})
        else:
            cursor = current_app.db.execute(query, {"student_id": user_id, "course_id": course_id, "position": 1})

        current_app.db.commit()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        return "Error: Could not waitlist course"
    finally:
        cursor.close()


def drop_waitlist(user_id, course_code):
    try:
        query = """UPDATE course SET waitlist = waitlist - 1 WHERE course_code = :course_code;"""
        cursor = current_app.db.execute(query, {"course_code": course_code})

        query = """SELECT course_id FROM course WHERE course_code = :course_code;"""
        cursor = current_app.db.execute(query, {"course_code": course_code})
        course_id = cursor.fetchone()[0]

        query = """SELECT position FROM student_waitlist WHERE student_id = :student_id AND course_id = :course_id;"""
        cursor = current_app.db.execute(query, {"student_id": user_id, "course_id": course_id})
        old_pos = cursor.fetchone()[0]

        query = """DELETE FROM student_waitlist WHERE student_id = :student_id AND course_id = :course_id;"""
        cursor = current_app.db.execute(query, {"student_id": user_id, "course_id": course_id})

        query = """UPDATE student_waitlist SET position = position - 1 WHERE course_id = :course_id AND position > :position;"""
        cursor = current_app.db.execute(query, {"course_id": course_id, "position": old_pos})

        current_app.db.commit()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        return "Error: Could not drop course from waitlist"
    finally:
        cursor.close()


def enroll_from_waitlist():
    try:
        query = """SELECT course_id, num_enrolled, capacity FROM course;"""
        cursor = current_app.db.execute(query)
        courses = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        return "Error: could not enroll in course from waitlist"
    finally:
        cursor.close()

    for course in courses:
        if course[1] < course[2]:
            course_id = course[0]

            # Check if students in waitlist
            try:
                query = """SELECT student_id FROM student_waitlist WHERE course_id = :course_id AND position = 1;"""
                cursor = current_app.db.execute(query, {"course_id": course_id})
                student_id = cursor.fetchone()
            except sqlite3.Error as e:
                current_app.logger.error(f"Database error: {e}")
                return "Error: could not enroll in course from waitlist"
            finally:
                cursor.close()

            if student_id:
                student_id = student_id[0]

                try:
                    # Drop from waitlist
                    query = """UPDATE course SET waitlist = waitlist - 1 WHERE course_id = :course_id;"""
                    cursor = current_app.db.execute(query, {"course_id": course_id})

                    query = """DELETE FROM student_waitlist WHERE student_id = :student_id AND course_id = :course_id;"""
                    cursor = current_app.db.execute(query, {"student_id": student_id, "course_id": course_id})

                    query = """UPDATE student_waitlist SET position = position - 1 WHERE course_id = :course_id;"""
                    cursor = current_app.db.execute(query, {"course_id": course_id})

                    # Add to enrollment
                    query = """UPDATE course SET num_enrolled = num_enrolled + 1 WHERE course_id = :course_id;"""
                    cursor = current_app.db.execute(query, {"course_id": course_id})

                    query = """INSERT INTO enrollment (student_id, course_id) VALUES (:student_id, :course_id);"""
                    cursor = current_app.db.execute(query, {"student_id": student_id, "course_id": course_id})

                    current_app.db.commit()
                except sqlite3.Error as e:
                    current_app.logger.error(f"Database error: {e}")
                    return "Error: could not enroll in course from waitlist"
                finally:
                    cursor.close()