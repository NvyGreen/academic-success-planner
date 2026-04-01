from flask import current_app
from datetime import datetime



def get_enrollment_window(user_id):
    query = """SELECT enrollment_start, enrollment_end FROM student WHERE student_id = :student_id;"""
    cursor = current_app.db.execute(query, {"student_id": user_id})
    raw_start, raw_end = cursor.fetchone()
    start = datetime.fromisoformat(raw_start)
    end = datetime.fromisoformat(raw_end)
    cursor.close()

    return (start, end)


def register_courses(user_id, course_codes):
    if len(course_codes) == 0:
        return []
    
    query = """SELECT course_id FROM course WHERE """

    for i in range(len(course_codes)):
        if i == 0:
            query += """course.course_code = """ + str(course_codes[i])
        else:
            query += """ OR course.course_code = """ + str(course_codes[i])
    
    query += """;"""

    cursor = current_app.db.execute(query)
    course_ids = cursor.fetchall()
    unreged_courses = []

    for course_id in course_ids:
        if check_prereqs(user_id, course_id[0]) and check_coreqs(course_id[0], course_ids):
            query = """INSERT INTO enrollment (student_id, course_id) VALUES (:student_id, :course_id);"""
            cursor = current_app.db.execute(query, {"student_id": user_id, "course_id": course_id[0]})

            query = """UPDATE course SET num_enrolled = num_enrolled + 1 WHERE course_id = :course_id;"""
            cursor = current_app.db.execute(query, {"course_id": course_id[0]})

            current_app.db.commit()
        else:
            query = """SELECT department_id, course_number FROM course WHERE course_id = :course_id;"""
            cursor = current_app.db.execute(query, {"course_id": course_id[0]})
            dept_info = cursor.fetchone()

            query = """SELECT abbreviation FROM department WHERE department_id = :department_id;"""
            cursor = current_app.db.execute(query, {"department_id": dept_info[0]})
            unreged_courses.append(cursor.fetchone()[0] + " " + dept_info[1])

            # query = """SELECT course_code FROM course WHERE course_id = :course_id;"""
            # cursor = current_app.db.execute(query, {"course_id": course_id[0]})
            # unreged_courses.append(cursor.fetchone()[0])
    
    cursor.close()
    return unreged_courses


def check_coreqs(course_id, all_ids):
    query = """SELECT coreq_id FROM corequisite WHERE course_id = :course_id;"""
    cursor = current_app.db.execute(query, {"course_id": course_id})
    coreqs = cursor.fetchall()
    cursor.close()

    if len(coreqs) == 0:
        return True
    
    for coreq in coreqs:
        if (coreq not in all_ids):
            return False
    
    return True


def check_prereqs(user_id, course_id):
    query = """SELECT prereq_id FROM prerequisite WHERE course_id = :course_id;"""
    cursor = current_app.db.execute(query, {"course_id": course_id})
    prereqs = cursor.fetchall()
    
    if len(prereqs) == 0:
        cursor.close()
        return True
    
    query = """SELECT course_id FROM prev_enrollment WHERE student_id = :student_id;"""
    cursor = current_app.db.execute(query, {"student_id": user_id})
    prev_courses = cursor.fetchall()
    cursor.close()

    for prereq in prereqs:
        if (prereq not in prev_courses):
            return False
    
    return True


def drop_course(user_id, course_code):
    query = """SELECT course_id FROM course WHERE course_code = :course_code;"""
    cursor = current_app.db.execute(query, {"course_code": course_code})
    course_id = cursor.fetchone()[0]
    
    query = """DELETE FROM enrollment WHERE student_id = :student_id AND course_id = :course_id;"""
    cursor = current_app.db.execute(query, {"student_id": user_id, "course_id": course_id})

    query = """UPDATE course SET num_enrolled = num_enrolled - 1 WHERE course_id = :course_id;"""
    cursor = current_app.db.execute(query, {"course_id": course_id})

    current_app.db.commit()
    cursor.close()


def waitlist_course(user_id, course_code):
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
    cursor.close()


def drop_waitlist(user_id, course_code):
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
    cursor.close()


def enroll_from_waitlist():
    query = """SELECT course_id, num_enrolled, capacity FROM course;"""
    cursor = current_app.db.execute(query)
    courses = cursor.fetchall()

    for course in courses:
        if course[1] < course[2]:
            course_id = course[0]

            # Check if students in waitlist
            query = """SELECT student_id FROM student_waitlist WHERE course_id = :course_id AND position = 1;"""
            cursor = current_app.db.execute(query, {"course_id": course_id})
            student_id = cursor.fetchone()

            if student_id:
                student_id = student_id[0]

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

    cursor.close()