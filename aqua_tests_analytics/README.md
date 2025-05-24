# Automated Test Analytics Server (Aqua Tests)

This project provides an on-premise web service to collect, aggregate, and visualize automated test results. It accepts ZIP uploads containing `total.json` summaries and related HTML artifacts, computes KPIs (pass-rate, duration, flakiness, etc.), and presents interactive dashboards per panel and version.

## Current Features (as of this version)

*   **Test Result Upload:** `/upload` endpoint accepts ZIP archives containing `total.json` and HTML reports.
    *   Supports `panel_type` and `version` query parameters.
    *   Validates `total.json` against a predefined schema.
    *   Handles idempotency: re-uploading for the same panel & version replaces old data.
    *   Stores uploaded ZIP files.
*   **Data Processing:**
    *   Parses `total.json` to extract test runs.
    *   Excludes "CreateEnvironment" and "RemoveEnvironment" tests.
    *   Stores individual test run data (name, class, status, duration, start time).
*   **Data Aggregation:**
    *   Calculates aggregated metrics per test case per version (`test_agg` table).
    *   Metrics include: last status, pass/fail/ignore/skip counts, flips (status changes within version runs), T1 (transition rate), T2 (fail-after-pass), T4 (flaky if any flips in version or recent history), T5 (weighted instability), average & median duration.
*   **Database:** Uses PostgreSQL (managed via Docker Compose for local dev, or native for prod).
    *   SQLAlchemy models for panels, versions, test runs, and aggregated test data.
    *   Database migrations handled by Flask-Migrate.
*   **API Endpoints:**
    *   `POST /upload?panel_type=<str>&version=<str>`: For uploading test data.
    *   `GET /healthz`: Health check.
    *   `GET /`: Displays a list of available panels.
    *   `GET /<panel_name>/metrics`: Displays metrics for the latest version of a panel.
    *   `GET /<panel_name>/<version_str>`: Displays detailed test results for a specific version.
    *   `GET /<panel_name>/<version_str>/<path:test_id_str>`: Displays history for a specific test case.
    *   `GET /admin/`: Admin dashboard for viewing panels and versions (HTTP Basic Auth).
*   **Caching:** In-memory caching for panel metrics endpoint (disabled in debug mode).
*   **Basic UI:**
    *   Lists available panels on the homepage.
    *   Panel metrics page with KPIs and status chart.
    *   Version detail page with filterable hierarchical test list.
    *   Test history page with duration trend chart and paginated runs.
    *   Admin dashboard.
    *   Supports system light/dark mode preference.
*   **Scripts:**
    *   `scripts/purge_old_zips.sh`: For deleting old ZIP archives based on retention policy.
    *   `scripts/db_backup.sh`: For backing up the PostgreSQL database with retention.

## Project Structure

*   `/app`: Main Flask application folder.
    *   `/models`: SQLAlchemy database models.
    *   `/routes`: Flask Blueprints and route definitions.
    *   `/services`: Business logic (data processing, etc.).
    *   `/static`: Static assets (CSS, JS, images - if any).
    *   `/templates`: Jinja2 HTML templates.
    *   `__init__.py`: Flask app factory.
*   `/migrations`: Flask-Migrate database migration scripts.
*   `/data/uploads`: Default folder for storing uploaded ZIP files (configurable via `.env`).
*   `/pgdata`: Default folder for PostgreSQL persistent data (used by Docker in local dev).
*   `/deploy`: Contains deployment configuration files (systemd, nginx).
*   `/scripts`: Contains operational scripts (backups, cleanup).
*   `config.py`: Application configuration.
*   `requirements.txt`: Python dependencies.
*   `run.py`: Script to run the Flask development server.
*   `wsgi.py`: WSGI entry point for Gunicorn.
*   `docker-compose.yml`: Defines the PostgreSQL service for local development.
*   `.env.example`: Example environment variables.
*   `README.md`: This file.

## Deployment Steps

These steps assume a bare-metal Ubuntu 20.04 LTS server.

1.  **Clone Repository:**
    ```bash
    sudo mkdir -p /opt/aqua-tests
    sudo chown your_user:your_group /opt/aqua-tests # Grant your user perms to clone
    git clone <repository_url> /opt/aqua-tests
    cd /opt/aqua-tests
    ```

2.  **Set Up PostgreSQL:**
    - Start PostgreSQL using Docker: `sudo docker compose up -d postgres`
    - Or ensure a native PostgreSQL instance is running and accessible. Configure connection details in `.env`.

3.  **Create Application User & Group (Recommended):**
    ```bash
    sudo groupadd aquauser || echo "Group aquauser already exists"
    sudo useradd -r -g aquauser -d /opt/aqua-tests -s /sbin/nologin aquauser || echo "User aquauser already exists"
    # Adjust home dir and shell as needed.
    # Ensure this user can read/write to UPLOAD_FOLDER and relevant parts of the app if needed.
    sudo chown -R aquauser:aquauser /opt/aqua-tests # Ownership for app files
    # If UPLOAD_FOLDER or log dirs are outside /opt/aqua-tests, set permissions:
    # Example: sudo mkdir -p /var/log/aqua-tests /var/uploads/aqua-zips
    # Example: sudo chown -R aquauser:aquauser /var/log/aqua-tests /var/uploads/aqua-zips
    ```

4.  **Set Up Python Environment & Dependencies:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt # gunicorn is now included
    deactivate
    ```
    *Ensure `venv` is owned by `aquauser` or readable by it if created by another user. If created as root, `sudo chown -R aquauser:aquauser venv`.*
    *Alternatively, create venv as `aquauser`: `sudo -u aquauser python3 -m venv /opt/aqua-tests/venv`*
    *Then install requirements: `sudo -u aquauser /opt/aqua-tests/venv/bin/pip install -r /opt/aqua-tests/requirements.txt`*


5.  **Configure Application:**
    - Copy `.env.example` to `.env`: `cp .env.example .env`
    - **Edit `.env`:**
        - Set `FLASK_ENV=production`.
        - Configure `DATABASE_URL` to point to your PostgreSQL instance (e.g., `postgresql://aqua:password@localhost:5432/aqua_tests_db`).
        - Set `ADMIN_USERNAME` and `ADMIN_PASSWORD`.
        - Configure `UPLOAD_FOLDER` (e.g., `/var/uploads/aqua-zips`) and `ZIP_RETENTION_DAYS`.
        - Configure `SECRET_KEY` with a strong random value.
    - Ensure `.env` is readable by `aquauser` but not world-readable: `sudo chown aquauser:aquauser .env && sudo chmod 600 .env`.

6.  **Run Database Migrations:**
    ```bash
    # As the application user (ensure correct FLASK_APP context if run.py is not used directly)
    # or ensure .env is sourced by the user running this.
    # It's often easiest to run as the app user:
    sudo -u aquauser /opt/aqua-tests/venv/bin/flask --app wsgi:app db upgrade
    # Or if FLASK_APP is defined in .env and EnvironmentFile in systemd sources it:
    # /opt/aqua-tests/venv/bin/flask db upgrade
    ```

7.  **Set Up Systemd Service:**
    - Create log directory: `sudo mkdir -p /var/log/aqua-tests && sudo chown aquauser:aquauser /var/log/aqua-tests`
    - Copy the service file:
      ```bash
      sudo cp deploy/aqua-tests.service /etc/systemd/system/aqua-tests.service
      ```
    - Edit `/etc/systemd/system/aqua-tests.service` if necessary to match your paths and user.
    - Reload systemd, enable and start the service:
      ```bash
      sudo systemctl daemon-reload
      sudo systemctl enable aqua-tests.service
      sudo systemctl start aqua-tests.service
      sudo systemctl status aqua-tests.service # Check status
      ```

8.  **Set Up Nginx Reverse Proxy:**
    - Copy the sample vhost configuration:
      ```bash
      sudo cp deploy/nginx_vhost.conf /etc/nginx/sites-available/aqua-tests
      ```
    - Edit `/etc/nginx/sites-available/aqua-tests`:
        - Change `server_name` to your server's domain or IP address.
        - If using HTTPS, configure SSL certificate paths.
        - Ensure `proxy_pass` matches Gunicorn's bind address (socket or host:port).
        - Ensure `client_max_body_size` is appropriate (e.g., matches `MAX_CONTENT_LENGTH` if set in Flask).
        - Update `alias` for `/static` if `/opt/aqua-tests` is not your project root.
    - Create a symbolic link to `sites-enabled`:
      ```bash
      sudo ln -s /etc/nginx/sites-available/aqua-tests /etc/nginx/sites-enabled/aqua-tests
      ```
    - Test Nginx configuration and restart:
      ```bash
      sudo nginx -t
      sudo systemctl restart nginx
      ```

9.  **Set Up Cron Jobs:**
    - Edit crontab for a user (e.g., `aquauser` or `root`): `sudo -u aquauser crontab -e` (for `aquauser`) or `sudo crontab -e` (for root).
    - Add entries for `db_backup.sh` and `purge_old_zips.sh`. Example:
      ```cron
      # Run daily at 01:30 UTC for DB backup
      30 1 * * * /opt/aqua-tests/scripts/db_backup.sh >> /var/log/aqua-tests/db_backup.log 2>&1

      # Run daily at 03:00 local time for ZIP purge
      0 3 * * * /opt/aqua-tests/scripts/purge_old_zips.sh >> /var/log/aqua-tests/purge_zips.log 2>&1
      ```
    - Ensure the scripts are executable, paths are correct, and the executing user has necessary permissions.
    - Consider using `flock` for cron job mutual exclusion if needed.

## Future Scope (from original specification)

*   Prometheus `/metrics` endpoint.
*   Email alerts.
*   JIRA API integration.
*   Advanced flakiness metric calculations (e.g., full T4 across versions - current T4 is based on recent history).
*   More detailed UI for F-1 (KPI donut/sparkline for panel list).
*   UI enhancements for existing pages.

## Contributing
(Placeholder for contribution guidelines if this were an open project)
