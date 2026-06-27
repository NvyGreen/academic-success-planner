import sqlite3
from flask import current_app
from course_reg.db import get_db

WORKLOAD_LIGHT_THRESHOLD = 15
WORKLOAD_BALANCED_THRESHOLD = 25
WORKLOAD_HEAVY_THRESHOLD = 30

BURNOUT_MEDIUM_THRESHOLD = 2
BURNOUT_MED_HIGH_THRESHOLD = 3
BURNOUT_HIGH_THRESHOLD = 4

BURNOUT_COURSES_MEDIUM_THRESHOLD = 0.5
BURNOUT_COURSES_HIGH_THRESHOLD = 0.75
BURNOUT_COURSES_VHIGH_THRESHOLD = 1

IMPACT_MEDIUM_THRESHOLD = 0.8
IMPACT_HIGH_THRESHOLD = 1.2
IMPACT_VHIGH_THRESHOLD = 1.4

EASY_MULTIPLIER = 0.5
MEDIUM_MULTIPLIER = 0.8
HARD_MULTIPLIER = 1.3
VHARD_MULTIPLIER = 1.6

AVG_COURSES = 4


# Workload Estimation
def classify_workload(final_score: float) -> str:
    if final_score <= WORKLOAD_LIGHT_THRESHOLD:
        return "Light"
    elif final_score <= WORKLOAD_BALANCED_THRESHOLD:
        return "Balanced"
    elif final_score <= WORKLOAD_HEAVY_THRESHOLD:
        return "Heavy"
    else:
        return "Overloaded"

def total_hours_per_week(courses: list[int]) -> float:
    if not courses:
        return 0
    
    cursor = None
    try:
        db = get_db()
        placeholders = ", ".join([f":code_{i}" for i in range(len(courses))])
        query = f"SELECT difficulty_score, estimated_hours_per_week FROM course WHERE course_code IN ({placeholders})"
        values = {f"code_{i}": code for i, code in enumerate(courses)}
        cursor = db.execute(query, values)
        raw_hours = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not estimate hours per week of work")
    finally:
        if cursor is not None:
            cursor.close()

    total_hours = 0
    for datum in raw_hours:
        difficulty_score = datum[0]
        if difficulty_score == 1:
            total_hours += EASY_MULTIPLIER * datum[1]
        elif difficulty_score == 2:
            total_hours += MEDIUM_MULTIPLIER * datum[1]
        elif difficulty_score == 3:
            total_hours += datum[1]
        elif difficulty_score == 4:
            total_hours += HARD_MULTIPLIER * datum[1]
        else:
            total_hours += VHARD_MULTIPLIER * datum[1]
    
    return round(total_hours, 2)


# Burnout Estimation
def calculate_burnout_risk(courses: list[int]) -> tuple[int, dict]:
    if not courses:
        return (0, {"num_courses": 0, "workload": "-", "num_difficult": 0})
    
    burnout_score = 0
    factors = {}
    cursor = None

    try:
        db = get_db()
        placeholders = ", ".join([f":code_{i}" for i in range(len(courses))])
        query = f"SELECT credits, difficulty_score FROM course WHERE course_code IN ({placeholders})"
        values = {f"code_{i}": code for i, code in enumerate(courses)}
        cursor = db.execute(query, values)
        course_data = cursor.fetchall()
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not calculate burnout risk")
    finally:
        if cursor is not None:
            cursor.close()

    num_courses = 0
    for course in course_data:
        if course["credits"] > 0:
            num_courses += 1

    if num_courses >= 4:
        burnout_score += 1
    
    factors["num_courses"] = num_courses
    
    workload = total_hours_per_week(courses)
    if workload > WORKLOAD_HEAVY_THRESHOLD:
        burnout_score += 3
        factors["workload"] = "Overloaded"
    elif workload > WORKLOAD_BALANCED_THRESHOLD:
        burnout_score += 2
        factors["workload"] = "Heavy"
    elif workload > WORKLOAD_LIGHT_THRESHOLD:
        burnout_score += 1
        factors["workload"] = "Balanced"
    else:
        factors["workload"] = "Light"

    num_difficult = 0
    for course in course_data:
        if course["difficulty_score"] >= 3:
            burnout_score += 1
            num_difficult += 1
    
    factors["num_difficult"] = num_difficult
    
    return (burnout_score, factors)

def estimate_burnout_risk(score: int) -> str:
    if score >= BURNOUT_HIGH_THRESHOLD:
        return "High"
    elif score >= BURNOUT_MEDIUM_THRESHOLD:
        return "Medium"
    else:
        return "Low"


def generate_burnout_explanation(factors: dict) -> str:
    if factors["num_courses"] == 0:
        return "No courses added."
    
    if factors["num_courses"] > AVG_COURSES:
        return "A lot of courses."
    elif factors["num_courses"] < AVG_COURSES:
        return "Not a lot of courses."
    
    if factors["workload"] == "Overloaded" or (factors["num_difficult"] / factors["num_courses"]) >= BURNOUT_COURSES_VHIGH_THRESHOLD:
        return "Too many hard courses."
    elif factors["workload"] == "Heavy" or (factors["num_difficult"] / factors["num_courses"]) >= BURNOUT_COURSES_HIGH_THRESHOLD:
        return "A good amount of hard courses."
    elif factors["workload"] == "Light" or (factors["num_difficult"] / factors["num_courses"]) < BURNOUT_COURSES_MEDIUM_THRESHOLD:
        return "Not a lot of hard courses."
    
    return "Good balance of courses."


# GPA / Academic Impact Estimation

def calculate_academic_impact(courses: list[int], user_id: int) -> float:
    cursor = None
    try:
        db = get_db()
        query = """SELECT gpa FROM student WHERE student_id = :student_id;"""
        cursor = db.execute(query, {"student_id": user_id})
        row = cursor.fetchone()
        gpa = row[0] if row else None
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: could not estimate academic impact")
    finally:
        if cursor is not None:
            cursor.close()

    estimate = total_hours_per_week(courses) / (WORKLOAD_LIGHT_THRESHOLD + 1)
    if gpa is not None:
        estimate *= 1 / (gpa / 4.0)
    
    return estimate

def classify_academic_impact(score: float) -> str:
    if score < IMPACT_MEDIUM_THRESHOLD:
        return "Low"
    elif score < IMPACT_HIGH_THRESHOLD:
        return "Medium"
    elif score < IMPACT_VHIGH_THRESHOLD:
        return "High"
    else:
        return "Very High"

def generate_impact_explanation(desc: str) -> str:
    if desc == "Low":
        return "Few/Easy courses"
    elif desc == "Medium":
        return "Good balance"
    elif desc == "High":
        return "Hard/Lots of courses"
    else:
        return "Lots of hard courses"


# Recommendation generation
def generate_recommendation(workload_score: float, burnout_score: float, academic_impact: float) -> str:
    # Overloaded
    if workload_score > WORKLOAD_HEAVY_THRESHOLD or burnout_score >= BURNOUT_HIGH_THRESHOLD or academic_impact >= IMPACT_VHIGH_THRESHOLD:
        if workload_score > WORKLOAD_HEAVY_THRESHOLD:
            return "Drop some courses."
        elif burnout_score >= BURNOUT_HIGH_THRESHOLD:
            return "Swap out some hard courses."
        else:
            return "Drop or swap some courses."
    
    # Heavy
    if (workload_score > WORKLOAD_BALANCED_THRESHOLD and burnout_score >= BURNOUT_MEDIUM_THRESHOLD) or (workload_score > WORKLOAD_BALANCED_THRESHOLD and academic_impact >= IMPACT_HIGH_THRESHOLD) or (burnout_score >= BURNOUT_MEDIUM_THRESHOLD and academic_impact >= IMPACT_HIGH_THRESHOLD):
        if workload_score > WORKLOAD_BALANCED_THRESHOLD:
            return "Drop a course."
        elif burnout_score >= BURNOUT_MED_HIGH_THRESHOLD:
            return "Swap out a hard course."
        else:
            return "Drop or swap a hard course."

    # Balanced
    if workload_score > WORKLOAD_LIGHT_THRESHOLD or academic_impact >= IMPACT_MEDIUM_THRESHOLD:
        return "Pace yourself!"

    # Light
    return "Add or swap in a hard course!"


def get_total_credits(courses: list[int]) -> int:
    if not courses:
        return 0
    
    cursor = None
    try:
        db = get_db()
        placeholders = ", ".join([f":code_{i}" for i in range(len(courses))])
        query = f"SELECT SUM(credits) FROM course WHERE course_code IN ({placeholders})"
        values = {f"code_{i}": code for i, code in enumerate(courses)}
        cursor = db.execute(query, values)
        total = cursor.fetchone()[0]
        return total if total is not None else 0
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not calculate total credits")
    finally:
        if cursor is not None:
            cursor.close()


def classify_difficulty_ratio(num_difficult: int, num_courses: int) -> str:
    if num_courses == 0:
        return "Low"

    ratio = num_difficult / num_courses

    if ratio >= BURNOUT_COURSES_VHIGH_THRESHOLD:
        return "Very High"
    elif ratio >= BURNOUT_COURSES_HIGH_THRESHOLD:
        return "High"
    elif ratio >= BURNOUT_COURSES_MEDIUM_THRESHOLD:
        return "Medium"
    else:
        return "Low"


def generate_sparkline_points(values: list[float], width=240, height=60, padding=6) -> str:
    if not values:
        return ""

    if len(values) == 1:
        values = values * 2

    min_val = min(values)
    max_val = max(values)
    value_range = max_val - min_val if max_val != min_val else 1

    step = (width - 2 * padding) / (len(values) - 1)

    points = []
    for i, value in enumerate(values):
        x = padding + i * step
        y = height - padding - ((value - min_val) / value_range) * (height - 2 * padding)
        points.append(f"{x:.1f},{y:.1f}")

    return " ".join(points)


def get_trend_direction(values: list[float], lower_is_better=True) -> tuple[str, str]:
    if len(values) < 2:
        return ("Not enough data yet", "neutral")

    delta = values[-1] - values[-2]

    if delta == 0:
        return ("Stable", "neutral")

    improving = (delta < 0) if lower_is_better else (delta > 0)

    if improving:
        return ("Improving", "positive")
    else:
        return ("Worsening", "negative")