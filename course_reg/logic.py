from flask import current_app

def calculate_workload(courses, user_id):
    query = """SELECT gpa FROM student WHERE student_id = :student_id;"""
    cursor = current_app.db.execute(query, {"student_id": user_id})
    gpa = cursor.fetchone()[0]
    
    query = """SELECT difficulty_score, estimated_hours_per_week, credits FROM course WHERE """
    for i in range(len(courses)):
        if i == 0:
            query += """course_code = """ + str(courses[i])
        else:
            query += """ OR course_code = """ + str(courses[i])
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

def classify_workload(final_score):
    if final_score <= 15:
        return "Light"
    elif final_score <= 25:
        return "Balanced"
    elif final_score <= 35:
        return "Heavy"
    else:
        return "Overloaded"

def total_hours_per_week(courses):    
    query = """SELECT estimated_hours_per_week FROM course WHERE """
    for i in range(len(courses)):
        if i == 0:
            query += """course_code = """ + str(courses[i])
        else:
            query += """ OR course_code = """ + str(courses[i])
    query += """;"""

    cursor = current_app.db.execute(query)
    raw_hours = cursor.fetchall()

    total_hours = 0
    for datum in raw_hours:
        total_hours += datum[0]
    
    return total_hours


def calculate_burnout_risk(courses, user_id):
    burnout_score = 0
    factors = []

    query = """SELECT credits, difficulty_score FROM course WHERE """
    for i in range(len(courses)):
        if i == 0:
            query += """course_code = """ + str(courses[i])
        else:
            query += """ OR course_code = """ + str(courses[i])
    query += """;"""

    cursor = current_app.db.execute(query)
    course_data = cursor.fetchall()
    cursor.close()

    num_courses = 0
    for course in course_data:
        if course[0] > 0:
            num_courses += 1

    if num_courses >= 4:
        burnout_score += 1
    
    factors.append(len(courses))
    
    workload = calculate_workload(courses, user_id)
    if workload >= 36:
        burnout_score += 3
        factors.append("Overloaded")
    elif workload >= 26:
        burnout_score += 2
        factors.append("Heavy")
    elif workload >= 16:
        burnout_score += 1
        factors.append("Balanced")
    else:
        factors.append("Light")

    num_difficult = 0
    for course in course_data:
        if course[1] >= 4:
            burnout_score += 1
            num_difficult += 1
    
    factors.append(num_difficult)
    
    if burnout_score >= 4:
        return ("High", factors)
    elif burnout_score >= 2:
        return ("Medium", factors)
    else:
        return ("Low", factors)

def generate_explanation(factors):
    explanations = []

    if factors[0] == 4:
        explanations.append("You're taking 4 courses, which is the average amount of courses a UCI student takes, but you should still pace yourself.")
    elif factors[0] > 4:
        explanations.append(f"You're taking {factors[0]} courses, which is more than what the average UCI student takes. Make sure to pace yourself, and consider taking out some classes if you think it might be too much.")
    else:
        explanations.append(f"You're taking {factors[0]} courses, which is less than what the average UCI student takes. Consider adding some more courses")
    
    if factors[1] == "Overloaded":
        explanations.append("Your schedule is overloaded! It's best to take out some of your more difficult courses.")
    elif factors[1] == "Heavy":
        explanations.append("Your schedule looks heavy, so consider taking out some of your more difficult courses.")
    elif factors[1] == "Balanced":
        explanations.append("Your schedule looks pretty balanced, but make sure to pace yourself!")
    else:
        explanations.append("You're schedule looks pretty light, consider adding some more difficult courses.")
    
    if (factors[2] / factors[0]) == 1:
        explanations.append("You're only taking hard courses! It's best to replace a few with easier courses.")
    elif (factors[2] / factors[0]) >= 0.75:
        explanations.append("You're taking a lot of hard courses, consider taking out one.")
    elif (factors[2] / factors[0]) >= 0.5:
        explanations.append("At least half of your schedule is hard courses, make sure to pace yourself!")
    else:
        explanations.append("It looks like you aren't taking a lot of difficult courses, consider adding another!")

    return explanations