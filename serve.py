"""
Production-style server for the CourseReg app using waitress.

Unlike `flask run`'s development server (single-process, drops connections under
concurrency), waitress is a real WSGI server with a worker thread pool that
handles many simultaneous clients without resetting connections. Use this to
load-test against something closer to production.

Usage (from project root, venv active):
    python serve.py
Then point Locust at http://127.0.0.1:8000:
    locust -f locust_realistic.py --host http://127.0.0.1:8000 --headless
"""

import os

from dotenv import load_dotenv
from waitress import serve

# Load app config (SECRET_KEY, SQLITE3_DB, ...) before importing the app factory,
# since waitress doesn't do Flask's .flaskenv/.env loading for us.
load_dotenv(os.path.join(os.path.dirname(__file__), "course_reg", ".env"))

from course_reg import create_app  # noqa: E402  (must follow load_dotenv)

if __name__ == "__main__":
    app = create_app()
    # threads = worker pool size. 8 comfortably serves the 50-user realistic
    # profile without the dev server's connection drops.
    serve(app, host="127.0.0.1", port=8000, threads=8)
