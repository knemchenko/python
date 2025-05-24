import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_caching import Cache # Import Cache
from config import Config

db = SQLAlchemy()
migrate = Migrate()
cache = Cache() # Instantiate Cache

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)

    # Ensure UPLOAD_FOLDER root directory exists
    upload_folder_root = app.config.get('UPLOAD_FOLDER')
    if upload_folder_root and not os.path.exists(upload_folder_root):
        os.makedirs(upload_folder_root, exist_ok=True)

    # Register blueprints here
    from app.routes.main import main_bp
    app.register_blueprint(main_bp)

    from app.routes.admin import admin_bp # Import admin blueprint
    app.register_blueprint(admin_bp)     # Register admin blueprint

    # Configure Caching
    if app.config.get('FLASK_DEBUG'):
        cache_type = 'NullCache'
    else:
        cache_type = 'SimpleCache' # In a real app, use 'RedisCache', 'MemcachedCache', etc.
    
    cache_default_timeout = app.config.get('CACHE_DEFAULT_TIMEOUT', 300)

    cache.init_app(app, config={
        'CACHE_TYPE': cache_type,
        'CACHE_DEFAULT_TIMEOUT': cache_default_timeout
    })

    return app
