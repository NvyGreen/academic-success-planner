from flask import current_app
from datetime import datetime



def get_short_courses(course_codes):
    if len(course_codes) == 0:
        return []
    
    query = """SELECT course.course_code, course.course_name, course.department, course.course_number, course.type, instructor.first_name, instructor.last_name, course.is_online, course.building_code, course.room, course.cancelled, course.num_enrolled, course.capacity, course.waitlist, course.days, course.start_time, course.end_time FROM course_instructor JOIN course ON course_instructor.course_id = course.course_id JOIN instructor ON course_instructor.instructor_id = instructor.instructor_id WHERE """

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

        # Times
        if raw_course[15] is None or raw_course[16] is None:
            course += [None, None]
        else:
            start_time_raw = str(datetime.fromisoformat(raw_course[15]).hour) + ":" + str(datetime.fromisoformat(raw_course[15]).minute)
            end_time_raw = str(datetime.fromisoformat(raw_course[16]).hour) + ":" + str(datetime.fromisoformat(raw_course[16]).minute)
            start_time = datetime.strptime(start_time_raw, "%H:%M").strftime("%#I:%M %p")
            end_time = datetime.strptime(end_time_raw, "%H:%M").strftime("%#I:%M %p")
            course.append(start_time)
            course.append(end_time)

        if (raw_course[7] == 1):
            course.append("Online")
        else:
            course.append(raw_course[8] + " " + raw_course[9])    # building_code room

        # Status
        if raw_course[10] == 1:
            course.append("CANCELLED")
        elif raw_course[11] < raw_course[12]:      # num_enrolled < capacity?
            course.append("Open")
        elif raw_course[13] >= 0:                # waitlist >= 0?
            course.append("Waitlist")
        elif raw_course[11] > raw_course[12]:    # num_enrolled > capacity
            course.append("OVER")
        else:
            course.append("FULL")
        
        course.append(raw_course[14])    # days
        
        courses.append(course)
    
    cursor.close()
    return courses


def get_short_courses_final(course_codes):
    if len(course_codes) == 0:
        return []
    
    query = """SELECT course.course_code, course.course_name, course.department, course.course_number, course.type, instructor.first_name, instructor.last_name, course.final, course.is_online, course.building_code, course.room, course.cancelled, course.num_enrolled, course.capacity, course.waitlist FROM course_instructor JOIN course ON course_instructor.course_id = course.course_id JOIN instructor ON course_instructor.instructor_id = instructor.instructor_id WHERE """

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
    course_len = len(course)
    days = course[course_len - 1]
    start_time = course[course_len - 5]
    end_time = course[course_len - 4]

    if not(days) or not(start_time) or not(end_time):
        return

    
    start_hour = datetime.strptime(start_time, "%I:%M %p").hour
    start_minute = datetime.strptime(start_time, "%I:%M %p").minute / 60
    end_hour = datetime.strptime(end_time, "%I:%M %p").hour
    end_minute = datetime.strptime(end_time, "%I:%M %p").minute / 60
    time_diff = (end_hour + end_minute) - (start_hour + start_minute)

    abbreviation = course[2]
    slot_data = (abbreviation, start_minute, round(time_diff, 2))
    start_slot = -1

    if 'M' in days:
        for i in range(1, len(calendar)):
            calendar_hour = datetime.strptime(calendar[i][0], "%I %p").hour

            if start_hour == calendar_hour:
                start_slot = i
                calendar[start_slot][1] = slot_data
    
    if 'Tu' in days:
        if start_slot >= 0:
            calendar[start_slot][2] = slot_data
        else:
            for i in range(1, len(calendar)):
                calendar_hour = datetime.strptime(calendar[i][0], "%I %p").hour

                if start_hour == calendar_hour:
                    start_slot = i
                    calendar[start_slot][2] = slot_data
    
    if 'W' in days:
        if start_slot >= 0:
            calendar[start_slot][3] = slot_data
        else:
            for i in range(1, len(calendar)):
                calendar_hour = datetime.strptime(calendar[i][0], "%I %p").hour

                if start_hour == calendar_hour:
                    start_slot = i
                    calendar[start_slot][3] = slot_data
    
    if 'Th' in days:
        if start_slot >= 0:
            calendar[start_slot][4] = slot_data
        else:
            for i in range(1, len(calendar)):
                calendar_hour = datetime.strptime(calendar[i][0], "%I %p").hour

                if start_hour == calendar_hour:
                    start_slot = i
                    calendar[start_slot][4] = slot_data
    
    if 'F' in days:
        if start_slot >= 0:
            calendar[start_slot][5] = slot_data
        else:
            for i in range(1, len(calendar)):
                calendar_hour = datetime.strptime(calendar[i][0], "%I %p").hour

                if start_hour == calendar_hour:
                    start_slot = i
                    calendar[start_slot][5] = slot_data


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