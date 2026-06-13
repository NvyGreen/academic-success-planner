import functools
from urllib.parse import urlparse, urljoin
import sqlite3
from passlib.hash import pbkdf2_sha256
from flask import (
    Blueprint,
    render_template,
    url_for,
    session,
    redirect,
    current_app,
    flash,
    request
)
from course_reg.db import get_db
from course_reg.forms import LoginForm, FilterForm, AdvancedFilterForm
from course_reg.models import Filters, AdvancedFilters
from course_reg import analytics, filter_methods, schedule_methods, register_methods, logic


pages = Blueprint(
    "pages", __name__, template_folder="templates", static_folder="static"
)


def login_required(route):
    @functools.wraps(route)
    def route_wrapper(*args, **kwargs):
        if session.get("email") is None:
            return redirect(url_for(".login"))
        
        return route(*args, **kwargs)
    
    return route_wrapper


def safe_redirect(target, fallback = "/"):
    if not target:
        return redirect(fallback)
    
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))

    if test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc:
        return redirect(target)

    return redirect(fallback)


@pages.route("/")
@login_required
def index():
    try:
        register_methods.enroll_from_waitlist()
    except sqlite3.Error as e:
        pass

    try:
        session["user_courses"] = schedule_methods.get_courses_from_list(session["user_id"], "enrollment")
    except sqlite3.Error as e:
        session["user_courses"] = str(e)
    session["unreged_courses"] = {}

    try:
        session["user_waitlist"] = schedule_methods.get_courses_from_list(session["user_id"], "student_waitlist")
    except sqlite3.Error as e:
        session["user_waitlist"] = str(e)

    session["temp_courses"] = []
    session["old_courses"] = []
    session["load_bearing"] = False
    session["cancel"] = False
    
    if session.get("filter_courses"):
        session.pop("filter_courses")
    
    if session.get("filter_criteria"):
        session.pop("filter_criteria")
    
    return redirect(url_for(".user_courses"))


@pages.route("/courses")
@login_required
def user_courses():
    if isinstance(session["old_courses"], str):
        flash(session["old_courses"], "error")
    session["old_courses"] = []

    if isinstance(session["user_courses"], str):
        flash(session["user_courses"], "error")
        courses = []
        calendar = [[]]
        workload_score = "-"
        classification = "-"
        avg_hours = "-"
    else:
        try:
            courses = schedule_methods.get_short_courses(session["user_courses"])
        except sqlite3.Error as e:
            flash(str(e), "error")
            courses = []
            calendar = [[]]
        else:
            calendar = schedule_methods.create_calendar(courses, "courses")

        try:
            workload_score = logic.calculate_workload(session["user_courses"], session["user_id"])
        except sqlite3.Error as e:
            flash(str(e), "error")
            workload_score = "-"
            classification = "-"            
        else:
            classification = logic.classify_workload(workload_score)

        try:
            avg_hours = logic.total_hours_per_week(session["user_courses"])
        except sqlite3.Error as e:
            flash(str(e), "error")
            avg_hours = "-"

    if isinstance(session["unreged_courses"], str):
        flash("All courses successfully registered", "success")
    else:
        for course, reqs in session["unreged_courses"].items():
            flash(f"Could not join {course} - {reqs}", "error")
    session["unreged_courses"] = {}

    return render_template(
        "index.html",
        title="Course Registration - My Courses",
        courses=courses,
        calendar=calendar,
        workload_score=workload_score,
        classification=classification,
        avg_hours=avg_hours
    )


@pages.route("/finals")
@login_required
def user_finals():
    if isinstance(session["user_courses"], str):
        flash(session["user_courses"], "error")
        courses = []
        calendar = [[]]
    else:
        try:
            courses = schedule_methods.get_short_courses_final(session["user_courses"])
        except sqlite3.Error as e:
            flash(str(e), "error")
            courses = []
            calendar = [[]]
        # if isinstance(courses, str):
        #     flash(e, "error")
        #     courses = []
        #     calendar = [[]]
        else:
            calendar = schedule_methods.create_calendar(courses, "final")

    return render_template(
        "index_finals.html",
        title="Course Registration - My Finals",
        courses=courses,
        calendar=calendar
    )


@pages.route("/quarter")
@login_required
def user_quarter():
    if isinstance(session["user_courses"], str):
        flash(session["user_courses"], "error")
        courses = []
    else:
        try:
            courses = schedule_methods.get_short_courses(session["user_courses"])
        except sqlite3.Error as e:
            flash(str(e), "error")
            courses = []

    return render_template(
        "index_quarter.html",
        title="Course Registration - Current Quarter",
        courses=courses
    )


@pages.route("/waitlists")
@login_required
def user_waitlists():
    if isinstance(session["user_waitlist"], str):
        flash(session["user_waitlist"], "error")
        courses = []
    else:
        try:
            courses = filter_methods.get_user_waitlist(session["user_id"], session["user_waitlist"])
        except sqlite3.Error as e:
            flash(str(e), "error")
            courses = []
            return redirect(url_for(".index"))

    return render_template(
        "waitlists.html",
        title="Course Registration - My Waitlists",
        courses=courses
    )


@pages.route("/login", methods=["GET", "POST"])
def login():
    if session.get("email"):
        return redirect(url_for(".index"))

    form = LoginForm()

    if form.validate_on_submit():
        db = get_db()
        user_cursor = db.execute(
            """SELECT student_id, email, password
            FROM student
            WHERE email = :email""",
            {"email": form.email.data}
        )
        user_data = user_cursor.fetchone()
        user_cursor.close()

        if not user_data:
            flash("Login credentials not correct")
            return redirect(url_for(".login"))
        
        user_id = user_data[0]
        user_email = user_data[1]
        user_pwd = user_data[2]

        if pbkdf2_sha256.verify(form.password.data, user_pwd):
            session["user_id"] = user_id
            session["email"] = user_email

            return redirect(url_for(".index"))
        
        flash("Login credentials not correct")

    return render_template(
        "login.html",
        title="Course Registration - Login",
        form=form
    )


@pages.route("/drop-courses")
@login_required
def drop_courses():
    try:
        courses = filter_methods.get_courses_from_codes(session["user_courses"])
    except sqlite3.Error as e:
        flash(str(e), "error")
        return redirect(url_for(".index"))

    return render_template(
        "drop_courses.html",
        title="Course Registration - Drop Courses",
        courses=courses
    )


@pages.route("/filter-courses", methods=["GET", "POST"])
@login_required
def filter_courses():
    if session["cancel"]:
        session["temp_courses"] = []
        session["cancel"] = False
    
    form = FilterForm()

    try:
        form.gen_cat.choices = filter_methods.prep_ge()
    except sqlite3.Error as e:
        flash(str(e), "error")
        return safe_redirect(request.args.get("current_page"), fallback=url_for(".filter_courses"))
    
    try:
        form.department.choices = filter_methods.prep_departments()
    except sqlite3.Error as e:
        flash(str(e), "error")
        return safe_redirect(request.args.get("current_page"), fallback=url_for(".filter_courses"))
    

    if form.validate_on_submit():
        if isinstance(session["user_courses"], str):
            flash(session["user_courses"], "error")
            return safe_redirect(request.args.get("current_page"), fallback=url_for(".filter_courses"))

        if isinstance(session["user_waitlist"], str):
            flash(session["user_waitlist"], "error")
            return safe_redirect(request.args.get("current_page"), fallback=url_for(".filter_courses"))
        
        filters = Filters(
            ge_cat=int(form.gen_cat.data),
            department=int(form.department.data),
            course_num=form.course_num.data,
            course_code=form.course_code.data,
            course_level=form.course_level.data,
            instructor=form.instructor.data
        )
        
        try:
            session["filter_courses"] = filter_methods.get_courses(filters, session["temp_courses"], session["user_courses"], session["user_waitlist"])
            session["filter_criteria"] = filter_methods.get_criteria(filters)
        except sqlite3.Error as e:
            flash(str(e), "error")
            return safe_redirect(request.args.get("current_page"), fallback=url_for(".filter_courses"))
        
        return redirect(url_for(".course_listing"))

    return render_template(
        "filter_courses.html",
        title="Course Registration - Filter Courses",
        form=form
    )


@pages.route("/filter-courses/advanced", methods=["GET", "POST"])
@login_required
def filter_courses_advanced():
    form = AdvancedFilterForm()
    
    try:
        form.gen_cat.choices = filter_methods.prep_ge()
    except sqlite3.Error as e:
        flash(str(e), "error")
        return safe_redirect(request.args.get("current_page"), fallback=url_for(".filter_courses"))
    
    try:
        form.department.choices = filter_methods.prep_departments()
    except sqlite3.Error as e:
        flash(form.department.choices, "error")
        return safe_redirect(request.args.get("current_page"), fallback=url_for(".filter_courses"))

    if form.validate_on_submit():
        if isinstance(session["user_courses"], str):
            flash(session["user_courses"], "error")
            return safe_redirect(request.args.get("current_page"), fallback=url_for(".filter_courses"))

        if isinstance(session["user_waitlist"], str):
            flash(session["user_waitlist"], "error")
            return safe_redirect(request.args.get("current_page"), fallback=url_for(".filter_courses"))
        
        filters = AdvancedFilters(
            ge_cat=int(form.gen_cat.data),
            department=int(form.department.data),
            course_num=form.course_num.data,
            course_code=form.course_code.data,
            course_level=form.course_level.data,
            instructor=form.instructor.data,
            modality=form.modality.data,
            days=form.days.data,
            starts_after=form.starts_after.data,
            ends_before=form.ends_before.data,
            course_full_option=form.course_full_option.data,
            cancel_option=form.cancel_option.data,
            building_code=form.building_code.data,
            room_no=form.room_no.data,
            credits=form.credits.data
        )

        try:
            session["filter_criteria"] = filter_methods.get_criteria_adv(filters)
            session["filter_courses"] = filter_methods.get_courses_adv(filters, session["temp_courses"], session["user_courses"], session["user_waitlist"])
        except sqlite3.Error as e:
            flash(str(e), "error")
            return safe_redirect(request.args.get("current_page"), fallback=url_for(".filter_courses")) or url_for(".filter_courses_advanced")
        
        return redirect(url_for(".course_listing"))

    return render_template(
        "filter_courses_advanced.html",
        title="Course Registration - Filter Courses - Advanced",
        form=form
    )


@pages.route("/listings")
@login_required
def course_listing():
    if not session.get("filter_criteria") or not session.get("filter_courses"):
        return redirect(url_for(".filter_courses"))

    return render_template(
        "course_listing.html",
        title="Course Registration - Listings",
        criteria=session["filter_criteria"],
        courses=session["filter_courses"]
    )


@pages.route("/preview/courses")
@login_required
def preview_courses():
    if isinstance(session["user_courses"], str):
        flash(session["user_courses"], "error")
        courses = []
        calendar = [[]]
    else:
        try:
            courses = schedule_methods.get_short_courses(session["temp_courses"] + session["user_courses"])
        except sqlite3.Error as e:
            flash(str(e), "error")
            courses = []
        calendar = schedule_methods.create_calendar(courses, "courses")

    return render_template(
        "preview_courses.html",
        title="Course Registration - Preview Courses",
        courses=courses,
        calendar=calendar
    )


@pages.route("/preview/finals")
@login_required
def preview_finals():
    if isinstance(session["user_courses"], str):
        flash(session["user_courses"], "error")
        courses = []
        calendar = [[]]
    else:
        try:
            courses = schedule_methods.get_short_courses_final(session["temp_courses"] + session["user_courses"])
        except sqlite3.Error as e:
            flash(str(e), "error")
            courses = []
        # if isinstance(courses, str):
        #     flash(courses, "error")
        #     courses = []
        calendar = schedule_methods.create_calendar(courses, "final")

    return render_template(
        "preview_finals.html",
        title="Course Registration - Preview Finals",
        courses=courses,
        calendar=calendar
    )


@pages.route("/preview/quarter")
@login_required
def preview_quarter():
    if isinstance(session["user_courses"], str):
        flash(session["user_courses"], "error")
        courses = []
    else:
        try:
            courses = schedule_methods.get_short_courses(session["temp_courses"] + session["user_courses"])
        except sqlite3.Error as e:
            flash(str(e), "error")
            courses = []

    return render_template(
        "preview_quarter.html",
        title="Course Registration - View Quarter",
        courses=courses
    )


@pages.route("/analytics")
@login_required
def analytics_page():
    return render_template(
        "analytics.html",
        title="Course Registration - Analytics"
    )


@pages.post("/add-course/<int:code>")
@login_required
def add_course(code):
    if code not in session["temp_courses"]:
        session["load_bearing"] = True
        session["temp_courses"].append(code)

        for course in session["filter_courses"]:
            if course[-1] == code:
                course[0] = "Registered"
                break
        
        session.modified = True
    
    return safe_redirect(request.form.get("current_page"), fallback=url_for(".filter_courses"))


@pages.post("/drop-course/<int:code>")
@login_required
def drop_course(code):
    if code in session["temp_courses"]:
        session["load_bearing"] = False
        session["temp_courses"].remove(code)

        if session.get("filter_courses"):
            for course in session["filter_courses"]:
                if course[-1] == code:
                    course[0] = "Neither"
                    break
        
        session.modified = True
    
    if code in session["user_courses"]:
        session["load_bearing"] = False
        session["user_courses"].remove(code)

        if session.get("filter_courses"):
            for course in session["filter_courses"]:
                if course[-1] == code:
                    course[0] = "Neither"
                    break

        try:
            error = register_methods.drop_course(session["user_id"], code)
        except sqlite3.Error as e:
            flash(error, "error")
            return safe_redirect(request.form.get("current_page"), fallback=url_for(".filter_courses"))

        session.modified = True

    return safe_redirect(request.form.get("current_page"), fallback=url_for(".filter_courses"))


@pages.post("/wait-course/<int:code>")
@login_required
def wait_course(code):
    if isinstance(session["user_waitlist"], str):
        flash(session["user_waitlist"], "error")
    else:
        if code not in session["user_waitlist"]:
            try:
                error = register_methods.waitlist_course(session["user_id"], code)
            except sqlite3.Error as e:
                flash(str(e), "error")
                return safe_redirect(request.form.get("current_page"), fallback=url_for(".filter_courses"))
                

            session["load_bearing"] = True
            session["user_waitlist"].append(code)

            for course in session["filter_courses"]:
                if course[-1] == code:
                    course[0] = "Waitlisted"
                    break

            session.modified = True

    return safe_redirect(request.form.get("current_page"), fallback=url_for(".filter_courses"))


@pages.post("/drop-wait/<int:code>")
@login_required
def drop_wait(code):
    if isinstance(session["user_waitlist"], str):
        flash(session["user_waitlist"], "error")
    else:
        if code in session["user_waitlist"]:
            try:
                error = register_methods.drop_waitlist(session["user_id"], code)
            except sqlite3.Error as e:
                flash(str(e), "error")
                return safe_redirect(request.form.get("current_page"), fallback=url_for(".filter_courses"))
            
            session["load_bearing"] = False
            session["user_waitlist"].remove(code)

            if session.get("filter_courses"):
                for course in session["filter_courses"]:
                    if course[-1] == code:
                        course[0] = "Neither"
                        break
            
            session.modified = True
    
    return safe_redirect(request.form.get("current_page"), fallback=url_for(".filter_courses"))


@pages.get("/cancel-filter")
@login_required
def cancel_filter():
    session["temp_courses"] = []
    return redirect(url_for(".user_courses"))


@pages.get("/cancel-waitlist")
@login_required
def cancel_waitlist():
    session["temp_courses"] = []
    return redirect(url_for(".user_waitlists"))


@pages.get("/cancel-select")
@login_required
def cancel_select():
    session["cancel"] = True
    return redirect(url_for(".filter_courses"))


@pages.get("/confirm-schedule")
@login_required
def confirm_schedule():
    session["old_courses"] = session["user_courses"]
    try:
        session["unreged_courses"] = register_methods.register_courses(session["user_id"], session["temp_courses"])
    except sqlite3.Error as e:
        session["unreged_courses"] = str(e)

    try:
        session["user_courses"] = schedule_methods.get_courses_from_list(session["user_id"], "enrollment")
    except sqlite3.Error as e:
        session["user_courses"] = str(e)
    
    if not isinstance(session["user_courses"], str) and session["old_courses"] != session["user_courses"]:
        try:
            workload = logic.total_hours_per_week(session["user_courses"])
            burnout = logic.calculate_burnout_risk(session["user_courses"], session["user_id"])[0]
            impact = logic.calculate_academic_impact(session["user_courses"], session["user_id"])
            recommendation_count = -1
            analytics.save_metrics(session["user_id"], workload, burnout, impact, recommendation_count)
        except sqlite3.Error as e:
            session["old_courses"] = str(e)

    session["temp_courses"] = []
    session["load_bearing"] = False

    return redirect(url_for(".user_courses"))