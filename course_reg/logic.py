from flask import current_app

def calculate_workload(courses, user_id):
    query = """SELECT gpa FROM student WHERE student_id = :student_id;"""
    cursor = current_app.db.execute(query, {"student_id": user_id})
    gpa = cursor.fetchone()[0]

    course_ids = []
    for course in courses:
        course_ids.append(course[-1])
    
    query = """SELECT difficulty_score, estimated_hours_per_week, credits FROM course WHERE """
    for i in range(len(course_ids)):
        if i == 0:
            query += """course_id = """ + str(course_ids[i])
        else:
            query += """ OR course_id = """ + str(course_ids[i])
    query += """;"""

    cursor = current_app.db.execute(query)
    workload_data = cursor.fetchall()

    workload_score = 0
    total_credits = 0

    for datum in workload_data:
        total_credits += datum[2]
        workload_score += datum[0] * datum[1] * 2 * datum[2]
    
    if gpa:
        workload_score /= total_credits + gpa
    else:
        workload_score /= total_credits
    
    cursor.close()
    return workload_score