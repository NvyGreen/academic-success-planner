import time
import threading
import schedule
from course_reg import register_methods


def _run_promote_waitlist(app):
    # Background threads have no request/app context — push one so
    # get_db()/current_app work, and so close_db commits + closes on exit.
    with app.app_context():
        try:
            register_methods.promote_waitlist()
            app.logger.info("promote_waitlist: nightly run completed")
        except Exception:
            app.logger.exception("promote_waitlist: nightly run failed")


def start_scheduler(app):
    # Midnight local time, every day.
    schedule.every().day.at("00:00").do(_run_promote_waitlist, app)

    def _loop():
        while True:
            schedule.run_pending()
            time.sleep(30)  # how often we check; fine for a daily job

    # daemon=True => thread won't keep the process alive on shutdown.
    threading.Thread(target=_loop, daemon=True, name="waitlist-scheduler").start()