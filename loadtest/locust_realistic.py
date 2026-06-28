"""
Realistic production load profile for the CourseReg app.

Models a course-registration window: a surge as registration opens, a sustained
plateau of steady activity, then a taper as it winds down -- NOT a stress test.
Reuses the StudentUser behavior from locustfile.py.

Run it (app must be serving on the --host):
    locust -f locust_realistic.py --host http://127.0.0.1:5000 --headless

The LoadTestShape below drives the user count over time, so you do NOT pass
--users / --spawn-rate / --run-time here.
"""

from locust import LoadTestShape

# Pull in the user behavior (login + browse + register cycle). Locust auto-detects
# both the imported StudentUser and the RegistrationSurge shape in this file.
from locustfile import StudentUser  # noqa: F401


class RegistrationSurge(LoadTestShape):
    """A registration-day curve.

    Each stage: run until `duration` seconds (cumulative), holding `users`
    concurrent students, spawning at `spawn_rate`/s. Peak of 50 matches the
    50 seeded loadtest accounts, so virtual users map ~1:1 to real students.
    """

    stages = [
        {"duration": 60,  "users": 50, "spawn_rate": 2},   # 0-1m:  registration opens, students pile in
        {"duration": 300, "users": 50, "spawn_rate": 2},   # 1-5m:  steady registration activity (plateau)
        {"duration": 360, "users": 15, "spawn_rate": 2},   # 5-6m:  winding down
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
        return None  # past the last stage -> Locust stops the run
