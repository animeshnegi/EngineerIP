"""Application-wide APScheduler integration."""

from __future__ import annotations

import atexit
import logging
from threading import Lock

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from jobs import register_app


class CampaignScheduler:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.scheduler = None
                    cls._instance._shutdown_registered = False
                    cls._instance.logger = logging.getLogger("engineerip.scheduler")
        return cls._instance

    def _build_scheduler(self, app, persistent: bool) -> BackgroundScheduler:
        jobstores = {}
        if persistent:
            jobstores["default"] = SQLAlchemyJobStore(url=app.config["SQLALCHEMY_DATABASE_URI"])
        else:
            jobstores["default"] = MemoryJobStore()

        scheduler = BackgroundScheduler(
            jobstores=jobstores,
            timezone=app.config.get("TIMEZONE", "Asia/Kolkata"),
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 300,
            },
        )
        scheduler.add_job(
            "jobs:run_scheduled_campaigns",
            trigger="interval",
            minutes=max(1, int(app.config.get("CAMPAIGN_INTERVAL_MINUTES", 2))),
            id="campaign_sender",
            replace_existing=True,
        )
        return scheduler

    def init_app(self, app) -> None:
        """Start the scheduler once for this process.

        A persistent SQLAlchemy job store is attempted first.  If its database
        is unavailable, the website still starts with an in-memory job store;
        the next process restart will retry persistence.
        """

        register_app(app)
        if self.scheduler and self.scheduler.running:
            return

        persistent = bool(app.config.get("SCHEDULER_PERSISTENCE", True))
        try:
            self.scheduler = self._build_scheduler(app, persistent=persistent)
            self.scheduler.start()
        except Exception:
            if self.scheduler:
                try:
                    self.scheduler.shutdown(wait=False)
                except Exception:
                    pass
            self.logger.exception("Persistent scheduler start failed")
            self.scheduler = self._build_scheduler(app, persistent=False)
            self.scheduler.start()
            self.logger.warning("Scheduler started with in-memory jobs")

        if not self._shutdown_registered:
            atexit.register(self.shutdown)
            self._shutdown_registered = True

    def shutdown(self) -> None:
        if self.scheduler and self.scheduler.running:
            try:
                self.scheduler.shutdown(wait=False)
            except Exception:
                self.logger.exception("Scheduler shutdown failed")


scheduler = CampaignScheduler()
