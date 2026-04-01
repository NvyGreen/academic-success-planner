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
from course_reg.forms import LoginForm, FilterForm, AdvancedFilterForm
from course_reg.models import Filters, AdvancedFilters
import course_reg.filter_methods
import course_reg.schedule_methods
import course_reg.register_methods
from passlib.hash import pbkdf2_sha256
import functools
from datetime import datetime, timezone


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


def check_window(route):
    @functools.wraps(route)
    def route_wrapper(*args, **kwargs):
        if session["start_window"] > datetime.now(timezone.utc) or session["end_window"] < datetime.now(timezone.utc):
            standard_start = datetime.strptime("07:00", "%H:%M").time()
            standard_end = datetime.strptime("19:00", "%H:%M").time()
            test_now = datetime.strptime("01:00", "%H:%M").time()

            if standard_start <= test_now and standard_end >= test_now:
                return redirect(url_for(".user_courses"))
            # return redirect(url_for(".user_courses"))

        return route(*args, **kwargs)
    
    return route_wrapper


@pages.route("/")
@login_required
def index():
    course_reg.register_methods.enroll_from_waitlist()
    session["user_courses"] = course_reg.schedule_methods.get_registered_courses(session["user_id"])
    session["unreged_courses"] = []
    session["user_waitlist"] = course_reg.schedule_methods.get_waitlist(session["user_id"])
    session["temp_courses"] = []
    session["load_bearing"] = False
    session["cancel"] = False
    session["start_window"], session["end_window"] = course_reg.register_methods.get_enrollment_window(session["user_id"])
    
    return redirect(url_for(".user_courses"))


@pages.route("/courses")
@login_required
def user_courses():
    courses = course_reg.schedule_methods.get_short_courses(session["user_courses"])
    calendar = course_reg.schedule_methods.create_calendar(courses)

    if len(session["unreged_courses"]) > 0:
        unreged = ", ".join(str(code) for code in session["unreged_courses"])
        flash(
            f"Could not register the following courses — check that all requirements are satisfied: {unreged}",
            "error"
        )
        session["unreged_courses"] = []

    return render_template(
        "index.html",
        title="Course Registration - My Courses",
        courses=courses,
        calendar=calendar
    )


@pages.route("/finals")
@login_required
def user_finals():
    courses = course_reg.schedule_methods.get_short_courses_final(session["user_courses"])
    calendar = course_reg.schedule_methods.create_final_calendar(courses)

    return render_template(
        "index_finals.html",
        title="Course Registration - My Finals",
        courses=courses,
        calendar=calendar
    )


@pages.route("/quarter")
@login_required
def user_quarter():
    courses = course_reg.schedule_methods.get_short_courses(session["user_courses"])

    return render_template(
        "index_quarter.html",
        title="Course Registration - Current Quarter",
        courses=courses
    )


@pages.route("/waitlists")
@login_required
def user_waitlists():
    courses = course_reg.filter_methods.get_user_waitlist(session["user_id"], session["user_waitlist"])

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
        user_cursor = current_app.db.execute(
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
@check_window
def drop_courses():
    courses = course_reg.filter_methods.get_courses_from_codes(session["user_courses"])

    return render_template(
        "drop_courses.html",
        title="Course Registration - Drop Courses",
        courses=courses
    )


@pages.route("/filter-courses", methods=["GET", "POST"])
@login_required
def filter_courses():
    if session["cancel"] == True:
        session["temp_courses"] = []
        session["cancel"] = False
    
    form = FilterForm()
    form.gen_cat.choices = course_reg.filter_methods.prep_ge()
    form.department.choices = course_reg.filter_methods.prep_departments()
    

    if form.validate_on_submit():
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
    form.department.choices = course_reg.filter_methods.prep_departments()

    if form.validate_on_submit():
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
        return redirect(url_for(".course_listing"))

    return render_template(
        "filter_courses_advanced.html",
        title="Course Registration - Filter Courses - Advanced",
        form=form
    )


@pages.route("/listings")
@login_required
def course_listing():    
    return render_template(
        "course_listing.html",
        title="Course Registration - Listings",
        criteria=session["filter_criteria"],
        courses=session["filter_courses"]
    )


@pages.route("/preview/courses")
@login_required
def preview_courses():
    courses = course_reg.schedule_methods.get_short_courses(session["temp_courses"] + session["user_courses"])
    calendar = course_reg.schedule_methods.create_calendar(courses)

    return render_template(
        "preview_courses.html",
        title="Course Registration - Preview Courses",
        courses=courses,
        calendar=calendar
    )


@pages.route("/preview/finals")
@login_required
def preview_finals():
    courses = course_reg.schedule_methods.get_short_courses_final(session["temp_courses"] + session["user_courses"])
    calendar = course_reg.schedule_methods.create_final_calendar(courses)

    return render_template(
        "preview_finals.html",
        title="Course Registration - Preview Finals",
        courses=courses,
        calendar=calendar
    )


@pages.route("/preview/quarter")
@login_required
def preview_quarter():
    courses = course_reg.schedule_methods.get_short_courses(session["temp_courses"] + session["user_courses"])

    return render_template(
        "preview_quarter.html",
        title="Course Registration - View Quarter",
        courses=courses
    )



@pages.get("/add-course/<int:code>")
@login_required
@check_window
def add_course(code):
    if code not in session["temp_courses"]:
        session["load_bearing"] = True
        session["temp_courses"].append(code)

        for course in session["filter_courses"]:
            if course[1] == code:
                course[0] = "Registered"
                break
    
    return redirect(request.args.get("current_page"))


@pages.get("/drop-course/<int:code>")
@login_required
@check_window
def drop_course(code):
    if code in session["temp_courses"]:
        session["load_bearing"] = False
        session["temp_courses"].remove(code)

        for course in session["filter_courses"]:
            if course[1] == code:
                course[0] = "Neither"
                break
    
    if code in session["user_courses"]:
        session["load_bearing"] = False
        session["user_courses"].remove(code)

        for course in session["filter_courses"]:
            if course[1] == code:
                course[0] = "Neither"
                break

        course_reg.register_methods.drop_course(session["user_id"], code)

    return redirect(request.args.get("current_page"))


@pages.get("/wait-course/<int:code>")
@login_required
@check_window
def wait_course(code):
    if code not in session["user_waitlist"]:
        course_reg.register_methods.waitlist_course(session["user_id"], code)
        session["load_bearing"] = True
        session["user_waitlist"].append(code)

        for course in session["filter_courses"]:
            if course[1] == code:
                course[0] = "Waitlisted"
                break

    return redirect(request.args.get("current_page"))


@pages.get("/drop-wait/<int:code>")
@login_required
@check_window
def drop_wait(code):
    if code in session["user_waitlist"]:
        course_reg.register_methods.drop_waitlist(session["user_id"], code)
        session["load_bearing"] = False
        session["user_waitlist"].remove(code)

        for course in session["filter_courses"]:
            if course[1] == code:
                course[0] = "Neither"
                break
    
    return redirect(request.args.get("current_page"))


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
@check_window
def confirm_schedule():
    session["unreged_courses"] = course_reg.register_methods.register_courses(session["user_id"], session["temp_courses"])
    session["user_courses"] = course_reg.schedule_methods.get_registered_courses(session["user_id"])
    session["temp_courses"] = []
    session["load_bearing"] = False

    return redirect(url_for(".user_courses"))