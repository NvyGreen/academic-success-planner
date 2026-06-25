from course_reg import logic, decision_engine, analytics

def add_new_schedule(student, courses):
    workload = logic.total_hours_per_week(courses)
    burnout_data = logic.calculate_burnout_risk(courses)
    burnout = burnout_data[0]
    burnout_explanation = logic.generate_burnout_explanation(burnout_data[1])
    impact = logic.calculate_academic_impact(courses, student)
    impact_explanation = logic.generate_impact_explanation(logic.classify_academic_impact(impact))
    recommendation, rec_type, old_course, new_course = decision_engine.generate_detailed_recommendation(student, courses)

    if old_course != -1:
        schedule_stats = decision_engine.get_old_and_new_schedule_stats(student, courses, old_course, new_course)
        raw_bullet, raw_why, raw_table = decision_engine.generate_change_summary(schedule_stats[0], schedule_stats[1])
        bullet_summary = decision_engine.serialize_list(raw_bullet)
        why_summary = decision_engine.serialize_list(raw_why)
        table_summary = decision_engine.serialize_matrix(raw_table)

        old_schedule, new_schedule = schedule_stats
        workload_change = old_schedule.workload - new_schedule.workload
        burnout_change = old_schedule.burnout - new_schedule.burnout
        impact_change = old_schedule.impact - new_schedule.impact
    else:
        bullet_summary = "No changes necessary"
        why_summary = "there is a good balance of courses"
        table_summary = f"Workload,{workload} hrs/week,{workload} hrs/week,0 hrs;Burnout Risk,{logic.estimate_burnout_risk(burnout)} ({burnout}),{logic.estimate_burnout_risk(burnout)} ({round(burnout, 2)}),0;Academic Impact,{logic.classify_academic_impact(impact)} ({impact}),{logic.classify_academic_impact(impact)} ({round(impact, 2)}),0"

        workload_change = float('-inf')
        burnout_change = float('-inf')
        impact_change = float('-inf')
    
    analytics.save_metrics(student, workload, burnout, burnout_explanation, impact, impact_explanation, recommendation, rec_type, bullet_summary, why_summary, table_summary)
    analytics.save_activity(student, "Evaluation", "Schedule Version ", recommendation, "TODO", workload_change, burnout_change, impact_change)