import os

class Config:
    """Configuration for the Flask dashboard."""
    # General Config
    SECRET_KEY = os.environ.get('SECRET_KEY', 'a-very-secret-key')

    # Data and Application paths
    # Construct path to the project root directory, then join with 'data'
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    DATA_DIR = os.path.join(PROJECT_ROOT, 'data')

    # Trading Strategy Filters (from main config)
    MIN_ABS_RET = 0.5    # %
    MIN_SIGMA   = 0.5    # σ

    # Authentication
    AUTH_USER = os.getenv("DASH_USER", "admin")
    AUTH_PASS = os.getenv("DASH_PWD", "changeme")
