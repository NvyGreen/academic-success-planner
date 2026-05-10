import sqlite3
from flask import current_app
from course_reg.db import get_db

WORKLOAD_LIGHT_THRESHOLD = 15
WORKLOAD_BALANCED_THRESHOLD = 25
WORKLOAD_HEAVY_THRESHOLD = 35

BURNOUT_MEDIUM_THRESHOLD = 2
BURNOUT_HIGH_THRESHOLD = 4

BURNOUT_COURSES_MEDIUM_THRESHOLD = 0.5
BURNOUT_COURSES_HIGH_THRESHOLD = 0.75
BURNOUT_COURSES_VHIGH_THRESHOLD = 1

IMPACT_MEDIUM_THRESHOLD = 0.8
IMPACT_HIGH_THRESHOLD = 1.2
IMPACT_VHIGH_THRESHOLD = 1.4

EASY_MULTIPLIER = 0.5
MEDIUM_MULTIPLER = 0.8
HARD_MULTIPLIER = 1.3
VHARD_MULTIPLIER = 1.6

AVG_COURSES = 4


# Workload Estimation

def calculate_workload(courses, user_id):
    try:
        db = get_db()
        query = """SELECT gpa FROM student WHERE student_id = :student_id;"""
        cursor = db.execute(query, {"student_id": user_id})
        gpa = cursor.fetchone()[0]

        placeholders = ", ".join([f":code_{i}" for i in range(len(courses))])
        query = f"SELECT difficulty_score, estimated_hours_per_week, credits FROM course WHERE course_code IN ({placeholders})"
        values = {f"code_{i}": code for i, code in enumerate(courses)}
        cursor = db.execute(query, values)
        workload_data = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        return "Error: Could not calculate workload"
    finally:
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
    if final_score <= WORKLOAD_LIGHT_THRESHOLD:
        return "Light"
    elif final_score <= WORKLOAD_BALANCED_THRESHOLD:
        return "Balanced"
    elif final_score <= WORKLOAD_HEAVY_THRESHOLD:
        return "Heavy"
    else:
        return "Overloaded"

def total_hours_per_week(courses):
    try:
        db = get_db()
        placeholders = ", ".join([f":code_{i}" for i in range(len(courses))])
        query = f"SELECT difficulty_score, estimated_hours_per_week FROM course WHERE course_code IN ({placeholders})"
        values = {f"code_{i}": code for i, code in enumerate(courses)}
        cursor = db.execute(query, values)
        raw_hours = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        return "Error: Could not estimate hours per week of work"
    finally:
        cursor.close()

    total_hours = 0
    for datum in raw_hours:
        difficulty_score = datum[0]
        if difficulty_score == 1:
            total_hours += EASY_MULTIPLIER * datum[1]
        elif difficulty_score == 2:
            total_hours += MEDIUM_MULTIPLER * datum[1]
        elif difficulty_score == 3:
            total_hours += datum[1]
        elif difficulty_score == 4:
            total_hours += HARD_MULTIPLIER * datum[1]
        else:
            total_hours += VHARD_MULTIPLIER * datum[1]
    
    return round(total_hours, 2)


# Burnout Estimation
def calculate_burnout_risk(courses, user_id):
    burnout_score = 0
    factors = []

    try:
        db = get_db()
        placeholders = ", ".join([f":code_{i}" for i in range(len(courses))])
        query = f"SELECT credits, difficulty_score FROM course WHERE course_code IN ({placeholders})"
        values = {f"code_{i}": code for i, code in enumerate(courses)}
        cursor = db.execute(query, values)
        course_data = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        return "Error: Could not calculate burnout risk"
    finally:
        cursor.close()

    num_courses = 0
    for course in course_data:
        if course[0] > 0:
            num_courses += 1

    if num_courses >= 4:
        burnout_score += 1
    
    factors.append(len(courses))
    
    workload = calculate_workload(courses, user_id)
    if workload > WORKLOAD_HEAVY_THRESHOLD:
        burnout_score += 3
        factors.append("Overloaded")
    elif workload > WORKLOAD_BALANCED_THRESHOLD:
        burnout_score += 2
        factors.append("Heavy")
    elif workload > WORKLOAD_LIGHT_THRESHOLD:
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
    if score >= BURNOUT_HIGH_THRESHOLD:
        return "High"
    elif score >= BURNOUT_MEDIUM_THRESHOLD:
        return "Medium"
    else:
        return "Low"

def generate_burnout_explanation(factors):
    explanations = []

    if factors[0] == 0:
        explanations.append("You're not taking any classes at all! Add some courses to your schedule to get a proper recommendation.")
        return explanations

    if factors[0] == 4:
        explanations.append(f"You're taking {AVG_COURSES} courses, which is the average amount of courses a UCI student takes, but you should still pace yourself.")
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
    
    if (factors[2] / factors[0]) == BURNOUT_COURSES_VHIGH_THRESHOLD:
        explanations.append("You're only taking hard courses! It's best to replace a few with easier courses.")
    elif (factors[2] / factors[0]) >= BURNOUT_COURSES_HIGH_THRESHOLD:
        explanations.append("You're taking a lot of hard courses, consider taking out one.")
    elif (factors[2] / factors[0]) >= BURNOUT_COURSES_MEDIUM_THRESHOLD:
        explanations.append("At least half of your schedule is hard courses, make sure to pace yourself!")
    else:
        explanations.append("It looks like you aren't taking a lot of difficult courses, consider adding another!")

    return explanations


# GPA / Academic Impact Estimation

def score_academic_impact(courses, user_id):
    try:
        db = get_db()
        query = """SELECT gpa FROM student WHERE student_id = :student_id;"""
        cursor = db.execute(query, {"student_id": user_id})
        gpa = cursor.fetchone()[0]
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        return "Error: could not estimate academic impact"
    finally:
        cursor.close()

    estimate = total_hours_per_week(courses) / 16
    if gpa:
        estimate *= 1 / (gpa / 4.0)
    
    return estimate

def estimate_academic_impact(score):
    if score < IMPACT_MEDIUM_THRESHOLD:
        return "Low"
    elif score >= IMPACT_MEDIUM_THRESHOLD and score < IMPACT_HIGH_THRESHOLD:
        return "Medium"
    elif score >= IMPACT_HIGH_THRESHOLD and score < IMPACT_VHIGH_THRESHOLD:
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
    if workload_score > WORKLOAD_HEAVY_THRESHOLD or burnout_score >= BURNOUT_HIGH_THRESHOLD or academic_impact >= IMPACT_VHIGH_THRESHOLD:
        if workload_score > WORKLOAD_HEAVY_THRESHOLD:
            return "Overall, this is a very overloaded scheudle. Consider dropping some of your courses."
        elif burnout_score >= BURNOUT_HIGH_THRESHOLD:
            return "Overall, this is a very overloaded scheudle. Consider swapping out some of your harder courses for easier ones."
        else:
            return "Overall, this is a very overloaded scheudle. Consider dropping some of your courses or swapping them for easier ones."
    
    # Heavy
    if (workload_score > WORKLOAD_BALANCED_THRESHOLD and burnout_score >= BURNOUT_MEDIUM_THRESHOLD) or (workload_score > WORKLOAD_BALANCED_THRESHOLD and academic_impact >= IMPACT_HIGH_THRESHOLD) or (burnout_score >= BURNOUT_MEDIUM_THRESHOLD and academic_impact >= IMPACT_HIGH_THRESHOLD):
        if workload_score > WORKLOAD_BALANCED_THRESHOLD:
            return "Overall, this is a pretty heavy schedule. Consider dropping a course."
        elif burnout_score >= 3:
            return "Overall, this is a pretty heavy scheudle. Consider swapping out a harder course for an easier one."
        else:
            return "Overall, this is a pretty heavy scheudle. Consider dropping a course or swapping it ouse for an easier one."

    # Balanced
    if workload_score > WORKLOAD_LIGHT_THRESHOLD or academic_impact >= IMPACT_MEDIUM_THRESHOLD:
        return "Overall, this seems like a very manageable schedule. Make sure to stay on top of your classes and pace yourself."

    # Light
    return "Overall, this seems like a pretty light schedule. Consider adding another course, or swapping out one of your courses for a harder one."