# app.py
from flask import Flask
from models import db
import json
from scheduler import scheduler
import os



def create_app():
    app = Flask(__name__)
    
    # Load configuration
    with open('static/config/config.json') as c:
        param = json.load(c)["param"]

    app.config.update({
        "SQLALCHEMY_DATABASE_URI": param['local_uri'],
        "UPLOAD_FOLDER": param['upload'],
        "CSV_FILE_PATH": param['camp_file'],
        "API_KEY": param['API_KEY'],
        "BASE_URL": param['BASE_URL'],
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "RECAPTCHA_SECRET_KEY": param['RECAPTCHA_SECRET_KEY'],
        "SCHEDULER_API_ENABLED": False
    })


    app.secret_key = param.get('secret_key', 'fallback-key-for-dev')



    # Initialize extensions
    db.init_app(app)
    
    # Register blueprints
    from routes import main_bp
    from campaigns import campaign_bp

    from docket.routes import docket_bp
    app.register_blueprint(docket_bp, url_prefix='/docket')


     # Create all tables (including docket tables) if they don't exist
    with app.app_context():
        try:
            # Import docket models to ensure they are registered
            from docket.models import SharedFile, FileRecord, UploadedFile, User, Configuration, Country, USPTOApiLog, FeeSchedule, AutomationLog, NotificationLog, Document, MaintenanceFee, OfficeAction, StatusHistory, Deadline, Case, Inventor, Attorney, NotificationType, DeadlineType, CaseStatus, CaseType, Project, ProjectMessage, ProjectFile, ProjectNotification
            db.create_all()  # This will create all tables that don't exist
            print("All tables checked/created successfully")
        except Exception as e:
            print(f"Error creating tables: {str(e)}")

    app.register_blueprint(main_bp)
    app.register_blueprint(campaign_bp)




    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            with app.app_context():
                try:
                    scheduler.init_app(app)
                    print("Scheduler initialized successfully (child process)")
                except Exception as e:
                    app.logger.error(f"Failed to initialize scheduler: {str(e)}")
    
    return app




app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=8000)



# THE BELOW CODE IS USED IN THE LIVE SERVER BUT COMMENTED OUT FOR LOCAL DEVELOPMENT


# from flask import Flask
# from models import db
# import json
# import os


# def create_app():
#     app = Flask(__name__)
    
#     # Get absolute path to config file
#     base_dir = os.path.dirname(os.path.abspath(__file__))
#     config_path = os.path.join(base_dir, 'static', 'config', 'config.json')
    
#     # Load configuration
#     with open(config_path) as c:
#         param = json.load(c)["param"]

#     # Get absolute paths for upload folder and CSV file
#     upload_folder = os.path.join(base_dir, param['upload'])
#     csv_file_path = os.path.join(base_dir, param['camp_file'])
    
#     app.config.update({
#         "SQLALCHEMY_DATABASE_URI": param['local_uri'],
#         "UPLOAD_FOLDER": upload_folder,
#         "CSV_FILE_PATH": csv_file_path,
#         "API_KEY": param['API_KEY'],
#         "BASE_URL": param['BASE_URL'],
#         "SQLALCHEMY_TRACK_MODIFICATIONS": False,
#         "RECAPTCHA_SECRET_KEY": param['RECAPTCHA_SECRET_KEY'],
#         "SCHEDULER_API_ENABLED": False,
#         "DEBUG": False,
#         "TESTING": False
#     })

#     app.secret_key = param.get('secret_key', 'fallback-key-for-dev')

#     # Initialize extensions
#     db.init_app(app)
    
#     # Register blueprints
#     from routes import main_bp
#     from campaigns import campaign_bp
    
#     app.register_blueprint(main_bp)
#     app.register_blueprint(campaign_bp)

#     return app

# app = create_app()