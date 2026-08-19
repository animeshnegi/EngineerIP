"""Functions executed by APScheduler."""

from __future__ import annotations

import logging
import random
from threading import Lock

from flask import current_app


_app = None
_app_lock = Lock()


def register_app(app) -> None:
    global _app
    with _app_lock:
        _app = app
    logging.getLogger(__name__).info("Flask app registered for scheduled jobs")


def run_scheduled_campaigns() -> bool:
    """Run the campaign worker inside the registered Flask app context."""

    app = _app
    if app is None:
        logging.getLogger(__name__).error("Campaign job skipped: Flask app is not registered")
        return False

    try:
        with app.app_context():
            from routes import send_scheduled_campaigns

            result = send_scheduled_campaigns()
            return result is not False
    except Exception:
        app.logger.exception("Scheduled campaign job failed")
        return False


def run_docket_deadline_notifications() -> bool:
    """Run deadline reminders inside the registered Flask app context."""
    app = _app
    if app is None:
        logging.getLogger(__name__).error('Deadline job skipped: Flask app is not registered')
        return False
    try:
        with app.app_context():
            from docket.routes import send_due_date_notifications
            result = send_due_date_notifications()
            app.logger.info('Docket reminder run complete: %s', result)
            return True
    except Exception:
        app.logger.exception('Docket deadline notification job failed')
        return False


def generate_random_digits() -> int:
    """Small utility retained for legacy callers."""

    app = _app
    if app is None:
        raise RuntimeError("Flask app not registered")

    with app.app_context():
        digits = random.randint(1000, 9999)
        current_app.logger.info("Generated random digits: %s", digits)
        return digits
