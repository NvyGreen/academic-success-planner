"""
Unit tests for scheduler.py — the nightly waitlist-promotion job wiring.

create_app() skips start_scheduler in this environment (FLASK_DEBUG=1 -> app.debug
True), so it's exercised directly here. The background loop is driven exactly once
via a fake Thread plus a sleep that raises, so no real daemon thread is left running
and the global `schedule` registry is cleaned up afterward.
"""

import os
import shutil
import types
import pytest

from tests import TEST_SECRET_KEY


@pytest.fixture
def app(tmp_path, monkeypatch):
    src = os.environ["EVAL_SEED_DB"]
    test_db = tmp_path / "scheduler.db"
    shutil.copy(src, test_db)
    monkeypatch.setenv("SQLITE3_DB", str(test_db))
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET_KEY)
    monkeypatch.setenv("SEED_EMAIL", "sch@uci.edu")
    monkeypatch.setenv("SEED_PWD", "unused")
    from course_reg import create_app
    application = create_app()
    application.config["TESTING"] = True
    return application


# --- _run_promote_waitlist ----------------------------------------------------

def test_run_promote_waitlist_success(app):
    from course_reg import scheduler
    # Empty waitlist -> promote_waitlist is a no-op, but the wrapper still pushes an
    # app context, runs it, and logs success without raising.
    scheduler._run_promote_waitlist(app)


def test_run_promote_waitlist_swallows_errors(app, monkeypatch):
    from course_reg import scheduler, register_methods

    def boom():
        raise RuntimeError("kaboom")

    monkeypatch.setattr(register_methods, "promote_waitlist", boom)
    # The wrapper must catch and log the failure, not propagate it.
    scheduler._run_promote_waitlist(app)


# --- start_scheduler ----------------------------------------------------------

class _StopLoop(Exception):
    pass


def _raise_stop(*_args):
    raise _StopLoop()


def test_start_scheduler_registers_job_and_runs_loop(app, monkeypatch):
    import schedule
    from course_reg import scheduler

    schedule.clear()
    captured = {}

    class FakeThread:
        def __init__(self, target=None, daemon=None, name=None):
            captured.update(target=target, daemon=daemon, name=name)

        def start(self):
            captured["started"] = True

    # Patch only scheduler's references, leaving the real threading/time alone.
    monkeypatch.setattr(scheduler, "threading", types.SimpleNamespace(Thread=FakeThread))

    scheduler.start_scheduler(app)

    # A daily job is registered, and a daemon thread is created + started.
    assert len(schedule.jobs) == 1
    assert captured["daemon"] is True
    assert captured["name"] == "waitlist-scheduler"
    assert captured["started"] is True
    assert callable(captured["target"])

    # Drive the loop body once: run_pending (job not due) then sleep -> _StopLoop.
    monkeypatch.setattr(scheduler, "time", types.SimpleNamespace(sleep=_raise_stop))
    with pytest.raises(_StopLoop):
        captured["target"]()      # the _loop closure

    schedule.clear()
