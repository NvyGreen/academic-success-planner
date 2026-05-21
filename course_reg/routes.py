import functools
from urllib.parse import urlparse, urljoin
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
import course_reg.filter_methods
import course_reg.schedule_methods
import course_reg.register_methods
import course_reg.logic


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
    course_reg.register_methods.enroll_from_waitlist()
    session["user_courses"] = course_reg.schedule_methods.get_courses_from_list(session["user_id"], "enrollment")
    session["unreged_courses"] = {}
    session["user_waitlist"] = course_reg.schedule_methods.get_courses_from_list(session["user_id"], "student_waitlist")
    session["temp_courses"] = []
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
    if isinstance(session["user_courses"], str):
        flash(session["user_courses"], "error")
        courses = []
        calendar = [[]]
        workload_score = "-"
        classification = "-"
        avg_hours = "-"
    else:
        courses = course_reg.schedule_methods.get_short_courses(session["user_courses"])
        if isinstance(courses, str):
            flash(courses, "error")
            courses = []
            calendar = [[]]
        else:
            calendar = course_reg.schedule_methods.create_calendar(courses, "courses")

        workload_score = course_reg.logic.calculate_workload(session["user_courses"], session["user_id"])
        if isinstance(workload_score, str):
            flash(workload_score, "error")
            workload_score = "-"
            classification = "-"
        else:
            classification = course_reg.logic.classify_workload(workload_score)

        avg_hours = course_reg.logic.total_hours_per_week(session["user_courses"])
        if isinstance(avg_hours, str):
            flash(avg_hours, "error")
            avg_hours = "-"

    if isinstance(session["unreged_courses"], str):
        flash(session["unreged_courses"], "error")
    elif "Success" in session["unreged_courses"]:
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
        courses = course_reg.schedule_methods.get_short_courses_final(session["user_courses"])
        if isinstance(courses, str):
            flash(courses, "error")
            courses = []
            calendar = [[]]
        else:
            calendar = course_reg.schedule_methods.create_calendar(courses, "final")

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
        courses = course_reg.schedule_methods.get_short_courses(session["user_courses"])
        if isinstance(courses, str):
            flash(courses, "error")
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
        courses = course_reg.filter_methods.get_user_waitlist(session["user_id"], session["user_waitlist"])
        if isinstance(courses, str):
            flash(courses, "error")
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

        if user_data and pbkdf2_sha256.verify(form.password.data, user_pwd):
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
    courses = course_reg.filter_methods.get_courses_from_codes(session["user_courses"])
    if isinstance(courses, str):
        flash(courses, "error")
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

    form.gen_cat.choices = course_reg.filter_methods.prep_ge()
    if isinstance(form.gen_cat.choices, str):
        flash(form.gen_cat.choices, "error")
        return safe_redirect(request.args.get("current_page"), fallback=url_for(".filter_courses"))
    
    form.department.choices = course_reg.filter_methods.prep_departments()
    if isinstance(form.department.choices, str):
        flash(form.department.choices, "error")
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
        
        session["filter_courses"] = course_reg.filter_methods.get_courses(filters, session["temp_courses"], session["user_courses"], session["user_waitlist"])
        session["filter_criteria"] = course_reg.filter_methods.get_criteria(filters)

        if isinstance(session["filter_courses"], str):
            flash(session["filter_courses"], "error")
            return safe_redirect(request.args.get("current_page"), fallback=url_for(".filter_courses"))
        
        if isinstance(session["filter_criteria"], str):
            flash(session["filter_criteria"], "error")
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
    
    form.gen_cat.choices = course_reg.filter_methods.prep_ge()
    if isinstance(form.gen_cat.choices, str):
        flash(form.gen_cat.choices, "error")
        return safe_redirect(request.args.get("current_page"), fallback=url_for(".filter_courses"))
    
    form.department.choices = course_reg.filter_methods.prep_departments()
    if isinstance(form.department.choices, str):
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
        session["filter_criteria"] = course_reg.filter_methods.get_criteria_adv(filters)
        session["filter_courses"] = course_reg.filter_methods.get_courses_adv(filters, session["temp_courses"], session["user_courses"], session["user_waitlist"])

        if isinstance(session["filter_courses"], str):
            flash(session["filter_courses"], "error")
            return safe_redirect(request.args.get("current_page"), fallback=url_for(".filter_courses")) or url_for(".filter_courses_advanced")

        if isinstance(session["filter_criteria"], str):
            flash(session["filter_criteria"], "error")
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
        courses = course_reg.schedule_methods.get_short_courses(session["temp_courses"] + session["user_courses"])
        if isinstance(courses, str):
            flash(courses, "error")
            courses = []
        calendar = course_reg.schedule_methods.create_calendar(courses, "courses")

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
        courses = course_reg.schedule_methods.get_short_courses_final(session["temp_courses"] + session["user_courses"])
        if isinstance(courses, str):
            flash(courses, "error")
            courses = []
        calendar = course_reg.schedule_methods.create_calendar(courses, "final")

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
        calendar = [[]]
    else:
        courses = course_reg.schedule_methods.get_short_courses(session["temp_courses"] + session["user_courses"])
        if isinstance(courses, str):
            flash(courses, "error")
            courses = []

    return render_template(
        "preview_quarter.html",
        title="Course Registration - View Quarter",
        courses=courses
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

        for course in session["filter_courses"]:
            if course[-1] == code:
                course[0] = "Neither"
                break
        
        session.modified = True
    
    if code in session["user_courses"]:
        session["load_bearing"] = False
        session["user_courses"].remove(code)

        for course in session["filter_courses"]:
            if course[-1] == code:
                course[0] = "Neither"
                break

        error = course_reg.register_methods.drop_course(session["user_id"], code)
        if isinstance(error, str):
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
            error = course_reg.register_methods.waitlist_course(session["user_id"], code)
            if isinstance(error, str):
                flash(error, "error")
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
            error = course_reg.register_methods.drop_waitlist(session["user_id"], code)
            if isinstance(error, str):
                flash(error, "error")
                return safe_redirect(request.form.get("current_page"), fallback=url_for(".filter_courses"))
            
            session["load_bearing"] = False
            session["user_waitlist"].remove(code)

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
# @check_window
def confirm_schedule():
    session["unreged_courses"] = course_reg.register_methods.register_courses(session["user_id"], session["temp_courses"])
    session["user_courses"] = course_reg.schedule_methods.get_courses_from_list(session["user_id"], "enrollment")
    session["temp_courses"] = []
    session["load_bearing"] = False

    return redirect(url_for(".user_courses"))