# Aqua Tests Analytics

This project is a Flask application for analyzing test results.

## Setup

1. Clone the repository.
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment: `source venv/bin/activate` (on macOS/Linux) or `venv\Scripts\activate` (on Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Create a `.env` file by copying `.env.example` and update the environment variables as needed.
6. Initialize the database: `flask db init`, `flask db migrate -m "initial migration"`, `flask db upgrade`
7. Run the application: `flask run`

## TODO

- Implement models for test results, suites, runs, etc.
- Create routes for uploading and viewing test data.
- Develop services for processing and analyzing test data.
- Add visualizations for test analytics.
