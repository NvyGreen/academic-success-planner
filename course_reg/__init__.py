import os
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
from course_reg.routes import pages
from course_reg import db as database
from course_reg.scheduler import start_scheduler


# Load the project-root .env explicitly so it's found regardless of the working
# directory the app is launched from (this file lives in course_reg/, .env is one up).
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
csrf = CSRFProtect()

def create_app():
    if os.environ.get("SECRET_KEY") is None or os.environ.get("SQLITE3_DB") is None or os.environ.get("SEED_EMAIL") is None or os.environ.get("SEED_PWD") is None:
        raise ValueError("Environment variables variables not configured")

    # Basic SECRET_KEY guardrail (not an entropy check): reject obviously-unsafe
    # keys so a placeholder can't reach production. A 32-char run of one character
    # still passes — this only catches the common mistakes. Runs before any DB work.
    secret_key = os.environ.get("SECRET_KEY")
    weak_secret_keys = {"development", "secret", "secret_key", "changeme", "password"}
    if len(secret_key) < 32 or secret_key.strip().lower() in weak_secret_keys:
        raise ValueError(
            'SECRET_KEY is too weak: use at least 32 characters and not a common '
            'placeholder. Generate one with: '
            'python -c "import secrets;print(secrets.token_hex(32))"'
        )

    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
    app.config["SQLITE3_DB"] = os.environ.get("SQLITE3_DB")
    csrf.init_app(app)

    app.teardown_appcontext(database.close_db)

    with app.app_context():
        db = database.get_db()
        already_exists = database.tables_exist(db)
        database.init_db(db)
        if not already_exists:
            database.seed_db(db, os.environ.get("SEED_EMAIL"), os.environ.get("SEED_PWD"))

    app.register_blueprint(pages)
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_scheduler(app)

    return app