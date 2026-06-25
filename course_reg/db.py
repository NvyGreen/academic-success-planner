import sqlite3
from typing import Optional
import flask

NO_WAITLIST = -1

def get_db() -> sqlite3.Connection:
    if 'db' not in flask.g:
        flask.g.db = sqlite3.connect(flask.current_app.config["SQLITE3_DB"])
        flask.g.db.execute("""PRAGMA foreign_keys = ON;""")
        # WAL lets reads proceed concurrently with a writer (only writer-vs-writer
        # serializes), which suits this read-heavy app. busy_timeout makes a
        # connection wait for a lock instead of failing immediately.
        flask.g.db.execute("""PRAGMA journal_mode = WAL;""")
        flask.g.db.execute("""PRAGMA busy_timeout = 5000;""")
        flask.g.db.row_factory = sqlite3.Row
    return flask.g.db


def tables_exist(db: sqlite3.Connection) -> bool:
    result = db.execute("""
        SELECT name FROM sqlite_master WHERE type='table' AND name='course'
    """).fetchone()
    return result is not None


def init_db(db: sqlite3.Connection):    
    db.execute("""
        CREATE TABLE IF NOT EXISTS "final" (
            "final_id" INTEGER,
            "start_datetime" TEXT,
            "end_datetime" TEXT,
            PRIMARY KEY("final_id")
        );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS "ge_category" (
            "category_id" INTEGER,
            "label" TEXT,
            "name" TEXT,
            PRIMARY KEY("category_id")
        );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS "instructor" (
            "instructor_id" INTEGER,
            "first_name" TEXT,
            "last_name" TEXT,
            PRIMARY KEY("instructor_id")
        );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS "school" (
            "school_id" INTEGER,
            "name" TEXT,
            PRIMARY KEY("school_id")
        );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS "student" (
            "student_id" INTEGER,
            "first_name" TEXT,
            "last_name" TEXT,
            "email" TEXT UNIQUE,
            "password" TEXT,
            "gpa" REAL,
            "schedule_preference" TEXT,
            PRIMARY KEY("student_id")
        );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS "department" (
            "department_id" INTEGER,
            "abbreviation" TEXT,
            "name" TEXT,
            "school_id" INTEGER,
            PRIMARY KEY("department_id"),
            FOREIGN KEY("school_id") REFERENCES "school"("school_id")
        );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS "metric" (
            "metric_id" INTEGER,
            "student_id" INTEGER,
            "workload_score" REAL,
            "burnout_score" REAL,
            "burnout_explanation" TEXT,
            "impact_score" REAL,
            "impact_explanation" TEXT,
            "recommendation" TEXT,
            "rec_type" TEXT,
            "bullet_summary" TEXT,
            "why_summary" TEXT,
            "table_summary" TEXT,
            "status" TEXT,
            "timestamp" TEXT,
            PRIMARY KEY("metric_id"),
            FOREIGN KEY("student_id") REFERENCES "student"("student_id")
        );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS "activity" (
            "activity_id" INTEGER,
            "student_id" INTEGER,
            "timestamp" TEXT,
            "type" TEXT,
            "description" TEXT,
            "details" TEXT,
            "workload_change" REAL,
            "burnout_change" REAL,
            "impact_change" REAL,
            "total_impact" TEXT,
            "version" INTEGER,
            PRIMARY KEY("activity_id"),
            FOREIGN KEY("student_id") REFERENCES "student"("student_id")
        );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS "course" (
            "course_id" INTEGER,
            "course_name" TEXT,
            "course_number" TEXT,
            "difficulty_score" INTEGER NOT NULL,
            "estimated_hours_per_week" REAL NOT NULL DEFAULT -1,
            "course_code" INTEGER UNIQUE,
            "credits" INTEGER,
            "category_id" INTEGER,
            "department_id" INTEGER,
            "course_level" TEXT,
            "type" TEXT,
            "days" INTEGER,
            "start_time" TEXT,
            "end_time" TEXT,
            "is_online" INTEGER,
            "final_id" INTEGER,
            "cancelled" INTEGER,
            "num_enrolled" INTEGER,
            "capacity" INTEGER,
            "waitlist" INTEGER,
            "building_code" TEXT,
            "room" TEXT,
            PRIMARY KEY("course_id"),
            FOREIGN KEY("category_id") REFERENCES "ge_category"("category_id"),
            FOREIGN KEY("department_id") REFERENCES "department"("department_id"),
            FOREIGN KEY("final_id") REFERENCES "final"("final_id")
        );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS "prerequisite" (
            "id" INTEGER,
            "course_id" INTEGER,
            "prereq_id" INTEGER,
            PRIMARY KEY("id"),
            FOREIGN KEY("course_id") REFERENCES "course"("course_id"),
            FOREIGN KEY("prereq_id") REFERENCES "course"("course_id")
        );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS "corequisite" (
            "id" INTEGER,
            "course_id" INTEGER,
            "coreq_id" INTEGER,
            PRIMARY KEY("id"),
            FOREIGN KEY("course_id") REFERENCES "course"("course_id"),
            FOREIGN KEY("coreq_id") REFERENCES "course"("course_id")
        );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS "course_instructor" (
            "id" INTEGER,
            "course_id" INTEGER,
            "instructor_id" INTEGER,
            PRIMARY KEY("id"),
            FOREIGN KEY("course_id") REFERENCES "course"("course_id"),
            FOREIGN KEY("instructor_id") REFERENCES "instructor"("instructor_id")
        );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS "enrollment" (
            "enrollment_id" INTEGER,
            "student_id" INTEGER,
            "course_id" INTEGER,
            PRIMARY KEY("enrollment_id"),
            FOREIGN KEY("course_id") REFERENCES "course"("course_id"),
            FOREIGN KEY("student_id") REFERENCES "student"("student_id")
        );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS "prev_enrollment" (
            "enrollment_id" INTEGER,
            "student_id" INTEGER,
            "course_id" INTEGER,
            PRIMARY KEY("enrollment_id"),
            FOREIGN KEY("course_id") REFERENCES "course"("course_id"),
            FOREIGN KEY("student_id") REFERENCES "student"("student_id")
        );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS "student_waitlist" (
            "waitlist_id" INTEGER,
            "student_id" INTEGER,
            "course_id" INTEGER,
            "position" INTEGER,
            PRIMARY KEY("waitlist_id"),
            FOREIGN KEY("course_id") REFERENCES "course"("course_id"),
            FOREIGN KEY("student_id") REFERENCES "student"("student_id")
        );
    """)

    # Prevent duplicate enrollments (a student in the same course twice), which
    # would desync course.num_enrolled under concurrent registration.
    db.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS "idx_enrollment_student_course"
        ON "enrollment" ("student_id", "course_id");
    """)

    # Analytics reads metric history per student ordered by time; this index turns
    # those full table scans into fast range scans as the table grows.
    db.execute("""
        CREATE INDEX IF NOT EXISTS "idx_metric_student_timestamp"
        ON "metric" ("student_id", "timestamp");
    """)

    db.commit()


def seed_db(db: sqlite3.Connection, seed_email: str, seed_pwd: str):
    data = [
        (None, None),
        ("2024-12-08T10:30:00.000Z", "2024-12-08T12:30:00.000Z"),
        ("2024-12-10T10:30:00.000Z", "2024-12-10T12:30:00.000Z"),
        ("2024-12-12T08:00:00.000Z", "2024-12-12T10:00:00.000Z"),
        ("2024-12-12T16:00:00.000Z", "2024-12-12T18:00:00.000Z"),
        ("2024-12-09T13:30:00.000Z", "2024-12-09T15:30:00.000Z"),
        ("2024-12-07T13:30:00.000Z", "2024-12-07T15:30:00.000Z"),
        ("2024-12-10T13:30:00.000Z", "2024-12-10T15:30:00.000Z")
    ]

    db.executemany("""
        INSERT INTO "final" ("start_datetime", "end_datetime")
        VALUES (?, ?);
    """, data)


    data = [
        ("0", "No GE Category"),
        ("Ia", "Lower Division Writing"),
        ("Ib", "Upper Division Writing"),
        ("II", "Science and Technology"),
        ("III", "Social and Behavioral Sciences"),
        ("IV", "Arts and Humanities"),
        ("Va", "Quantitative Literacy"),
        ("Vb", "Formal Reasoning"),
        ("VI", "Language Other Than English"),
        ("VII", "Multicultural Studies"),
        ("VIII", "International/Global Issues")
    ]

    db.executemany("""
        INSERT INTO "ge_category" ("label", "name")
        VALUES (?, ?);
    """, data)


    data = [
        ("Candice", "Yacono"),
        ("Michael", "Green"),
        ("Shannon", "Alfaro"),
        ("Alex", "Thornton"),
        ("Andromache", "Karanika"),
        ("Irene", "Gassko"),
        ("Joel", "Veenstra"),
        ("Brian", "Sato"),
        ("Sarah", "Pressman"),
        ("Jianan", "Zhu"),
        ("Lillian", "Jones"),
        ("Raymond", "Klefstad"),
        ("Iris", "Morell"),
        ("Gaelle", "Sehi"),
        ("Charles", "Smith")
    ]

    db.executemany("""
        INSERT INTO "instructor" ("first_name", "last_name")
        VALUES (?, ?);
    """, data)


    data = [
        ("Unaffiliated",),
        ("School of Humanities",),
        ("School of Physical Sciences",),
        ("Donald Bren School of Information and Computer Sciences",),
        ("Joe C. Wen School of Population and Public Health",),
        ("School of Social Sciences",)
    ]

    db.executemany("""
        INSERT INTO "school" ("name")
        VALUES (?);
    """, data)

    
    db.execute("""
        INSERT INTO "student" ("first_name", "last_name", "email", "password", "gpa", "schedule_preference")
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("John", "Doe", seed_email, seed_pwd, 3.5, "balanced"))


    data = [
        ("UNI STU", "University Studies", 1),
        ("WRITING", "Writing", 2),
        ("CHEM", "Chemistry", 3),
        ("I&C SCI", "Information and Computer Sciences", 4),
        ("POL SCI", "Political Science", 6),
        ("PUBHLTH", "Public Health", 5),
        ("CLASSIC", "Classics", 2),
        ("MATH", "Mathematics", 3),
        ("SPANISH", "Spanish", 2),
        ("COM LIT", "Comparative Literature", 2)
    ]

    db.executemany("""
        INSERT INTO "department" ("abbreviation", "name", "school_id")
        VALUES (?, ?, ?)
    """, data)


    db.execute("""
        CREATE TRIGGER IF NOT EXISTS sync_estimated_hours
        AFTER INSERT ON course
        BEGIN
            UPDATE course
            SET estimated_hours_per_week = NEW.credits * 1.5
            WHERE course_id = NEW.course_id;
        END;
    """)

    db.execute("""
        CREATE TRIGGER IF NOT EXISTS sync_estimated_hours_on_update
        AFTER UPDATE OF credits ON course
        BEGIN
            UPDATE course
            SET estimated_hours_per_week = NEW.credits * 1.5
            WHERE course_id = NEW.course_id;
        END;
    """)

    # (course_name, course_number, difficulty_score, course_code, credits, category_id, , department_id, course_level, type, days, start_time, end_time, is_online, final_id, cancelled, num_enrolled, capacity, waitlist, building_code, room)
    data = [
        ("Critical Reading and Rhetoric", "50", 2, 33201, 4, 2, 2, "lower", "Sem", "MWF", "2024-09-30T11:00:00.000Z", "2024-09-30T11:50:00.000Z", 0, 1, 0, 23, 23, 0, "HH", "230"),
        ("Argument and Research", "60", 2, 33314, 4, 2, 2, "lower", "Sem", "TuTh", "2024-09-26T12:30:00.000Z", "2024-09-26T13:50:00.000Z", 0, 1, 0, 17, 23, 0, "PSCB", "220"),
        ("General Chemistry", "1A", 3, 40000, 4, 4, 3, "lower", "Lec", "TuTh", "2024-09-26T09:30:00.000Z", "2024-09-26T10:50:00.000Z", 0, 2, 0, 225, 400, 0, "PSLH", "100"),
        ("General Chemistry", "1A", 3, 40001, 0, 1, 3, "lower", "Dis", "W", "2024-10-02T16:00:00.000Z", "2024-10-02T16:50:00.000Z", 0, 1, 0, 24, 40, 0, "HICF", "100K"),
        ("Introduction to Programming", "31", 2, 36040, 4, 4, 4, "lower", "Lec", "TuTh", "2024-09-26T11:00:00.000Z", "2024-09-26T12:30:00.000Z", 0, 3, 0, 87, 212, 0, "ALP", "2300"),
        ("Introduction to Programming", "31", 2, 36051, 0, 1, 4, "lower", "Lab", "MWF", "2024-09-27T08:00:00.000Z", "2024-09-27T09:20:00.000Z", 0, 1, 0, 42, 42, 0, "ICS", "183"),
        ("Programming with Software Libraries", "32", 3, 36080, 4, 4, 4, "lower", "Lec", "TuTh", "2024-09-26T09:30:00.000Z", "2024-09-26T10:50:00.000Z", 0, 4, 0, 43, 150, 0, "PCB", "1100"),
        ("Programming with Software Libraries", "32", 3, 36081, 0, 1, 4, "lower", "Lab", "MWF", "2024-09-27T12:30:00.000Z", "2024-09-27T13:50:00.000Z", 0, 1, 0, 16, 37, 0, "ICS", "192"),
        ("Python Programming and Libraries (Accelerated)", "H32", 2, 36100, 4, 4, 4, "lower", "Lec", "TuTh", "2024-09-26T17:00:00.000Z", "2024-09-26T18:20:00.000Z", 0, 5, 0, 259, 325, 0, "BS3", "1200"),
        ("Python Programming and Libraries (Accelerated)", "H32", 2, 36101, 0, 1, 4, "lower", "Lab", "MWF", "2024-09-27T17:00:00.000Z", "2024-09-27T18:20:00.000Z", 0, 1, 0, 46, 46, 0, "ICS", "364A"),
        ("Classical Mythology: The Heroes", "45B", 2, 22230, 4, 6, 7, "lower", "Lec", None, None, None, 1, 1, 0, 118, 210, 0, None, None),
        ("Boolean Logic and Discrete Structures", "6B", 2, 35920, 4, 8, 4, "lower", "Lec", "MWF", "2024-09-30T12:00:00.000Z", "2024-09-30T12:50:00.000Z", 0, 6, 0, 214, 325, 0, "HSLH", "100A"),
        ("Boolean Logic and Discrete Structures", "6B", 2, 35931, 0, 1, 4, "lower", "Dis", "MW", "2024-09-30T15:00:00.000Z", "2024-09-30T15:50:00.000Z", 0, 1, 0, 206, 325, 0, "SSLH", "100"),
        ("New Students Seminar", "90", 1, 36240, 1, 1, 4, "lower", "Lec", "Th", "2024-09-26T15:30:00.000Z", "2024-09-26T16:50:00.000Z", 0, 1, 0, 6, 50, 0, "HG", "1800"),
        ("AI for Human Good", "3", 1, 87413, 1, 1, 1, "lower", "Sem", "Tu", "2024-10-01T09:00:00.000Z", "2024-10-01T09:50:00.000Z", 0, 1, 0, 8, 15, 0, "CAC", "3100B"),
        ("Directed Studies in Undergraduate Education", "196", 1, 87760, 1, 1, 1, "upper", "Res", None, None, None, 1, 1, 0, 516, 950, NO_WAITLIST, None, None),
        ("Foundations for Success", "87", 1, 87610, 1, 1, 1, "lower", "Sem", None, None, None, 1, 1, 0, 49, 120, NO_WAITLIST, None, None),
        ("Single-Variable Calculus I", "2A", 3, 44020, 4, 8, 8, "lower", "Lec", "MWF", "2024-09-30T16:00:00.000Z", "2024-09-30T16:50:00.000Z", 0, 7, 0, 94, 195, 0, "PSLH", "100"),
        ("Single-Variable Calculus I", "2A", 3, 44021, 0, 1, 8, "lower", "Dis", "TuTh", "2024-09-26T12:00:00.000Z", "2024-09-26T12:50:00.000Z", 0, 1, 0, 21, 49, 0, "DBH", "1300"),
        ("Fundamentals of Spanish", "1A", 2, 31300, 4, 1, 9, "lower", "Lec", "TuWTh", "2024-09-26T08:00:00.000Z", "2024-09-26T08:50:00.000Z", 0, 8, 0, 18, 23, 0, "HH", "108"),
        ("Invitation to Computing", "20", 1, 36350, 1, 1, 4, "lower", "Sem", None, None, None, 1, 1, 0, 14, 50, 0, None, None),
        ("Love", "10", 2, 22720, 4, 11, 10, "lower", "Lec", None, None, None, 1, 1, 0, 19, 35, 0, None, None),
        ("Introduction to Public Health", "1", 2, 81010, 4, 5, 6, "lower", "Lec", None, None, None, 1, 1, 0, 95, 100, 0, None, None),
        ("Introduction to Law", "71A", 2, 67110, 4, 5, 5, "lower", "Lec", None, None, None, 1, 1, 0, 36, 40, 0, None, None)
    ]

    db.executemany("""
        INSERT INTO "course" ("course_name", "course_number", "difficulty_score", "course_code", "credits", "category_id", "department_id", "course_level", "type", "days", "start_time", "end_time", "is_online", "final_id", "cancelled", "num_enrolled", "capacity", "waitlist", "building_code", "room")
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, data)


    data = [
        (2, 1),
        (3, 18),
        (7, 5),
    ]

    db.executemany("""
        INSERT INTO "prerequisite" ("course_id", "prereq_id")
        VALUES (?, ?);
    """, data)


    data = [
        (3, 4),
        (4, 3),
        (5, 6),
        (6, 5),
        (7, 8),
        (8, 7),
        (9, 10),
        (10, 9),
        (12, 13),
        (13, 12),
        (18, 19),
        (19, 18)
    ]

    db.executemany("""
        INSERT INTO "corequisite" ("course_id", "coreq_id")
        VALUES (?, ?);
    """, data)


    data = [
        (1, 1),
        (2, 1),
        (3, 2),
        (4, 2),
        (5, 3),
        (6, 3),
        (7, 3),
        (8, 3),
        (9, 4),
        (10, 4),
        (11, 5),
        (12, 6),
        (13, 6),
        (14, 2),
        (15, 7),
        (16, 8),
        (17, 9),
        (18, 10),
        (19, 10),
        (20, 11),
        (21, 12),
        (22, 13),
        (23, 14),
        (24, 15)
    ]

    db.executemany("""
        INSERT INTO "course_instructor" ("course_id", "instructor_id")
        VALUES (?, ?);
    """, data)


    data = [
        (1, 1),
        (1, 3),
        (1, 4),
        (1, 5),
        (1, 6),
        (1, 7),
        (1, 8),
        (1, 11),
        (1, 17),
        (1, 18),
        (1, 19),
        (1, 20),
        (1, 21)
    ]

    db.executemany("""
        INSERT INTO "prev_enrollment" ("student_id", "course_id")
        VALUES (?, ?);
    """, data)




def close_db(exception: Optional[BaseException]):
    db = flask.g.pop('db', None)
    if db is not None:
        if exception is not None:
            db.rollback()
        else:
            db.commit()
        db.close()