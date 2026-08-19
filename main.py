"""Application factory and development entry point for EngineerIP."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

from flask import Flask

from models import db
from scheduler import scheduler


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "static" / "config" / "config.json"


def _as_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _absolute_path(value: str | os.PathLike[str], default: Path) -> str:
    path = Path(value) if value else default
    if not path.is_absolute():
        path = BASE_DIR / path
    return str(path)


def _database_uri(config: Mapping[str, object]) -> str:
    """Return a SQLAlchemy URL using the configured environment or JSON file.

    Older deployments use ``mysql://``.  SQLAlchemy maps that URL to the
    mysqlclient driver (``MySQLdb``), which is not installed by this project.
    Use PyMySQL for a portable Python-only deployment instead.
    """

    uri = os.environ.get("DATABASE_URL") or str(config.get("local_uri", "sqlite:///engineerip.db"))
    if uri.startswith("mysql://"):
        uri = "mysql+pymysql://" + uri[len("mysql://") :]
    return uri


def _should_start_scheduler(app: Flask) -> bool:
    if _as_bool(os.environ.get("DISABLE_SCHEDULER")) or app.config.get("TESTING"):
        return False

    # Flask's reloader creates a parent and a child process.  Start the
    # scheduler only in the child when debug mode is enabled.
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return False
    return True


def _ensure_compatibility_schema() -> None:
    """Add columns introduced by the project/docket features to old installs.

    ``db.create_all`` creates missing tables but deliberately does not alter
    existing tables.  These small, idempotent additions keep existing client
    projects usable after an upgrade without replacing user data.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    additions = {
        'projects': {
            'completion_notes': 'TEXT',
            'completed_at': 'DATETIME',
        },
        'project_files': {
            'description': 'TEXT',
        },
        'file_records': {
            'case_id': 'INTEGER',
        },
    }
    statements = []
    for table, columns in additions.items():
        if not inspector.has_table(table):
            continue
        existing = {column['name'] for column in inspector.get_columns(table)}
        for column, sql_type in columns.items():
            if column not in existing:
                statements.append(f'ALTER TABLE {table} ADD COLUMN {column} {sql_type}')

    if statements:
        with db.engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))

    # New campaign sequence records are unique per email in the sequence,
    # not merely per campaign/contact.  MySQL can update the old constraint
    # in-place; fresh databases get the model constraint from create_all.
    if inspector.has_table('campaign_recipient') and db.engine.dialect.name == 'mysql':
        constraints = {item.get('name') for item in inspector.get_unique_constraints('campaign_recipient')}
        with db.engine.begin() as connection:
            if '_campaign_contact_uc' in constraints:
                connection.execute(text('ALTER TABLE campaign_recipient DROP INDEX `_campaign_contact_uc`'))
            if '_campaign_contact_email_uc' not in constraints:
                connection.execute(text(
                    'ALTER TABLE campaign_recipient ADD CONSTRAINT `_campaign_contact_email_uc` '
                    'UNIQUE (campaign_id, contact_id, email_index)'
                ))


def create_app(config_overrides: Mapping[str, object] | None = None) -> Flask:
    app = Flask(__name__)

    try:
        with CONFIG_PATH.open(encoding="utf-8") as config_file:
            file_config = json.load(config_file).get("param", {})
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        app.logger.warning("Could not load %s: %s", CONFIG_PATH, exc)
        file_config = {}

    upload_folder = _absolute_path(
        os.environ.get("UPLOAD_FOLDER") or file_config.get("upload", "static/upload"),
        BASE_DIR / "static" / "upload",
    )
    csv_file_path = _absolute_path(
        os.environ.get("CSV_FILE_PATH") or file_config.get("camp_file", "static/csv/test.csv"),
        BASE_DIR / "static" / "csv" / "test.csv",
    )

    debug_enabled = _as_bool(os.environ.get("FLASK_DEBUG"), False)
    app.config.update(
        {
            "DEBUG": debug_enabled,
            "TESTING": False,
            "SQLALCHEMY_DATABASE_URI": _database_uri(file_config),
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_pre_ping": True},
            "UPLOAD_FOLDER": upload_folder,
            "DOCKET_UPLOAD_FOLDER": _absolute_path(
                os.environ.get("DOCKET_UPLOAD_FOLDER") or "uploads",
                BASE_DIR / "uploads",
            ),
            "PROJECTS_DATA_FOLDER": _absolute_path(
                os.environ.get("PROJECTS_DATA_FOLDER") or "projects_data",
                BASE_DIR / "projects_data",
            ),
            "CSV_FILE_PATH": csv_file_path,
            "API_KEY": os.environ.get("ELASTIC_EMAIL_API_KEY", file_config.get("API_KEY", "")),
            "BASE_URL": os.environ.get(
                "ELASTIC_EMAIL_BASE_URL",
                file_config.get("BASE_URL", "https://api.elasticemail.com/v2/email/send"),
            ),
            "PUBLIC_BASE_URL": os.environ.get(
                "PUBLIC_BASE_URL", file_config.get("PUBLIC_BASE_URL", "https://www.engineerip.com")
            ).rstrip("/"),
            "TSDR_API_KEY": os.environ.get("USPTO_TSDR_API_KEY", file_config.get("TSDR_API_KEY", "")),
            "TSDR_SAVE_XML": _as_bool(
                os.environ.get("TSDR_SAVE_XML", file_config.get("TSDR_SAVE_XML", False))
            ),
            "TSDR_XML_FOLDER": _absolute_path(
                os.environ.get("TSDR_XML_FOLDER") or file_config.get("TSDR_XML_FOLDER", "uploads/tsdr_xml"),
                BASE_DIR / "uploads" / "tsdr_xml",
            ),
            "TSDR_MAX_REQUESTS_PER_MINUTE": int(
                os.environ.get("TSDR_MAX_REQUESTS_PER_MINUTE", 60)
            ),
            "TSDR_RATE_WINDOW_SECONDS": int(os.environ.get("TSDR_RATE_WINDOW_SECONDS", 60)),
            "TSDR_MAX_WORKERS": int(os.environ.get("TSDR_MAX_WORKERS", 10)),
            "TSDR_REQUEST_TIMEOUT": int(os.environ.get("TSDR_REQUEST_TIMEOUT", 15)),
            "TSDR_MAX_RETRIES": int(os.environ.get("TSDR_MAX_RETRIES", 3)),
            "TRADEMARK_OFFICE_ACTION_MONTHS": int(
                os.environ.get("TRADEMARK_OFFICE_ACTION_MONTHS", 3)
            ),
            "DOCKET_RECORD_DELAY_SECONDS": float(os.environ.get("DOCKET_RECORD_DELAY_SECONDS", 0)),
            "RECAPTCHA_SECRET_KEY": os.environ.get(
                "RECAPTCHA_SECRET_KEY", file_config.get("RECAPTCHA_SECRET_KEY", "")
            ),
            "SECRET_KEY": os.environ.get("SECRET_KEY", file_config.get("secret_key", "")),
            "MAX_CONTENT_LENGTH": int(os.environ.get("MAX_CONTENT_LENGTH", 50 * 1024 * 1024)),
            "CAMPAIGN_INTERVAL_MINUTES": int(os.environ.get("CAMPAIGN_INTERVAL_MINUTES", 2)),
            "CAMPAIGN_SEND_DELAY_SECONDS": float(os.environ.get("CAMPAIGN_SEND_DELAY_SECONDS", 0)),
            "DEADLINE_NOTIFICATION_INTERVAL_MINUTES": int(
                os.environ.get("DEADLINE_NOTIFICATION_INTERVAL_MINUTES", 60)
            ),
            "SCHEDULER_PERSISTENCE": _as_bool(os.environ.get("SCHEDULER_PERSISTENCE"), True),
            "TIMEZONE": os.environ.get("TIMEZONE", "Asia/Kolkata"),
            "SESSION_COOKIE_HTTPONLY": True,
            "SESSION_COOKIE_SAMESITE": "Lax",
        }
    )

    if config_overrides:
        app.config.update(config_overrides)

    app.secret_key = app.config.get("SECRET_KEY") or os.urandom(32)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["CSV_FILE_PATH"]).parent.mkdir(parents=True, exist_ok=True)

    db.init_app(app)

    # Import models before create_all so SQLAlchemy knows about every table.
    from docket import models as docket_models  # noqa: F401
    from docket.routes import docket_bp
    from routes import main_bp
    from campaigns import campaign_bp

    app.register_blueprint(docket_bp, url_prefix="/docket")
    app.register_blueprint(main_bp)
    app.register_blueprint(campaign_bp)

    with app.app_context():
        try:
            db.create_all()
            _ensure_compatibility_schema()
            app.logger.info("All database tables checked/created successfully")
        except Exception:
            # Keep the original behaviour of allowing the web process to boot
            # so health checks can report the database problem.  Individual
            # database-backed requests will still return a useful error.
            app.logger.exception("Database initialisation failed")

    if _should_start_scheduler(app):
        try:
            scheduler.init_app(app)
            app.logger.info("Campaign scheduler started")
        except Exception:
            # A scheduler outage should not take down the public website.
            app.logger.exception("Campaign scheduler could not be started")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 8000)),
        debug=app.config.get("DEBUG", False),
    )
