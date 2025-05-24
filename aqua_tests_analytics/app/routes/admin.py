from functools import wraps
from flask import Blueprint, render_template, request, Response, current_app, jsonify
from sqlalchemy.orm import joinedload # Correct import for joinedload

from app import db # Assuming db is accessible from app package
from app.models import Panel, Version # Assuming models are in app.models

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# --- Basic Authentication ---
def check_auth(username, password):
    """Checks if a username / password combination is valid."""
    return username == current_app.config['ADMIN_USERNAME'] and \
           password == current_app.config['ADMIN_PASSWORD']

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def require_basic_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# --- Routes ---
@admin_bp.route('/')
@require_basic_auth
def index():
    """
    Admin index page. Lists panels and their versions.
    """
    panels_with_versions = db.session.query(Panel).options(joinedload(Panel.versions)).order_by(Panel.panel_type).all()
    return render_template('admin/index.html', panels_with_versions=panels_with_versions)
