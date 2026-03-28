from flask import current_app
from datetime import datetime
import math


def get_short_courses(course_codes):
    if len(course_codes) == 0:
        return []

    query = """SELECT course.department_id, course.course_number, course.course_name, course.days, course.start_time, course.end_time, instructor.first_name, instructor.last_name, course.is_online, course.building_code, course.room FROM course_instructor JOIN course ON course_instructor.course_id = course.course_id JOIN instructor ON course_instructor.instructor_id = instructor.instructor_id WHERE """

    for i in range(len(course_codes)):
        if i == 0:
            query += """course.course_code = """ + str(course_codes[i])
        else:
            query += """ OR course.course_code = """ + str(course_codes[i])
    
    query += """;"""

    cursor = current_app.db.execute(query)
    raw_courses = cursor.fetchall()
    courses = []

    # (department_id, number, name, days, start_time, end_time, teach_first, teach_last, is_online, building_code, room)
    for raw_course in raw_courses:
        # print(raw_course)
        course = []

        # Abbreviation
        cursor = current_app.db.execute("SELECT abbreviation FROM department WHERE department_id = :department_id;", {"department_id": raw_course[0]})
        department = cursor.fetchone()[0]
        course.append(department + " " + raw_course[1])    # department + course_number

        course.append(raw_course[2])    # name/title
        course.append(raw_course[3])    # days

        # Times
        if raw_course[4] is None or raw_course[5] is None:
            course.append(None)
        else:
            start_dt = datetime.fromisoformat(raw_course[4].replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(raw_course[5].replace("Z", "+00:00"))
            start_time = start_dt.strftime("%#I:%M %p")  # use %#I on Windows
            end_time = end_dt.strftime("%#I:%M %p")
            course.append(start_time + " - " + end_time)

        course.append(raw_course[7] + ", " + raw_course[6][0] + ".")    # last_name, first_init

        if (raw_course[8] == 1):
            course.append("Online")
        else:
            course.append(raw_course[9] + " " + raw_course[10])    # building_code room
        
        courses.append(course)
    
    cursor.close()
    return courses


def get_short_courses_final(course_codes):
    if len(course_codes) == 0:
        return []
    
    query = """SELECT course.course_code, course.course_name, course.department_id, course.course_number, course.type, instructor.first_name, instructor.last_name, course.final_id, course.is_online, course.building_code, course.room, course.cancelled, course.num_enrolled, course.capacity, course.waitlist FROM course_instructor JOIN course ON course_instructor.course_id = course.course_id JOIN instructor ON course_instructor.instructor_id = instructor.instructor_id WHERE """

    for i in range(len(course_codes)):
        if i == 0:
            query += """course.course_code = """ + str(course_codes[i])
        else:
            query += """ OR course.course_code = """ + str(course_codes[i])
    
    query += """;"""

    cursor = current_app.db.execute(query)
    raw_courses = cursor.fetchall()
    courses = []

    for raw_course in raw_courses:
        course = []

        course.append(raw_course[0])    # course_code
        course.append(raw_course[1])    # course_name

        # Abbreviation
        cursor = current_app.db.execute("SELECT abbreviation FROM department WHERE department_id = :department_id;", {"department_id": raw_course[2]})
        department = cursor.fetchone()[0]
        course.append(department + " " + raw_course[3])    # department + course_number

        course.append(raw_course[4])    # type
        course.append(raw_course[6] + ", " + raw_course[5][0] + ".")    # last_name, first_init

        # Final Data
        cursor = current_app.db.execute("SELECT start_datetime, end_datetime FROM final WHERE final_id = :final_id;", {"final_id": raw_course[7]})
        raw_final = cursor.fetchone()

        if (raw_final[0] == "No Final") or (raw_final[1] == "No Final"):
            course += [None, None, None]
        else:
            raw_start = datetime.fromisoformat(raw_final[0])
            raw_end = datetime.fromisoformat(raw_final[1])
            final_day = raw_start.strftime("%a")
            final_start = raw_start.strftime("%#I:%M %p")
            final_end = raw_end.strftime("%#I:%M %p")
            course += (final_day, final_start, final_end)
        
        if (raw_course[8] == 1):
            course.append("Online")
        else:
            course.append(raw_course[9] + " " + raw_course[10])    # building_code room

        # Status
        if raw_course[11] == 1:
            course.append("CANCELLED")
        elif raw_course[12] < raw_course[13]:      # num_enrolled < capacity?
            course.append("Open")
        elif raw_course[14] >= 0:                # waitlist >= 0?
            course.append("Waitlist")
        elif raw_course[12] > raw_course[13]:    # num_enrolled > capacity
            course.append("OVER")
        else:
            course.append("FULL")

        courses.append(course)
    
    cursor.close()
    return courses


def create_calendar(courses):
    calendar = [["", "Mon", "Tue", "Wed", "Thu", "Fri"]]
    times = [
        "7 AM",
        "8 AM",
        "9 AM",
        "10 AM",
        "11 AM",
        "12 PM",
        "1 PM",
        "2 PM",
        "3 PM",
        "4 PM",
        "5 PM",
        "6 PM",
        "7 PM",
        "8 PM",
        "9 PM",
        "10 PM"
    ]

    for time in times:
        calendar.append([time] + ([None] * 5))
    
    # 6 across, 17 down

    for course in courses:
        add_course_to_calendar(course, calendar)

    return calendar


def add_course_to_calendar(course, calendar):
    days = course[2]
    time_str = course[3]

    if not days or not time_str:
        return

    start_time, end_time = time_str.split(" - ")
    start_hour = datetime.strptime(start_time, "%I:%M %p").hour
    start_minute = datetime.strptime(start_time, "%I:%M %p").minute / 60
    end_hour = datetime.strptime(end_time, "%I:%M %p").hour
    end_minute = datetime.strptime(end_time, "%I:%M %p").minute / 60
    time_diff = (end_hour + end_minute) - (start_hour + start_minute)

    rowspan = math.ceil(round(start_minute + time_diff, 2))
    top_pct = round((start_minute / rowspan) * 100, 2)
    height_pct = round((time_diff / rowspan) * 100, 2)

    abbreviation = course[0]
    slot_data = (abbreviation, rowspan, top_pct, height_pct)
    
    start_slot = -1
    for i in range(1, len(calendar)):
        if datetime.strptime(calendar[i][0], "%I %p").hour == start_hour:
            start_slot = i
            break
    
    if start_slot < 0:
        return
    
    col_map = []
    if 'M'  in days: col_map.append(1)
    if 'Tu' in days: col_map.append(2)
    if 'W'  in days: col_map.append(3)
    if 'Th' in days: col_map.append(4)
    if 'F'  in days: col_map.append(5)

    for col in col_map:
        calendar[start_slot][col] = slot_data
        for r in range(1, rowspan):
            if start_slot + r < len(calendar):
                calendar[start_slot + r][col] = "SKIP"


def create_final_calendar(courses):
    calendar = [["", "Mon", "Tue", "Wed", "Thu", "Fri"]]
    times = [
        "7 AM",
        "8 AM",
        "9 AM",
        "10 AM",
        "11 AM",
        "12 PM",
        "1 PM",
        "2 PM",
        "3 PM",
        "4 PM",
        "5 PM",
        "6 PM",
        "7 PM",
        "8 PM",
        "9 PM",
        "10 PM"
    ]

    for time in times:
        calendar.append([time] + ([None] * 5))
    
    # 6 across, 17 down

    for course in courses:
        add_final_to_calendar(course, calendar)
    
    return calendar


def add_final_to_calendar(course, calendar):
    day = course[-5]
    start = course[-4]
    end = course[-3]

    if not(day) or not(start) or not(end):
        return
    
    start_hour = datetime.strptime(start, "%I:%M %p").hour
    start_minute = datetime.strptime(start, "%I:%M %p").minute / 60
    abbreviation = course[2]
    slot_data = (abbreviation, start_minute)

    if day == "Mon":
        for i in range(1, len(calendar)):
            calendar_hour = datetime.strptime(calendar[i][0], "%I %p").hour

            if start_hour == calendar_hour:
                calendar[i][1] = slot_data
    elif day == "Tue":
        for i in range(1, len(calendar)):
            calendar_hour = datetime.strptime(calendar[i][0], "%I %p").hour

            if start_hour == calendar_hour:
                calendar[i][2] = slot_data
    elif day == "Wed":
        for i in range(1, len(calendar)):
            calendar_hour = datetime.strptime(calendar[i][0], "%I %p").hour

            if start_hour == calendar_hour:
                calendar[i][3] = slot_data
    elif day == "Thu":
        for i in range(1, len(calendar)):
            calendar_hour = datetime.strptime(calendar[i][0], "%I %p").hour

            if start_hour == calendar_hour:
                calendar[i][4] = slot_data
    elif day == "Fri":
        for i in range(1, len(calendar)):
            calendar_hour = datetime.strptime(calendar[i][0], "%I %p").hour

            if start_hour == calendar_hour:
                calendar[i][5] = slot_data


def get_registered_courses(user_id):
    query = """SELECT course.course_code FROM enrollment JOIN course ON enrollment.course_id = course.course_id WHERE enrollment.student_id = :student_id;"""
    cursor = current_app.db.execute(query, {"student_id": user_id})
    codes_tup = cursor.fetchall()
    cursor.close()

    course_codes = []
    for code in codes_tup:
        course_codes.append(code[0])

    return course_codes


def get_waitlist(user_id):
    query = """SELECT course.course_code FROM student_waitlist JOIN course ON student_waitlist.course_id = course.course_id WHERE student_waitlist.student_id = :student_id;"""
    cursor = current_app.db.execute(query, {"student_id": user_id})
    codes_tup = cursor.fetchall()
    cursor.close()

    course_codes = []
    for code in codes_tup:
        course_codes.append(code[0])

    return course_codes