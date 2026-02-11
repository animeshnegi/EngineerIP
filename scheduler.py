# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import atexit
import logging
from jobs import register_app  # Only register, not run here

class CampaignScheduler:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CampaignScheduler, cls).__new__(cls)
            cls._instance.scheduler = None
            cls._instance.logger = logging.getLogger('scheduler')
        return cls._instance

    def init_app(self, app):
        if self.scheduler and self.scheduler.running:
            return

        # ✅ Register app to use in job
        register_app(app)

        jobstores = {
            'default': SQLAlchemyJobStore(url=app.config['SQLALCHEMY_DATABASE_URI'])
        }

        self.scheduler = BackgroundScheduler(jobstores=jobstores)

        # ✅ Must be a string reference — no closures
        self.scheduler.add_job(
            func='jobs:run_scheduled_campaigns',
            trigger='interval',
            minutes=2,
            id='campaign_sender',
            replace_existing=True
        )

        # Example of a job that scrapes a page every 10 minutes
        # Uncomment if you want to add new jobs
        # self.scheduler.add_job(
        #     func='jobs:scrape_example_page',  #   change the function accordingly
        #     trigger='interval',
        #     minutes=10,
        #     id='page_scraper',
        #     replace_existing=True
        # )





        try:
            self.scheduler.start()
            self.logger.info("Scheduler initialized successfully")
        except Exception as e:
            self.logger.error(f"Scheduler failed to start: {str(e)}")
            raise

        @atexit.register
        def shutdown():
            if self.scheduler and self.scheduler.running:
                try:
                    self.scheduler.shutdown(wait=False)
                    self.logger.info("Scheduler stopped gracefully")
                except Exception as e:
                    self.logger.error(f"Scheduler shutdown error: {str(e)}")

scheduler = CampaignScheduler()
