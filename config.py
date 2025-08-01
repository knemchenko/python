import os

# Get the base directory of the project
basedir = os.path.abspath(os.path.dirname(__file__))

# Path to the database file
DATABASE = os.path.join(basedir, 'app', 'database.db')

# Path to the uploads folder
UPLOADS_FOLDER = os.path.join(basedir, 'uploads')

# Allowed extensions for file uploads
ALLOWED_EXTENSIONS = {'zip'}

# Cache configuration
CACHE_TYPE = 'simple'
CACHE_DEFAULT_TIMEOUT = 300

# Secret key for session management (e.g., for flash messages)
SECRET_KEY = 'a_very_secret_key'
