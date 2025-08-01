import os
from flask import Flask, current_app
from flask_caching import Cache

# App factory
import datetime

def create_app():
    app = Flask(__name__)

    @app.template_filter('datetimeformat')
    def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
        return datetime.datetime.fromtimestamp(int(value)).strftime(format)

    @app.template_filter('relpath')
    def relpath_filter(path):
        base = current_app.config['UPLOADS_FOLDER']
        return os.path.relpath(path, base).replace('\\', '/')

    # Load config
    app.config.from_pyfile('../config.py')

    # Init extensions
    cache = Cache(app)

    # Create uploads folder
    if not os.path.exists(app.config['UPLOADS_FOLDER']):
        os.makedirs(app.config['UPLOADS_FOLDER'])

    # Register blueprints
    from . import routes
    app.register_blueprint(routes.bp)

    # Init DB
    from . import database
    database.init_app(app)

    return app
