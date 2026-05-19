from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SelectField,
    IntegerField,
    SubmitField
)
from wtforms.validators import (
    InputRequired,
    Email,
    Optional
)

GEN_CAT_BLANK = "1"
DEPT_BLANK = "0"

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[InputRequired(), Email()], render_kw={"placeholder": "Email"})
    password = PasswordField("Password", validators=[InputRequired()], render_kw={"placeholder": "Password"})
    submit = SubmitField("Log in")


class FilterForm(FlaskForm):
    gen_cat = SelectField("General Education Category", validators=[Optional()])

    department = SelectField("Department", validators=[Optional()])

    course_num = StringField("Course Number/Range", validators=[Optional()], render_kw={"placeholder": "ex: 45B, 31-33"})
    course_code = IntegerField("Course Code", validators=[Optional()])

    course_level = SelectField("Course Level", validators=[Optional()], choices=[
        ("all", " "),
        ("lower", "Lower Division Only"),
        ("upper", "Upper Division Only"),
        ("gradprof", "Graduate/Professional Only")
    ])

    instructor = StringField("Instructor", validators=[Optional()], render_kw={"placeholder": "ex: Smith"})
    submit = SubmitField("See Courses")


    def validate(self, extra_validators = None):
        if not super().validate(extra_validators):
            return False
        
        if (self.gen_cat.data == GEN_CAT_BLANK) and (self.department.data == DEPT_BLANK) and not self.course_code.data and not self.instructor.data:
            self.gen_cat.errors.append("Please refine your search with a department, course code, or instructor.")
            return False
        
        return True


class AdvancedFilterForm(FilterForm):
    modality = SelectField("Modality", validators=[Optional()], choices=[
        ("nomode", " "),
        ("inperson", "In-person"),
        ("online", "Online")
    ])
    days = StringField("Days", validators=[Optional()], render_kw={"placeholder": "ex: Tu; M,W,F"})
    
    starts_after = SelectField("Starts After", validators=[Optional()], choices=[
        ("nopref", " "),
        ("01:00", "1:00am"),
        ("02:00", "2:00am"),
        ("03:00", "3:00am"),
        ("04:00", "4:00am"),
        ("05:00", "5:00am"),
        ("06:00", "6:00am"),
        ("07:00", "7:00am"),
        ("08:00", "8:00am"),
        ("09:00", "9:00am"),
        ("10:00", "10:00am"),
        ("11:00", "11:00am"),
        ("12:00", "12:00pm"),
        ("13:00", "1:00pm"),
        ("14:00", "2:00pm"),
        ("15:00", "3:00pm"),
        ("16:00", "4:00pm"),
        ("17:00", "5:00pm"),
        ("18:00", "6:00pm"),
        ("19:00", "7:00pm"),
        ("20:00", "8:00pm"),
        ("21:00", "9:00pm"),
        ("22:00", "10:00pm"),
        ("23:00", "11:00pm")
    ])

    ends_before = SelectField("Ends Before", validators=[Optional()], choices=[
        ("nopref", " "),
        ("02:00", "2:00am"),
        ("03:00", "3:00am"),
        ("04:00", "4:00am"),
        ("05:00", "5:00am"),
        ("06:00", "6:00am"),
        ("07:00", "7:00am"),
        ("08:00", "8:00am"),
        ("09:00", "9:00am"),
        ("10:00", "10:00am"),
        ("11:00", "11:00am"),
        ("12:00", "12:00pm"),
        ("13:00", "1:00pm"),
        ("14:00", "2:00pm"),
        ("15:00", "3:00pm"),
        ("16:00", "4:00pm"),
        ("17:00", "5:00pm"),
        ("18:00", "6:00pm"),
        ("19:00", "7:00pm"),
        ("20:00", "8:00pm"),
        ("21:00", "9:00pm"),
        ("22:00", "10:00pm"),
        ("23:00", "11:00pm")
    ])

    course_full_option = SelectField("Show Courses at Capacity", validators=[Optional()], choices=[
        ("nopref", " "),
        ("open_or_waitlist", "Include waitlisted courses"),
        ("open_only", "Don't show full courses"),
        ("full_only", "Only full/waitlisted courses"),
        ("over_only", "Only over-enrolled courses")
    ])

    cancel_option = SelectField("Cancelled/Unavailable Courses", validators=[Optional()], choices=[
        ("excl", "Exclude cancelled courses"),
        ("incl", "Include cancelled courses"),
        ("only_cancel", "Only show cancelled courses")
    ])

    building_code = StringField("Building Code", validators=[Optional()])
    room_no = StringField("Room #", validators=[Optional()])

    credits = IntegerField("Credits", validators=[Optional()])

    def validate(self, extra_validators=None):
        if super().validate(extra_validators):
            if self.room_no.data and not self.building_code.data:
                self.building_code.errors.append("Please add a building code to go with the room number.")
                return False
            return True
        return False