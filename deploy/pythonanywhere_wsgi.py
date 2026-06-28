"""WSGI entry point for PythonAnywhere.

IMPORTANT: PythonAnywhere does NOT read this file from the repo. Copy its
contents into the WSGI configuration file linked on your Web tab
(Web -> "WSGI configuration file"), then edit the two placeholders:

  - USERNAME       -> your PythonAnywhere username
  - project_path   -> where you cloned the repo

It loads .env by an ABSOLUTE path, because PythonAnywhere's working directory at
WSGI load time is not the project root (a relative load would silently find
nothing). Then it builds the app via the package's application factory.
"""
import os
import sys

from dotenv import load_dotenv

project_path = "/home/USERNAME/academic-success-planner"
if project_path not in sys.path:
    sys.path.insert(0, project_path)

load_dotenv(os.path.join(project_path, ".env"))

from course_reg import create_app  # noqa: E402  (must follow sys.path / .env setup)

application = create_app()
