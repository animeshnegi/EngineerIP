import logging
import random
from flask import current_app

# this is the file Where the all the tasks are stored, like sending emails, generating random digits, etc.

_app = None

def register_app(app):
    global _app
    _app = app
    print("App registered in jobs.py")
    logging.getLogger().info("App registered in jobs.py")


def run_scheduled_campaigns():
    try:
        if _app is None:
            print("app is still None!")
            raise RuntimeError("Flask app not registered")

        print("Inside run_scheduled_campaigns() with app context")
        with _app.app_context():
            from routes import send_scheduled_campaigns
            send_scheduled_campaigns()
        return True
    except Exception as e:
        if _app:
            _app.logger.error(f"Campaign job failed: {str(e)}")
        else:
            logging.error(f"Campaign job failed: {str(e)}")
        return False



def generate_random_digits():
    with _app.app_context():
        digits = random.randint(1000, 9999)
        current_app.logger.info(f"Generated random digits: {digits}")