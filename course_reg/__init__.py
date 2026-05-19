import os
import sqlite3
import flask
from flask import Flask
from dotenv import load_dotenv
from course_reg.routes import pages
from course_reg.db import *


load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
    app.config["SQLITE3_DB"] = os.environ.get("SQLITE3_DB")

    app.teardown_appcontext(close_db)

    with app.app_context():
        db = get_db()
        already_exists = tables_exist(db)
        init_db(db)
        if not already_exists:
            seed_db(db, os.environ.get("SEED_EMAIL"), os.environ.get("SEED_PWD"))

    app.register_blueprint(pages)

    return app