from flask import current_app
from datetime import datetime



def prep_ge():
    cursor = current_app.db.execute("SELECT * FROM ge_category;")
    # (category_id, label, name)
    ge_categories = cursor.fetchall()
    cursor.close()

    ge_dropdown = []
    for category in ge_categories:
        if category[0] == 1:
            ge_dropdown.append((category[0], " "))
        else:
            ge_dropdown.append((category[0], "GE " + category[1] + ": " + category[2]))
    
    return ge_dropdown


def prep_departments():
    cursor = current_app.db.execute("SELECT * FROM department;")
    # (department_id, abbreviation, name)
    dep_list = cursor.fetchall()
    cursor.close()

    dep_dropdown = [("0", " ")]
    for department in dep_list:
        dep_dropdown.append((department[0], department[1] + ": " + department[2]))
    
    return dep_dropdown


def get_courses(filters, temp_courses, reg_courses, waitlist):
    query = """SELECT course.department_id, course.course_number, course.course_name, course.type, course.days, course.start_time, course.end_time, course.final_id, instructor.first_name, instructor.last_name, course.is_online, course.building_code, course.room, course.credits, course.num_enrolled, course.capacity, course.waitlist, course.cancelled, course.course_code FROM course_instructor JOIN course ON course_instructor.course_id = course.course_id JOIN instructor ON course_instructor.instructor_id = instructor.instructor_id WHERE """
    modifier = "course."
    
    values = dict()
    add_condition = """ AND """
    first_condition = True

    # General Education Category
    if filters.ge_cat - 1:
        first_condition = False
        query += modifier + """category_id = :ge_category"""
        values["ge_category"] = filters.ge_cat
    
    # Department
    if filters.department:
        if first_condition:
            first_condition = False
        else:
            query += add_condition

        query += modifier + """department_id = :department"""
        values["department"] = filters.department
    
    # Course Number
    if filters.course_num:
        if first_condition:
            first_condition = False
        else:
            query += add_condition

        query += modifier + """course_number = :course_number"""
        values["course_number"] = filters.course_num
    
    # Course Code
    if filters.course_code != None:
        if first_condition:
            first_condition = False
        else:
            query += add_condition

        query += modifier + """course_code = :course_code"""
        values["course_code"] = filters.course_code
    
    # Course Level
    if filters.course_level != "all":
        if first_condition:
            first_condition = False
        else:
            query += add_condition

        query += modifier + """course_level = :course_level"""
        values["course_level"] = filters.course_level
    
    # Instructor
    if filters.instructor:
        if first_condition:
            first_condition = False
        else:
            query += add_condition
        
        query += """instructor.last_name = :instructor"""
        values["instructor"] = filters.instructor
    
    query += add_condition + modifier + """cancelled = 0;"""

    cursor = current_app.db.execute(query, values)
    courses_raw = cursor.fetchall()
    cursor.close()

    courses = []
    for raw_course in courses_raw:
        added = (raw_course[len(raw_course) - 1] in temp_courses) or (raw_course[len(raw_course) - 1] in reg_courses)
        waitlisted = raw_course[len(raw_course) - 1] in waitlist
        courses.append(clean_course(raw_course, added, waitlisted))
    return courses


def get_courses_adv(filters, temp_courses, reg_courses, waitlist):
    query = """SELECT course.department_id, course.course_number, course.course_name, course.type, course.days, course.start_time, course.end_time, course.final_id, instructor.first_name, instructor.last_name, course.is_online, course.building_code, course.room, course.credits, course.num_enrolled, course.capacity, course.waitlist, course.cancelled, course.course_code FROM course_instructor JOIN course ON course_instructor.course_id = course.course_id JOIN instructor ON course_instructor.instructor_id = instructor.instructor_id WHERE """
    modifier = "course."
    
    values = dict()
    add_condition = """ AND """
    first_condition = True

    # General Education Category
    if filters.ge_cat - 1:
        first_condition = False
        query += modifier + """category_id = :ge_category"""
        values["ge_category"] = filters.ge_cat
    
    # Department
    if filters.department:
        if first_condition:
            first_condition = False
        else:
            query += add_condition

        query += modifier + """department_id = :department"""
        values["department"] = filters.department
    
    # Course Number
    if filters.course_num:
        if first_condition:
            first_condition = False
        else:
            query += add_condition

        query += modifier + """course_number = :course_number"""
        values["course_number"] = filters.course_num
    
    # Course Code
    if filters.course_code != None:
        if first_condition:
            first_condition = False
        else:
            query += add_condition

        query += modifier + """course_code = :course_code"""
        values["course_code"] = filters.course_code
    
    # Course Level
    if filters.course_level != "all":
        if first_condition:
            first_condition = False
        else:
            query += add_condition

        query += modifier + """course_level = :course_level"""
        values["course_level"] = filters.course_level
    
    # Instructor
    if filters.instructor:
        if first_condition:
            first_condition = False
        else:
            query += add_condition
        
        query += """instructor.last_name = :instructor"""
        values["instructor"] = filters.instructor
    
    # Modality
    if filters.modality != "nomode":
        if first_condition:
            first_condition = False
        else:
            query += add_condition
        
        if filters.modality == "inperson":
            query += modifier + """is_online = 0"""
        elif filters.modality == "online":
            query += modifier + """is_online = 1"""
    
    # Days
    if filters.days:        
        days_arr = filters.days.split(",")
        days_abbr = ["Su", "M", "Tu", "W", "Th", "F", "Sa"]
        for day in days_arr:
            if day in days_abbr:
                query += add_condition + modifier + f"""days LIKE '%{day}%'"""

    # Starts After
    if filters.starts_after != "nopref":
        start_time = datetime.strptime(filters.starts_after, "%H:%M").strftime("%H:%M:%S")
        query += add_condition + modifier + """TIME(start_time) >= :start_time"""
        values["start_time"] = start_time

    # Ends Before
    if filters.ends_before != "nopref":
        end_time = datetime.strptime(filters.ends_before, "%H:%M").strftime("%H:%M:%S")
        query += add_condition + modifier + """TIME(end_time) < :end_time"""
        values["end_time"] = end_time

    # Courses Full Option
    if filters.course_full_option != "nopref":
        if filters.course_full_option == "open_or_waitlist":
            query += add_condition + """(""" + modifier + """num_enrolled < """ + modifier + """capacity OR """
            query += modifier + """waitlist <> -1)"""
        elif filters.course_full_option == "open_only":
            query += add_condition + modifier + """num_enrolled < """ + modifier + """capacity"""
        elif filters.course_full_option == "full_only":
            query += add_condition + modifier + """num_enrolled >= """ + modifier + """capacity"""
        elif filters.course_full_option == "over_only":
            query += add_condition + modifier + """num_enrolled > """ + modifier + """capacity"""

    # Cancel Option
    if filters.cancel_option == "excl":
        query += add_condition + modifier + "cancelled = 0"
    elif filters.cancel_option == "only_cancel":
        query += add_condition + modifier + "cancelled = 1"

    # Building Code
    if filters.building_code:
        if first_condition:
            first_condition = False
        else:
            query += add_condition
        
        query += modifier + """building_code = :building_code"""
        values["building_code"] = filters.building_code

    # Room No
    if filters.room_no:
        if first_condition:
            first_condition = False
        else:
            query += add_condition
        
        query += modifier + """room = :room"""
        values["room"] = filters.room_no
    
    # Credits
    if filters.credits:
        if first_condition:
            first_condition = False
        else:
            query += add_condition
        
        query += modifier + """credits = :credits"""
        values["credits"] = filters.credits
    
    query += ";"

    cursor = current_app.db.execute(query, values)
    courses_raw = cursor.fetchall()
    cursor.close()

    courses = []
    for raw_course in courses_raw:
        added = (raw_course[len(raw_course) - 1] in temp_courses) or (raw_course[len(raw_course) - 1] in reg_courses)
        waitlisted = raw_course[len(raw_course) - 1] in waitlist
        courses.append(clean_course(raw_course, added, waitlisted))
    return courses


def get_courses_from_codes(course_codes):
    if len(course_codes) == 0:
        return []
    
    query = """SELECT course.department_id, course.course_number, course.course_name, course.type, course.days, course.start_time, course.end_time, course.final_id, instructor.first_name, instructor.last_name, course.is_online, course.building_code, course.room, course.credits, course.num_enrolled, course.capacity, course.waitlist, course.cancelled, course.course_code FROM course_instructor JOIN course ON course_instructor.course_id = course.course_id JOIN instructor ON course_instructor.instructor_id = instructor.instructor_id WHERE """

    for i in range(len(course_codes)):
        if i == 0:
            query += """course.course_code = """ + str(course_codes[i])
        else:
            query += """ OR course.course_code = """ + str(course_codes[i])
    
    query += """;"""

    cursor = current_app.db.execute(query)
    courses_raw = cursor.fetchall()
    cursor.close()

    courses = []
    for raw_course in courses_raw:
        courses.append(clean_course(raw_course, True, False))
    return courses


def get_user_waitlist(user_id, course_codes):
    if len(course_codes) == 0:
        return []
    
    query = """SELECT course.department_id, course.course_number, course.course_name, course.type, course.days, course.start_time, course.end_time, course.final_id, instructor.first_name, instructor.last_name, course.is_online, course.building_code, course.room, course.credits, course.num_enrolled, course.capacity, course.waitlist, course.cancelled, course.course_code FROM course_instructor JOIN course ON course_instructor.course_id = course.course_id JOIN instructor ON course_instructor.instructor_id = instructor.instructor_id WHERE """

    for i in range(len(course_codes)):
        if i == 0:
            query += """course.course_code = """ + str(course_codes[i])
        else:
            query += """ OR course.course_code = """ + str(course_codes[i])
    
    query += """;"""

    cursor = current_app.db.execute(query)
    courses_raw = cursor.fetchall()

    courses = []
    for raw_course in courses_raw:
        courses.append(clean_course(raw_course, False, True))
    
    for i in range(len(courses)):
        query = """SELECT course_id FROM course WHERE course_code = :course_code;"""
        cursor = current_app.db.execute(query, {"course_code": course_codes[i]})
        course_id = cursor.fetchone()[0]

        query = """SELECT position FROM student_waitlist WHERE student_id = :student_id AND course_id = :course_id;"""
        cursor = current_app.db.execute(query, {"student_id": user_id, "course_id": course_id})
        student_pos = cursor.fetchone()[0]

        courses[i].append(student_pos)

    cursor.close()
    return courses


def get_criteria(filters):
    criteria = []

    if filters.ge_cat - 1:
        cursor = current_app.db.execute("SELECT label, name FROM ge_category WHERE category_id = :category_id", {"category_id": filters.ge_cat})
        category = cursor.fetchone()
        cursor.close()
        criteria.append("General Education Category " + category[0] + ": " + category[1])
    
    if filters.department:
        cursor = current_app.db.execute("SELECT abbreviation FROM department WHERE department_id = :department_id", {"department_id": filters.department})
        dep = cursor.fetchone()
        cursor.close()
        criteria.append("Department: " + dep[0])
    
    if filters.course_num:
        criteria.append("Course Number Range: " + filters.course_num)
    
    if filters.course_code != None:
        criteria.append("Course Code: " + str(filters.course_code))
    
    if filters.course_level != "all":
        if filters.course_level == "lower":
            criteria.append("Course Level: Lower Division only")
        elif filters.course_level == "upper":
            criteria.append("Course Level: Upper Division only")
        elif filters.course_level == "gradprof":
            criteria.append("Course Level: Graduate/Professional only")
    
    if filters.instructor:
        criteria.append("Instructor: " + filters.instructor)
    
    criteria.append("Exclude cancelled courses")
    
    return criteria


def get_criteria_adv(filters):
    criteria = []

    if filters.ge_cat - 1:
        cursor = current_app.db.execute("SELECT label, name FROM ge_category WHERE category_id = :category_id", {"category_id": filters.ge_cat})
        category = cursor.fetchone()
        cursor.close()
        criteria.append("General Education Category " + category[0] + ": " + category[1])
    
    if filters.department:
        cursor = current_app.db.execute("SELECT abbreviation FROM department WHERE department_id = :department_id", {"department_id": filters.department})
        dep = cursor.fetchone()
        cursor.close()
        criteria.append("Department: " + dep[0])
    
    if filters.course_num:
        criteria.append("Course Number Range: " + filters.course_num)
    
    if filters.course_code != None:
        criteria.append("Course Code: " + str(filters.course_code))
    
    if filters.course_level != "all":
        if filters.course_level == "lower":
            criteria.append("Course Level: Lower Division only")
        elif filters.course_level == "upper":
            criteria.append("Course Level: Upper Division only")
        elif filters.course_level == "gradprof":
            criteria.append("Course Level: Graduate/Professional only")


    if filters.instructor:
        criteria.append("Instructor: " + filters.instructor)
    
    if filters.modality != "nomode":
        if filters.modality == "inperson":
            criteria.append("Modality: In-person")
        elif filters.modality == "online":
            criteria.append("Modality: Online")
    
    if filters.days:
        criteria.append("Meeting Days: " + filters.days)
    
    if filters.starts_after != "nopref":
        raw_start = datetime.strptime(filters.starts_after, "%H:%M")
        criteria.append("Course meets on or after: " + raw_start.strftime("%I:%M %p"))
    
    if filters.ends_before != "nopref":
        raw_end = datetime.strptime(filters.ends_before, "%H:%M")
        criteria.append("Course finishes by: " + raw_end.strftime("%I:%M %p"))
    
    if filters.course_full_option != "nopref":
        full_option = "Full Courses Option: "
        if filters.course_full_option == "open_or_waitlist":
            criteria.append(full_option + "Include waitlisted courses")
        elif filters.course_full_option == "open_only":
            criteria.append(full_option + "Don't show full courses")
        elif filters.course_full_option == "full_only":
            criteria.append(full_option + "Only full/waitlisted courses")
        elif filters.course_full_option == "over_only":
            criteria.append(full_option + "Only over-enrolled courses")
    
    if filters.building_code:
        if filters.room_no:
            criteria.append("Course meets at: " + filters.building_code + ", room " + filters.room_no)
        else:
            criteria.append("Course meets in building: " + filters.building_code)
    
    if filters.cancel_option == "excl":
        criteria.append("Exclude cancelled courses")
    elif filters.cancel_option == "incl":
        criteria.append("Include cancelled courses")
    elif filters.cancel_option == "only_cancel":
        criteria.append("Only show cancelled courses")
    
    if filters.credits != None:
        criteria.append("Number of credits: " + str(filters.credits))
    
    return criteria


def clean_course(raw_course, added: bool, waitlisted: bool):
    course = []

    # (department_id, course_number, course_name, type, days, start_time, end_time, final_id, first_name, last_name, is_online, building_code, room, credits, num_enrolled, capacity, waitlist, cancelled)

    # Add/Drop/Wait
    if added:
        course.append("Registered")
    elif waitlisted:
        course.append("Waitlisted")
    else:
        course.append("Neither")
    
    # Abbreviation
    cursor = current_app.db.execute("SELECT abbreviation FROM department WHERE department_id = :department_id;", {"department_id": raw_course[0]})
    department = cursor.fetchone()[0]
    course.append(department + " " + raw_course[1])    # department + course_number

    course.append(raw_course[2])    # course_name
    course.append(raw_course[3])    # type
    course.append(raw_course[4])    # days

    # Times
    if raw_course[5] is None or raw_course[6] is None:
        course.append(None)
    else:
        start_time_raw = str(datetime.fromisoformat(raw_course[5]).hour) + ":" + str(datetime.fromisoformat(raw_course[5]).minute)
        end_time_raw = str(datetime.fromisoformat(raw_course[6]).hour) + ":" + str(datetime.fromisoformat(raw_course[6]).minute)
        start_time = datetime.strptime(start_time_raw, "%H:%M").strftime("%I:%M %p")
        end_time = datetime.strptime(end_time_raw, "%H:%M").strftime("%I:%M %p")
        course.append(start_time + "-" + end_time)
    
    # Final
    cursor = current_app.db.execute("SELECT start_datetime, end_datetime FROM final WHERE final_id = :final_id;", {"final_id": raw_course[7]})
    final_data = cursor.fetchone()

    if (final_data[0] == "No Final"):
        course.append(None)
    else:
        final_start_raw = str(datetime.fromisoformat(final_data[0]).hour) + ":" + str(datetime.fromisoformat(final_data[0]).minute)
        final_end_raw = str(datetime.fromisoformat(final_data[1]).hour) + ":" + str(datetime.fromisoformat(final_data[1]).minute)

        final_date = datetime.fromisoformat(final_data[0]).strftime("%b") + " " + str(datetime.fromisoformat(final_data[0]).day)
        final_day = datetime.fromisoformat(final_data[0]).strftime("%a")
        final_start = datetime.strptime(final_start_raw, "%H:%M").strftime("%I:%M %p")
        final_end = datetime.strptime(final_end_raw, "%H:%M").strftime("%I:%M %p")

        course.append(final_day + ", " + final_date + ", " + final_start + "-" + final_end)

    # Instructor
    course.append(raw_course[8] + ", " + raw_course[9][0] + ".")    # instructor.first_name, instructor.first_initial.

    # Location
    if (raw_course[10] == 1):
            course.append("Online")
    else:
        course.append(raw_course[11] + " " + raw_course[12])    # building_code room
    
    course.append(raw_course[13])    # credits
    course.append(str(raw_course[14]) + " / " + str(raw_course[15]))    # num_enrolled / capacity

    # Status
    if raw_course[17] == 1:
        course.append("CANCELLED")
    elif raw_course[14] < raw_course[15]:      # num_enrolled < capacity?
        course.append("Open")
    elif raw_course[16] >= 0:                  # waitlist >= 0?
        course.append("Waitlist")
    elif raw_course[14] > raw_course[15]:      # num_enrolled > capacity
        course.append("OVER")
    else:
        course.append("FULL")
    
    course.append(raw_course[18])
    
    cursor.close()
    return course