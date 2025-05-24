import os
import zipfile
import json
import jsonschema
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify, current_app, render_template # Import render_template
from app import db, cache # Import cache
from app.models import Panel, Version, TestRun, TestAgg # TestRun and TestAgg might not be directly used here anymore
from app.services.data_processing import process_test_data, aggregate_test_data

main_bp = Blueprint('main', __name__)


@main_bp.route('/', methods=['GET'])
def index():
    """
    Index page, lists all available panels.
    """
    panels = Panel.query.order_by(Panel.panel_type).all()
    return render_template('index.html', panels=panels)

TOTAL_JSON_SCHEMA = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["statistic", "modules", "app_type"],
  "properties": {
    "app_type": {"type": "string"},
    "statistic": {
      "type": "object",
      "required": ["Started", "Duration", "Failures", "Warnings", "Ignored"],
      "properties": {
        "Started":   {"type": "number"}, # Should be string in ISO format e.g. "2024-03-10T10:00:00Z"
        "Duration":  {"type": "number"},
        "Failures":  {"type": "integer"},
        "Warnings":  {"type": "integer"},
        "Ignored":   {"type": "integer"}
      }
    },
    "modules": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "tests", "statistic"],
        "properties": {
          "name": {"type": "string"},
          "tests": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["name", "statistic"],
              "properties": {
                "name": {"type": "string"},
                # Reference to the main statistic object definition
                "statistic": {"$ref": "#/properties/statistic"}
              }
            }
          },
          # Reference to the main statistic object definition
          "statistic": {"$ref": "#/properties/statistic"}
        }
      }
    }
  }
}


@main_bp.route('/upload', methods=['POST'])
def upload_file():
    if request.method != 'POST':
        return jsonify({"code": 405, "error": "Method not allowed"}), 405

    panel_type = request.args.get('panel_type')
    version_str = request.args.get('version')

    if not panel_type or not version_str:
        return jsonify({"code": 400, "error": "Missing 'panel_type' or 'version' query parameters"}), 400

    if 'file' not in request.files:
        return jsonify({"code": 400, "error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"code": 400, "error": "No selected file"}), 400

    if not file.filename.endswith('.zip'):
        return jsonify({"code": 400, "error": "File must be a .zip archive"}), 400

    filename = secure_filename(file.filename)
    
    # Ensure UPLOAD_FOLDER exists
    upload_folder_root = current_app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder_root):
        os.makedirs(upload_folder_root, exist_ok=True)

    temp_zip_path = os.path.join(upload_folder_root, f"temp_{filename}")

    try:
        file.save(temp_zip_path)

        # Validate ZIP and total.json
        try:
            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                if 'total.json' not in zip_ref.namelist():
                    return jsonify({"code": 400, "error": "'total.json' not found in the zip archive"}), 400
                with zip_ref.open('total.json') as total_file:
                    total_data = json.load(total_file)
        except zipfile.BadZipFile:
            return jsonify({"code": 400, "error": "Invalid or corrupted zip file"}), 400
        except json.JSONDecodeError:
             return jsonify({"code": 400, "error": "Failed to decode 'total.json'. Invalid JSON."}), 400


        try:
            jsonschema.validate(instance=total_data, schema=TOTAL_JSON_SCHEMA)
        except jsonschema.exceptions.ValidationError as e:
            return jsonify({"code": 400, "error": f"Schema validation failed: {e.message}"}), 400

        # Idempotency: Check for existing version and clean up
        existing_version = Version.query.join(Panel).filter(
            Panel.panel_type == panel_type,
            Version.version == version_str
        ).first()

        if existing_version:
            # Delete associated TestAgg and TestRun records
            TestAgg.query.filter_by(version_id=existing_version.id).delete()
            TestRun.query.filter_by(version_id=existing_version.id).delete()
            
            # Delete the Version record
            db.session.delete(existing_version)
            
            # Delete old ZIP file and directory
            old_zip_dir = os.path.join(upload_folder_root, panel_type, version_str)
            old_zip_path = os.path.join(old_zip_dir, filename) # Assuming filename was the same
            if os.path.exists(old_zip_path):
                os.remove(old_zip_path)
            if os.path.exists(old_zip_dir) and not os.listdir(old_zip_dir): # Check if dir is empty
                os.rmdir(old_zip_dir)
            
            db.session.commit()


        # Database Operations: Create new Panel/Version
        panel = Panel.query.filter_by(panel_type=panel_type).first()
        if not panel:
            panel = Panel(panel_type=panel_type)
            db.session.add(panel)
            # Commit here to get panel.id if it's new
            db.session.commit() 

        new_version = Version(panel_id=panel.id, version=version_str)
        db.session.add(new_version)
        db.session.commit()

        # Final ZIP Storage
        final_zip_dir = os.path.join(upload_folder_root, panel_type, version_str)
        os.makedirs(final_zip_dir, exist_ok=True)
        final_zip_path = os.path.join(final_zip_dir, filename)
        
        # Ensure no old temp file exists at final destination if names collide (unlikely with temp_ prefix)
        if os.path.exists(final_zip_path):
             os.remove(final_zip_path) # Should not happen if old files are cleaned up properly
        os.rename(temp_zip_path, final_zip_path) # temp_zip_path is now final_zip_path

        # Data processing steps
        try:
            current_app.logger.info(f"Starting data processing for version_id: {new_version.id}")
            process_test_data(new_version.id, total_data)
            current_app.logger.info(f"Finished process_test_data for version_id: {new_version.id}. Starting aggregation.")
            aggregate_test_data(new_version.id)
            current_app.logger.info(f"Finished aggregate_test_data for version_id: {new_version.id}.")
            db.session.commit() # Commit changes from processing and aggregation
            return jsonify({"message": "Upload successful, data processed."}), 202
        except Exception as data_processing_error:
            db.session.rollback()
            current_app.logger.error(f"Data processing failed for version_id {new_version.id if 'new_version' in locals() and new_version else 'unknown'}: {data_processing_error}")
            # Clean up: version, panel (if new and no other versions), and filesystem data
            # This part can be complex. For now, we delete the version and log.
            # A more robust system might mark the version as 'processing_failed'
            if 'new_version' in locals() and new_version and new_version.id:
                try:
                    # Re-fetch to ensure session state is current if rollback occurred
                    version_to_delete = db.session.get(Version, new_version.id)
                    if version_to_delete:
                        TestAgg.query.filter_by(version_id=version_to_delete.id).delete()
                        TestRun.query.filter_by(version_id=version_to_delete.id).delete()
                        db.session.delete(version_to_delete)
                        # Potentially delete Panel if it was just created and has no other versions
                        # panel_to_check = db.session.get(Panel, panel.id) # panel from outer scope
                        # if panel_to_check and not panel_to_check.versions:
                        #    db.session.delete(panel_to_check)
                        db.session.commit()
                        current_app.logger.info(f"Rolled back database entries for version_id {new_version.id}")
                except Exception as cleanup_error:
                    db.session.rollback()
                    current_app.logger.error(f"Error during cleanup after data processing failure: {cleanup_error}")
            
            # Clean up the saved ZIP file
            if os.path.exists(final_zip_path):
                try:
                    os.remove(final_zip_path)
                    # Attempt to remove directory if empty
                    if os.path.exists(final_zip_dir) and not os.listdir(final_zip_dir):
                        os.rmdir(final_zip_dir)
                    current_app.logger.info(f"Cleaned up file {final_zip_path}")
                except OSError as file_cleanup_error:
                    current_app.logger.error(f"Error cleaning up file {final_zip_path}: {file_cleanup_error}")

            return jsonify({"code": 500, "error": "Data processing failed after upload. Upload has been rolled back."}), 500

    except Exception as e:
        db.session.rollback()
        # Clean up temp file if it still exists and wasn't moved to final_zip_path
        if 'temp_zip_path' in locals() and os.path.exists(temp_zip_path) and ('final_zip_path' not in locals() or temp_zip_path != final_zip_path):
             try:
                os.remove(temp_zip_path)
             except OSError as temp_file_error:
                current_app.logger.error(f"Error removing temp file {temp_zip_path} during main exception: {temp_file_error}")
        current_app.logger.error(f"Upload failed: {e}", exc_info=True)
        return jsonify({"code": 500, "error": "An internal server error occurred during upload."}), 500
    # No finally block needed here as temp file cleanup is handled in the main try-except for upload
    # and the processing try-except handles final_zip_path cleanup.


@main_bp.route('/healthz', methods=['GET'])
def health_check():
    """
    Health check endpoint.
    """
    return jsonify({"status": "healthy"}), 200


@main_bp.route('/<string:panel_name>/metrics', methods=['GET'])
@cache.cached() # Uses default timeout configured in app
def get_panel_metrics(panel_name: str):
    """
    Placeholder endpoint for panel-specific metrics.
    This endpoint's response will be cached.
    """
    # In a real scenario, you would fetch data from the database
    # based on panel_name and compute metrics.
    # For now, just a placeholder.
    current_app.logger.info(f"Cache miss or first request for /{(panel_name)}/metrics") # Log cache miss
    return jsonify({
        "panel_name": panel_name,
        "message": f"Metrics for panel {panel_name} - this response should be cached.",
        "data_source": "Simulated data generation"
    }), 200
