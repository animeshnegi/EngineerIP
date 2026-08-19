# EngineerIP

EngineerIP is a Flask application for patent and trademark services, IP docketing, client projects, document sharing, and campaign automation.

## Local setup

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Set the database and application secrets in the environment rather than committing them to the repository:

```bash
export DATABASE_URL="mysql+pymysql://user:password@localhost/location"
export SECRET_KEY="replace-with-a-long-random-value"
export ELASTIC_EMAIL_API_KEY="replace-with-your-api-key"
export PUBLIC_BASE_URL="https://www.engineerip.com"
```

Run the development server:

```bash
python main.py
```

The server listens on `0.0.0.0:8000` by default. Set `DISABLE_SCHEDULER=1` for tests or one-off tooling. The campaign scheduler starts automatically in production and uses the configured database job store, falling back to in-memory scheduling if the database is temporarily unavailable.

## Main areas

- Public patent, trademark, drawing, consultant, article, and contact pages
- DocketTrack dashboard at `/docket/`
- Case CSV/XLS/XLSX uploads with background processing and Excel result downloads
- Client project collaboration, messages, files, and ZIP downloads
- Campaign datasets, templates, sequences, follow-ups, and unsubscribe handling

Existing deployments should back up the database before upgrading. The application adds compatibility columns for project completion metadata and project-file descriptions during startup; larger schema changes should still be applied through the deployment database migration process.
