from flask import current_app


# Workload Estimation

def calculate_workload(courses, user_id):
    query = """SELECT gpa FROM student WHERE student_id = :student_id;"""
    cursor = current_app.db.execute(query, {"student_id": user_id})
    gpa = cursor.fetchone()[0]

    placeholders = ", ".join([f":code_{i}" for i in range(len(courses))])
    query = f"SELECT difficulty_score, estimated_hours_per_week, credits FROM course WHERE course_code IN ({placeholders})"
    values = {f"code_{i}": code for i, code in enumerate(courses)}
    cursor = current_app.db.execute(query, values)
    workload_data = cursor.fetchall()
    cursor.close()

    workload_score = 0
    total_credits = 0

    for datum in workload_data:
        total_credits += datum[2]
        workload_score += datum[0] * datum[1] * 2 * datum[2]
    
    if gpa:
        workload_score /= total_credits + gpa
    else:
        workload_score /= total_credits
    
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
    placeholders = ", ".join([f":code_{i}" for i in range(len(courses))])
    query = f"SELECT difficulty_score, estimated_hours_per_week FROM course WHERE course_code IN ({placeholders})"
    values = {f"code_{i}": code for i, code in enumerate(courses)}
    cursor = current_app.db.execute(query, values)
    raw_hours = cursor.fetchall()
    cursor.close()

    total_hours = 0
    for datum in raw_hours:
        difficulty_score = datum[0]
        if difficulty_score == 1:
            total_hours += 0.5 * datum[1]
        elif difficulty_score == 2:
            total_hours += 0.8 * datum[1]
        elif difficulty_score == 3:
            total_hours += datum[1]
        elif difficulty_score == 4:
            total_hours += 1.3 * datum[1]
        else:
            total_hours += 1.6 * datum[1]
    
    return round(total_hours, 2)


# Burnout Estimation
def calculate_burnout_risk(courses, user_id):
    burnout_score = 0
    factors = []

    placeholders = ", ".join([f":code_{i}" for i in range(len(courses))])
    query = f"SELECT credits, difficulty_score FROM course WHERE course_code IN ({placeholders})"
    values = {f"code_{i}": code for i, code in enumerate(courses)}
    cursor = current_app.db.execute(query, values)
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
    
    return (burnout_score, factors)

def estimate_burnout_risk(score):
    if score >= 4:
        return "High"
    elif score >= 2:
        return "Medium"
    else:
        return "Low"

def generate_burnout_explanation(factors):
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


# GPA / Academic Impact Estimation

def score_academic_impact(courses, user_id):
    query = """SELECT gpa FROM student WHERE student_id = :student_id;"""
    cursor = current_app.db.execute(query, {"student_id": user_id})
    gpa = cursor.fetchone()[0]
    cursor.close()

    estimate = total_hours_per_week(courses) / 16
    if gpa:
        estimate *= 1 / (gpa / 4.0)
    
    return estimate

def estimate_academic_impact(score):
    if score < 0.8:
        return "Low"
    elif score >= 0.8 and score < 1.2:
        return "Medium"
    elif score >= 1.2 and score < 1.4:
        return "High"
    else:
        return "Very High"

def generate_impact_explanation(desc):
    if desc == "Low":
        return "You probably got this score because you aren't taking a lot of classes, or you're taking easier classes. If your workload is rated as light and your burnout risk is low, consider taking some harder classes. As of right now though, this schedule shouldn't negatively impact your GPA."
    elif desc == "Medium":
        return "You probably got this score because you have a good mix of easier and challenging classes. If your workload is rated as balanced and your burnout risk is medium, you have a good schedule to make the most of this term! As long as you put effort into studying, your GPA will be fine."
    elif desc == "High":
        return "You probably got this score because you're taking quite a few hard classes, or you're taking a lot of units in general. If your workload is rated as heavy but your burnout score is medium, you should be able to maintain or improve your GPA as long as you maintain good discipline. If your burnout score is high, however, you might want to replace some of your courses with easier ones, so your GPA isn't negatively impacted."
    else:
        return "You probably got this score because you're taking a ton of difficult classes. If your workload is rated as overloaded and your burnout score is high, you should take less units or swap out some challenging classes for easier ones. As of right now, this schedule is highly likely to negatively affect your GPA."


# Recommendation generation
def generate_recommendation(workload_score, burnout_score, academic_impact):
    # Overloaded
    if workload_score > 35 or burnout_score >= 4 or academic_impact >= 1.4:
        if workload_score > 35:
            return "Overall, this is a very overloaded scheudle. Consider dropping some of your courses."
        elif burnout_score >= 4:
            return "Overall, this is a very overloaded scheudle. Consider swapping out some of your harder courses for easier ones."
        else:
            return "Overall, this is a very overloaded scheudle. Consider dropping some of your courses or swapping them for easier ones."
    
    # Heavy
    if (workload_score > 25 and burnout_score >= 2) or (workload_score > 25 and academic_impact >= 1.2) or (burnout_score >= 2 and academic_impact >= 1.2):
        if workload_score > 25:
            return "Overall, this is a pretty heavy schedule. Consider dropping a course."
        elif burnout_score >= 3:
            return "Overall, this is a pretty heavy scheudle. Consider swapping out a harder course for an easier one."
        else:
            return "Overall, this is a pretty heavy scheudle. Consider dropping a course or swapping it ouse for an easier one."

    # Balanced
    if workload_score > 15 or academic_impact >= 0.8:
        return "Overall, this seems like a very manageable schedule. Make sure to stay on top of your classes and pace yourself."

    # Light
    return "Overall, this seems like a pretty light schedule. Consider adding another course, or swapping out one of your courses for a harder one."