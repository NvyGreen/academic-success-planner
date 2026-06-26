import sqlite3
from flask import current_app
from course_reg import logic, decision_engine, analytics
from course_reg.db import get_db

def add_new_schedule(student, courses):
    workload = logic.total_hours_per_week(courses)
    burnout_data = logic.calculate_burnout_risk(courses)
    burnout = burnout_data[0]
    burnout_explanation = logic.generate_burnout_explanation(burnout_data[1])
    impact = logic.calculate_academic_impact(courses, student)
    impact_explanation = logic.generate_impact_explanation(logic.classify_academic_impact(impact))
    recommendation, rec_type, old_course, new_course = decision_engine.generate_detailed_recommendation(student, courses)
    num_courses, credits = get_schedule_stats(courses)
    details = f"{num_courses} courses, {credits} credits"
    sched_impact = f"{workload} hrs/wk, Burnout: {logic.estimate_burnout_risk(burnout)}"

    if old_course != -1:
        schedule_stats = decision_engine.get_old_and_new_schedule_stats(student, courses, old_course, new_course)
        raw_bullet, raw_why, raw_table = decision_engine.generate_change_summary(schedule_stats[0], schedule_stats[1])
        bullet_summary = serialize_list(raw_bullet)
        why_summary = serialize_list(raw_why)
        table_summary = serialize_matrix(raw_table)

        old_schedule, new_schedule = schedule_stats
        workload_change = old_schedule.workload - new_schedule.workload
        burnout_change = old_schedule.burnout - new_schedule.burnout
        impact_change = old_schedule.impact - new_schedule.impact

        rec_impact_list = []
        if workload_change > 0:
            rec_impact_list.append(f"{workload_change * -1:+} hrs")
        if burnout_change > 0:
            rec_impact_list.append(f"{burnout_change * -1:+} burnout")
        if impact_change < 0:
            rec_impact_list.append(f"{impact_change * -1:+} impact")
        
        rec_impact = serialize_list(rec_impact_list)
    else:
        bullet_summary = "No changes necessary"
        why_summary = "there is a good balance of courses"
        table_summary = f"Workload,{workload} hrs/week,{workload} hrs/week,0 hrs;Burnout Risk,{logic.estimate_burnout_risk(burnout)} ({burnout}),{logic.estimate_burnout_risk(burnout)} ({round(burnout, 2)}),0;Academic Impact,{logic.classify_academic_impact(impact)} ({round(impact, 2)}),{logic.classify_academic_impact(impact)} ({round(impact, 2)}),0"

        workload_change = 0
        burnout_change = 0
        impact_change = 0

        rec_impact = bullet_summary
    
    analytics.save_metrics(student, workload, burnout, burnout_explanation, impact, impact_explanation, recommendation, rec_type, bullet_summary, why_summary, table_summary, "Viewed")
    analytics.save_activity(student, "Evaluation", "Schedule Version ", details, sched_impact, workload_change, burnout_change, impact_change)
    analytics.save_activity(student, "Viewed", recommendation, why_summary, rec_impact, workload_change, burnout_change, impact_change)


def get_schedule_stats(courses) -> tuple[int, int]:
    cursor = None
    try:
        db = get_db()
        placeholders = ", ".join([f":code_{i}" for i in range(len(courses))])
        query = f"SELECT credits FROM course WHERE course_code IN ({placeholders})"
        values = {f"code_{i}": code for i, code in enumerate(courses)}
        cursor = db.execute(query, values)
        course_credits = cursor.fetchall()
        
        num_courses = 0
        credits = 0
        for course in course_credits:
            credits += course["credits"]
            if course["credits"] > 0:
                num_courses += 1
        
        return num_courses, credits
    except sqlite3.Error as e:
        current_app.logger.error(f"Database error: {e}")
        raise sqlite3.Error("Error: Could not get schedule stats")
    finally:
        if cursor is not None:
            cursor.close()


def serialize_list(arr: list[str]) -> str:
    return ",".join(arr)


def deserialize_list(text: str) -> list[str]:
    return text.split(",") if text else []


def serialize_matrix(matrix: list[list[str]]) -> str:
    arr = []
    for row in matrix:
        arr.append(",".join(row))
    
    return ";".join(arr)


def deserialize_matrix(text: str) -> list[list[str]]:
    if not text:
        return []
    arr = text.split(";")
    matrix = []
    for line in arr:
        matrix.append(line.split(","))
    
    return matrix