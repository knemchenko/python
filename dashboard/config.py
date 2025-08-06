import os

class Config:
    """Configuration for the Flask dashboard."""
    # General Config
    SECRET_KEY = os.environ.get('SECRET_KEY', 'a-very-secret-key')

    # Data and Application paths
    # Assuming the dashboard is run from the root of the project
    DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))

    # Trading Strategy Filters (from main config)
    MIN_ABS_RET = 0.5    # %
    MIN_SIGMA   = 0.5    # σ

    # Authentication
    # It's better to use environment variables for credentials
    AUTH_USER = os.getenv("DASH_USER", "admin")
    AUTH_PASS = os.getenv("DASH_PWD", "changeme")
