from datetime import datetime
import math
import sqlite3
from flask import current_app
from course_reg.db import get_db

ABBR_INDEX = 0
DAYS_INDEX = 3
FINAL_TIME_INDEX = 3
TIMES_INDEX = 4
SLOT_LOOKUP = [
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
    22
]

def get_short_courses(course_codes):
    if len(course_codes) == 0:
        return []

    placeholders = ", ".join([f":code_{i}" for i in range(len(course_codes))])
    query = f"SELECT department.abbreviation, course.course_number, course.course_name, course.type, course.days, course.start_time, course.end_time, (SELECT GROUP_CONCAT(i.last_name || ', ' || SUBSTR(i.first_name, 1, 1) || '.', '; ') FROM course_instructor ci JOIN instructor i ON ci.instructor_id = i.instructor_id WHERE ci.course_id = course.course_id) AS instructors, course.is_online, course.building_code, course.room, course.course_id FROM course JOIN department ON course.department_id = department.department_id WHERE course_code IN ({placeholders})"
    values = {f"code_{i}": code for i, code in enumerate(course_codes)}
    cursor = None

    try:
        db = get_db()
        cursor = db.execute(query, values)
        raw_courses = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: could not fetch courses for calendar")
        # return "Error: Could not fetch courses for calendar"
    finally:
        if cursor is not None:
            cursor.close()

    courses = []
    # (department_id, number, name, days, start_time, end_time, teach_first, teach_last, is_online, building_code, room)
    for raw_course in raw_courses:
        course = []
        
        course.append(raw_course["abbreviation"] + " " + raw_course["course_number"])    # department + course_number
        course.append(raw_course["course_name"])    # name/title
        course.append(raw_course["type"])    # type
        course.append(raw_course["days"])    # days

        # Times
        if raw_course["start_time"] is None or raw_course["end_time"] is None:
            course.append(None)
        else:
            start_dt = datetime.fromisoformat(raw_course["start_time"].replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(raw_course["end_time"].replace("Z", "+00:00"))
            start_time = start_dt.strftime("%I:%M %p").lstrip("0")
            end_time = end_dt.strftime("%I:%M %p").lstrip("0")
            course.append(start_time + " - " + end_time)

        course.append(raw_course["instructors"])    # last_name, first_init (or "; "-joined when co-taught)

        if (raw_course["is_online"] == 1):
            course.append("Online")
        else:
            course.append(raw_course["building_code"] + " " + raw_course["room"])    # building_code room
        
        course.append(raw_course["course_id"])

        courses.append(course)
    
    return courses


def get_short_courses_final(course_codes):
    if len(course_codes) == 0:
        return []

    placeholders = ", ".join([f":code_{i}" for i in range(len(course_codes))])
    query = f"SELECT department.abbreviation, course.course_number, course.course_name, course.type, final.start_datetime, final.end_datetime, course.is_online, course.building_code, course.room FROM course JOIN final ON course.final_id = final.final_id JOIN department ON course.department_id = department.department_id WHERE course_code IN ({placeholders})"
    values = {f"code_{i}": code for i, code in enumerate(course_codes)}
    cursor = None

    try:
        db = get_db()
        cursor = db.execute(query, values)
        raw_courses = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not fetch finals for calendar")
    finally:
        if cursor is not None:
            cursor.close()
    courses = []

    # (department_id, course_number, course_name, type, final_id, is_online, building_code, room)
    for raw_course in raw_courses:
        course = []

        # Abbreviation
        course.append(raw_course["abbreviation"] + " " + raw_course["course_number"])    # department + course_number
        course.append(raw_course["course_name"])    # name/title
        course.append(raw_course["type"])    # type

        # Final Data        
        if (raw_course["start_datetime"] is None) or (raw_course["end_datetime"] is None):
            course.append(None)
        else:
            raw_start = datetime.fromisoformat(raw_course["start_datetime"])
            raw_end = datetime.fromisoformat(raw_course["end_datetime"])
            final_day = raw_start.strftime("%a")
            final_start = raw_start.strftime("%I:%M %p").lstrip("0")
            final_end = raw_end.strftime("%I:%M %p").lstrip("0")
            course.append(final_day + ", " + final_start + " - " + final_end)
        
        if (raw_course["is_online"] == 1):
            course.append("Online")
        else:
            course.append(raw_course["building_code"] + " " + raw_course["room"])    # building_code room

        courses.append(course)
    
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
    days = course[DAYS_INDEX]
    time_str = course[TIMES_INDEX]

    if not days or not time_str:
        return
    start_time, end_time = time_str.split(" - ")

    start_dt     = datetime.strptime(start_time, "%I:%M %p")
    end_dt       = datetime.strptime(end_time,   "%I:%M %p")
    start_hour   = start_dt.hour
    start_minute = start_dt.minute / 60
    end_hour     = end_dt.hour
    end_minute   = end_dt.minute / 60
    time_diff    = (end_hour + end_minute) - (start_hour + start_minute)

    rowspan = math.ceil(round(start_minute + time_diff, 2))
    top_pct = round((start_minute / rowspan) * 100, 2)
    height_pct = round((time_diff / rowspan) * 100, 2)

    abbreviation = course[ABBR_INDEX]
    slot_data = (abbreviation, rowspan, top_pct, height_pct)
    
    try:
        start_slot = SLOT_LOOKUP.index(start_hour) + 1
    except ValueError:
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
    time_str = course[FINAL_TIME_INDEX]  # "Tue, 12:30 PM - 1:50 PM" or None

    if not time_str:
        return

    # Split "Tue, 12:30 PM - 1:50 PM" into day and time range
    day_part, time_part = time_str.split(", ", 1)
    start_str, end_str  = time_part.split(" - ")

    start_dt     = datetime.strptime(start_str, "%I:%M %p")
    end_dt       = datetime.strptime(end_str,   "%I:%M %p")
    start_hour   = start_dt.hour
    start_minute = start_dt.minute / 60
    end_hour     = end_dt.hour
    end_minute   = end_dt.minute / 60
    time_diff    = (end_hour + end_minute) - (start_hour + start_minute)

    rowspan    = math.ceil(round(start_minute + time_diff, 2))
    top_pct    = round((start_minute / rowspan) * 100, 2)
    height_pct = round((time_diff    / rowspan) * 100, 2)

    abbreviation = course[ABBR_INDEX]
    slot_data    = (abbreviation, rowspan, top_pct, height_pct)

    # Find the starting row
    try:
        start_slot = SLOT_LOOKUP.index(start_hour) + 1
    except ValueError:
        return

    col_map = {"Mon": 1, "Tue": 2, "Wed": 3, "Thu": 4, "Fri": 5}
    col = col_map.get(day_part)
    if col is None:
        return

    calendar[start_slot][col] = slot_data
    for r in range(1, rowspan):
        if start_slot + r < len(calendar):
            calendar[start_slot + r][col] = "SKIP"


def get_courses_from_list(user_id, table):
    query = f"""SELECT course.course_code FROM {table} JOIN course ON {table}.course_id = course.course_id WHERE {table}.student_id = :student_id;"""
    cursor = None
    try:
        db = get_db()
        if table not in ["enrollment", "student_waitlist"]:
            raise sqlite3.Error("Wrong table")
        cursor = db.execute(query, {"student_id": user_id})
        codes_tup = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: could not get student's courses")
    finally:
        if cursor is not None:
            cursor.close()

    course_codes = []
    for code in codes_tup:
        course_codes.append(code[0])

    return course_codes