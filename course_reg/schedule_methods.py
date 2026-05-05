from datetime import datetime
import math
from flask import current_app


def get_short_courses(course_codes):
    if len(course_codes) == 0:
        return []

    placeholders = ", ".join([f":code_{i}" for i in range(len(course_codes))])
    query = f"SELECT course.department_id, course.course_number, course.course_name, course.type, course.days, course.start_time, course.end_time, instructor.first_name, instructor.last_name, course.is_online, course.building_code, course.room, course.course_id FROM course_instructor JOIN course ON course_instructor.course_id = course.course_id JOIN instructor ON course_instructor.instructor_id = instructor.instructor_id WHERE course_code IN ({placeholders})"
    values = {f"code_{i}": code for i, code in enumerate(course_codes)}
    cursor = current_app.db.execute(query, values)
    raw_courses = cursor.fetchall()

    courses = []
    # (department_id, number, name, days, start_time, end_time, teach_first, teach_last, is_online, building_code, room)
    for raw_course in raw_courses:
        course = []

        # Abbreviation
        cursor = current_app.db.execute("SELECT abbreviation FROM department WHERE department_id = :department_id;", {"department_id": raw_course[0]})
        department = cursor.fetchone()[0]
        course.append(department + " " + raw_course[1])    # department + course_number

        course.append(raw_course[2])    # name/title
        course.append(raw_course[3])    # type
        course.append(raw_course[4])    # days

        # Times
        if raw_course[5] is None or raw_course[6] is None:
            course.append(None)
        else:
            start_dt = datetime.fromisoformat(raw_course[5].replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(raw_course[6].replace("Z", "+00:00"))
            start_time = start_dt.strftime("%#I:%M %p")  # use %#I on Windows
            end_time = end_dt.strftime("%#I:%M %p")
            course.append(start_time + " - " + end_time)

        course.append(raw_course[8] + ", " + raw_course[7][0] + ".")    # last_name, first_init

        if (raw_course[9] == 1):
            course.append("Online")
        else:
            course.append(raw_course[10] + " " + raw_course[11])    # building_code room
        
        course.append(raw_course[12])

        courses.append(course)
    
    cursor.close()
    return courses


def get_short_courses_final(course_codes):
    if len(course_codes) == 0:
        return []

    placeholders = ", ".join([f":code_{i}" for i in range(len(course_codes))])
    query = f"SELECT course.department_id, course.course_number, course.course_name, course.type, course.final_id, course.is_online, course.building_code, course.room FROM course JOIN final ON course.final_id = final.final_id WHERE course_code IN ({placeholders})"
    values = {f"code_{i}": code for i, code in enumerate(course_codes)}
    cursor = current_app.db.execute(query, values)
    raw_courses = cursor.fetchall()
    courses = []

    # (department_id, course_number, course_name, type, final_id, is_online, building_code, room)
    for raw_course in raw_courses:
        course = []

        # Abbreviation
        cursor = current_app.db.execute("SELECT abbreviation FROM department WHERE department_id = :department_id;", {"department_id": raw_course[0]})
        department = cursor.fetchone()[0]
        course.append(department + " " + raw_course[1])    # department + course_number

        course.append(raw_course[2])    # name/title
        course.append(raw_course[3])    # type

        # Final Data
        cursor = current_app.db.execute("SELECT start_datetime, end_datetime FROM final WHERE final_id = :final_id;", {"final_id": raw_course[4]})
        raw_final = cursor.fetchone()

        if (raw_final[0] == "No Final") or (raw_final[1] == "No Final"):
            course.append(None)
        else:
            raw_start = datetime.fromisoformat(raw_final[0])
            raw_end = datetime.fromisoformat(raw_final[1])
            final_day = raw_start.strftime("%a")
            final_start = raw_start.strftime("%#I:%M %p")
            final_end = raw_end.strftime("%#I:%M %p")
            course.append(final_day + ", " + final_start + " - " + final_end)
        
        if (raw_course[5] == 1):
            course.append("Online")
        else:
            course.append(raw_course[6] + " " + raw_course[7])    # building_code room

        courses.append(course)
    
    cursor.close()
    return courses


def create_calendar(courses, cal_type):
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

    if cal_type == "courses":
        for course in courses:
            add_course_to_calendar(course, calendar)
    elif cal_type == "final":
        for course in courses:
            add_final_to_calendar(course, calendar)
    
    return calendar


def add_course_to_calendar(course, calendar):
    days = course[3]
    time_str = course[4]

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


def add_final_to_calendar(course, calendar):
    time_str = course[3]  # "Tue, 12:30 PM - 1:50 PM" or None

    if not time_str:
        return

    # Split "Tue, 12:30 PM - 1:50 PM" into day and time range
    day_part, time_part = time_str.split(", ", 1)
    start_str, end_str  = time_part.split(" - ")

    start_hour   = datetime.strptime(start_str, "%I:%M %p").hour
    start_minute = datetime.strptime(start_str, "%I:%M %p").minute / 60
    end_hour     = datetime.strptime(end_str,   "%I:%M %p").hour
    end_minute   = datetime.strptime(end_str,   "%I:%M %p").minute / 60
    time_diff    = (end_hour + end_minute) - (start_hour + start_minute)

    rowspan    = math.ceil(round(start_minute + time_diff, 2))
    top_pct    = round((start_minute / rowspan) * 100, 2)
    height_pct = round((time_diff    / rowspan) * 100, 2)

    abbreviation = course[0]
    slot_data    = (abbreviation, rowspan, top_pct, height_pct)

    # Find the starting row
    start_slot = -1
    for i in range(1, len(calendar)):
        if datetime.strptime(calendar[i][0], "%I %p").hour == start_hour:
            start_slot = i
            break

    if start_slot < 0:
        return

    col_map = {"Mon": 1, "Tue": 2, "Wed": 3, "Thu": 4, "Fri": 5}
    col = col_map.get(day_part)
    if col is None:
        return

    calendar[start_slot][col] = slot_data
    for r in range(1, rowspan):
        if start_slot + r < len(calendar):
            calendar[start_slot + r][col] = "SKIP"


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