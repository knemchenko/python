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
    Displays metrics for a specific panel, focusing on its latest version.
    """
    current_app.logger.info(f"Executing get_panel_metrics for panel: {panel_name}. Cache miss or first request.")
    panel = Panel.query.filter_by(panel_type=panel_name).first()

    if not panel:
        return render_template('404.html'), 404 # Or a specific "panel not found" template

    # Get the latest version for this panel (order by created_ts descending)
    latest_version = Version.query.filter_by(panel_id=panel.id)\
                                  .order_by(Version.created_ts.desc())\
                                  .first()

    status_counts = {'pass': 0, 'fail': 0, 'warning': 0, 'ignored': 0, 'skipped': 0}
    duration_data = []
    test_aggregates = []
    pass_rate = 0
    pass_rate_color = 'grey' # Default color

    if latest_version:
        test_aggregates = TestAgg.query.filter_by(version_id=latest_version.id).all()

        if test_aggregates:
            for agg in test_aggregates:
                # Ensure agg.last_status is not None and has a value attribute if it's an Enum object
                # If it's already a string from db.Enum, direct use is fine.
                # Based on model (TestStatus(enum.Enum)), it should be an enum object.
                if agg.last_status: # Check if not None
                    status_counts[agg.last_status.value] += 1 
                
                duration_data.append({
                    'test_id': agg.test_id,
                    'avg_duration': agg.avg_duration,
                    'median_duration': agg.median_duration
                })
            
            # Calculate pass rate (excluding ignored and skipped from the denominator)
            total_relevant_tests = sum(status_counts.values()) - status_counts['ignored'] - status_counts['skipped']
            if total_relevant_tests > 0:
                pass_rate = (status_counts['pass'] / total_relevant_tests) * 100
            else: # Avoid division by zero if only ignored/skipped or no tests
                pass_rate = 0 if sum(status_counts.values()) > 0 else 100 # 100% if no tests at all, 0% if only ignored/skipped

            # Determine pass rate color
            if pass_rate >= 95:
                pass_rate_color = 'green'
            elif pass_rate >= 85:
                pass_rate_color = 'yellow'
            else:
                pass_rate_color = 'red'

    return render_template('panel_metrics.html',
                           panel=panel,
                           latest_version=latest_version,
                           status_counts=status_counts, # Will be converted to JSON in template
                           duration_data=duration_data,
                           test_aggregates_count=len(test_aggregates),
                           pass_rate=pass_rate,
                           pass_rate_color=pass_rate_color)


@main_bp.route('/<string:panel_name>/<string:version_str>', methods=['GET'])
def version_detail_page(panel_name: str, version_str: str):
    """
    Displays details for a specific version of a panel, including all its test aggregates
    grouped by class_name.
    """
    panel = Panel.query.filter_by(panel_type=panel_name).first()
    if not panel:
        return render_template('404.html', message=f"Panel '{panel_name}' not found."), 404

    version = Version.query.filter_by(panel_id=panel.id, version=version_str).first()
    if not version:
        return render_template('404.html', message=f"Version '{version_str}' for panel '{panel_name}' not found."), 404

    test_aggregates = TestAgg.query.filter_by(version_id=version.id)\
                                   .order_by(TestAgg.class_name, TestAgg.test_id)\
                                   .all()
    
    grouped_tests = {}
    if test_aggregates:
        from itertools import groupby
        for class_name, group in groupby(test_aggregates, key=lambda x: x.class_name or "Unclassified"):
            grouped_tests[class_name] = list(group)

    return render_template('version_detail.html',
                           panel=panel,
                           version=version,
                           grouped_tests=grouped_tests,
                           total_tests=len(test_aggregates))


@main_bp.route('/<string:panel_name>/<string:version_str>/<path:test_id_str>', methods=['GET'])
def test_history_page(panel_name: str, version_str: str, test_id_str: str):
    """
    Displays the history of a specific test case within a given version of a panel,
    including a duration trend chart and paginated test runs.
    """
    panel = Panel.query.filter_by(panel_type=panel_name).first()
    if not panel:
        return render_template('404.html', message=f"Panel '{panel_name}' not found."), 404

    version = Version.query.filter_by(panel_id=panel.id, version=version_str).first()
    if not version:
        return render_template('404.html', message=f"Version '{version_str}' for panel '{panel_name}' not found."), 404

    page = request.args.get('page', 1, type=int)
    
    # Query for all runs for the chart data (ordered by time for trend)
    all_runs_for_test = TestRun.query.filter_by(version_id=version.id, test_id=test_id_str)\
                                     .order_by(TestRun.started_ts.asc())\
                                     .all()
    
    chart_data = []
    if all_runs_for_test:
        chart_data = [{'x': run.started_ts.strftime('%Y-%m-%d %H:%M:%S') if run.started_ts else f"Run_{i+1}", 
                       'y': float(run.duration_seconds) if run.duration_seconds is not None else 0}
                      for i, run in enumerate(all_runs_for_test)]

    # Query for paginated runs (ordered by time descending for display)
    # Note: Using a subquery or a more complex query might be needed if all_runs_for_test is very large
    # and we want to avoid loading it all into memory just for the chart.
    # For now, this is simpler.
    
    # Re-query for pagination, ordered descending for latest first in table
    paginated_runs_query = TestRun.query.filter_by(version_id=version.id, test_id=test_id_str)\
                                     .order_by(TestRun.started_ts.desc())
    
    pagination = paginated_runs_query.paginate(page=page, per_page=10, error_out=False)
    
    # test_id_str is used as test_id in the template for url_for
    return render_template('test_history.html',
                           panel=panel,
                           version=version,
                           test_id=test_id_str, 
                           pagination=pagination,
                           chart_data_json=json.dumps(chart_data)) # Pass chart data as JSON
