"""
Locust load test for the CourseRegProject Flask app.

Start the app first (it's threaded by default, so it can handle concurrent
requests and surface SQLite write contention):
    flask run

Then run Locust against it:
    locust -f locustfile.py --host http://127.0.0.1:5000

Open http://localhost:8089 to drive the swarm, or run headless:
    locust -f locustfile.py --host http://127.0.0.1:5000 \
        --users 50 --spawn-rate 5 --run-time 2m --headless

Each virtual user logs in as one of the seeded loadtest accounts
(loadtest1@uci.edu .. loadtest50@uci.edu, created by seed_students.py).
Override the shared password with LOCUST_PASSWORD if you reseeded with one.
"""

import os
import re
import random

from locust import HttpUser, task, between

# How many seeded accounts exist (seed_students.py --count). Keep in sync.
NUM_ACCOUNTS = int(os.environ.get("LOCUST_NUM_ACCOUNTS", "50"))
PASSWORD = os.environ.get("LOCUST_PASSWORD", "loadtest")

# Coreq-free, prereq-free course codes that ACTUALLY EXIST in sample_courses.db --
# registration succeeds (a real DB write) instead of bouncing on a missing course
# or unmet requisite. Verified against the live DB; regenerate if course data
# changes with:
#   SELECT course_code FROM course
#   WHERE course_id NOT IN (SELECT course_id FROM prerequisite)
#     AND course_id NOT IN (SELECT course_id FROM corequisite)
#     AND credits > 0 AND (cancelled = 0 OR cancelled IS NULL);
SAFE_COURSE_CODES = [22320, 31310, 33201, 67170]

# Matches the Flask-WTF hidden CSRF input in any rendered form.
_CSRF_RE = re.compile(r'name="csrf_token"[^>]*value="([^"]+)"')


def _csrf(html):
    """Pull the csrf_token out of a rendered page, or None if absent."""
    m = _CSRF_RE.search(html or "")
    return m.group(1) if m else None


class StudentUser(HttpUser):
    # Think-time between tasks: 1-4s, like a real student clicking around.
    wait_time = between(1, 4)

    def on_start(self):
        """Log in once when the virtual user spawns, as a distinct seeded
        account. Flask-WTF stores one CSRF token per session, so we keep it
        for all later POSTs."""
        self.csrf = None
        n = random.randint(1, NUM_ACCOUNTS)
        email = f"loadtest{n}@uci.edu"

        resp = self.client.get("/login")
        token = _csrf(resp.text)
        if not token:
            return  # already logged in or page changed

        with self.client.post(
            "/login",
            data={
                "csrf_token": token,
                "email": email,
                "password": PASSWORD,
                "submit": "Log in",
            },
            allow_redirects=True,
            catch_response=True,
            name="/login [POST]",
        ) as r:
            # A successful login redirects to /courses; a failed one re-renders
            # /login with a flash message.
            if "Login credentials not correct" in r.text:
                r.failure("Login failed -- run seed_students.py / check LOCUST_PASSWORD")
            else:
                self.csrf = token

    # ---- Read-heavy browsing: the bulk of realistic traffic ----------------

    @task(5)
    def view_courses(self):
        self.client.get("/courses")

    @task(2)
    def view_finals(self):
        self.client.get("/finals")

    @task(2)
    def view_quarter(self):
        self.client.get("/quarter")

    @task(2)
    def view_waitlists(self):
        self.client.get("/waitlists")

    @task(2)
    def view_analytics(self):
        self.client.get("/analytics")
        self.client.get("/analytics/history")

    # ---- Full register cycle: the write path that contends on SQLite -------

    @task(3)
    def register_cycle(self):
        if not self.csrf:
            return
        code = random.choice(SAFE_COURSE_CODES)

        # Filter by exact code so it lands in session["filter_courses"]
        # (add_course iterates that list) and shows in listings.
        self.client.get("/filter-courses")
        self.client.post(
            "/filter-courses",
            data={
                "csrf_token": self.csrf,
                "gen_cat": "1",        # blank sentinel
                "department": "0",     # blank sentinel
                "course_num": "",
                "course_code": str(code),
                "course_level": "all",
                "instructor": "",
                "submit": "See Courses",
            },
            allow_redirects=True,
            name="/filter-courses [POST]",
        )
        self.client.get("/listings")

        # Stage the course in the session cart (no DB write yet).
        self.client.post(
            f"/add-course/{code}",
            data={"csrf_token": self.csrf, "current_page": "/listings"},
            allow_redirects=True,
            name="/add-course/[code]",
        )

        # COMMIT: INSERT enrollment + UPDATE course.num_enrolled (contended
        # write), and mark metrics dirty.
        self.client.get("/confirm-schedule", name="/confirm-schedule")

        # Navigating flushes the dirty metric -> INSERT metric (another write).
        self.client.get("/courses")

        # DROP: the code is now in user_courses, so this DELETEs enrollment +
        # UPDATEs course (write), keeping the test repeatable.
        self.client.post(
            f"/drop-course/{code}",
            data={"csrf_token": self.csrf, "current_page": "/courses"},
            allow_redirects=True,
            name="/drop-course/[code]",
        )
        self.client.get("/courses")  # flush the second dirty metric
