from flask import Blueprint

bp = Blueprint('main', __name__)

import os
import hashlib
import zipfile
import json
import time
from flask import request, jsonify, current_app
from werkzeug.utils import secure_filename
from .database import get_db

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

from flask import render_template
import pandas as pd

import plotly
import plotly.express as px
import shutil
from flask import flash, redirect, url_for, send_from_directory

@bp.route('/admin/delete_version', methods=['POST'])
def delete_version():
    version_id = request.form.get('version_id')
    if not version_id:
        flash('Version ID is required.', 'danger')
        return redirect(url_for('main.admin'))

    db = get_db()

    # Get all runs for the version
    runs = db.execute('SELECT id, report_path FROM test_runs WHERE version_id = ?', (version_id,)).fetchall()
    run_ids = [run['id'] for run in runs]

    # Delete report directories
    for run in runs:
        if run['report_path']:
            run_dir = os.path.dirname(run['report_path'])
            if os.path.exists(run_dir):
                shutil.rmtree(run_dir)

    # Delete test cases
    if run_ids:
        db.execute(f'DELETE FROM test_cases WHERE test_run_id IN ({",".join(map(str, run_ids))})')
        db.commit()

    # Delete test runs
    db.execute('DELETE FROM test_runs WHERE version_id = ?', (version_id,))
    db.commit()

    # Delete version
    db.execute('DELETE FROM versions WHERE id = ?', (version_id,))
    db.commit()

    flash('Version deleted successfully.', 'success')
    return redirect(url_for('main.admin'))

@bp.route('/admin', methods=['GET', 'POST'])
def admin():
    db = get_db()

    if request.method == 'POST':
        form_type = request.form.get('form_type')
        if form_type == 'settings':
            for panel in panels:
                panel_id = panel['id']
                pass_rate_yellow = request.form.get(f'pass_rate_yellow_{panel_id}')
                pass_rate_red = request.form.get(f'pass_rate_red_{panel_id}')
                flaky_rate_yellow = request.form.get(f'flaky_rate_yellow_{panel_id}')
                flaky_rate_red = request.form.get(f'flaky_rate_red_{panel_id}')

                db.execute(
                    """
                    INSERT INTO panel_settings (panel_id, pass_rate_yellow, pass_rate_red, flaky_rate_yellow, flaky_rate_red)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(panel_id) DO UPDATE SET
                        pass_rate_yellow=excluded.pass_rate_yellow,
                        pass_rate_red=excluded.pass_rate_red,
                        flaky_rate_yellow=excluded.flaky_rate_yellow,
                        flaky_rate_red=excluded.flaky_rate_red
                    """,
                    (panel_id, pass_rate_yellow, pass_rate_red, flaky_rate_yellow, flaky_rate_red)
                )
            db.commit()
            flash('Settings saved successfully.', 'success')
            return redirect(url_for('main.admin'))

    panels = db.execute('SELECT * FROM panels').fetchall()
    panels_data = []
    for panel_row in panels:
        panel = dict(panel_row)
        versions_rows = db.execute('SELECT * FROM versions WHERE panel_id = ?', (panel['id'],)).fetchall()
        versions = [dict(row) for row in versions_rows]
        settings_row = db.execute('SELECT * FROM panel_settings WHERE panel_id = ?', (panel['id'],)).fetchone()
        settings = dict(settings_row) if settings_row else None

        panels_data.append({
            'panel': panel,
            'versions': versions,
            'settings': settings
        })

    return render_template('admin.html', panels_data=panels_data)

@bp.route('/<panel_name>/<version_name>', methods=['GET'])
def version_metrics(panel_name, version_name):
    db = get_db()
    panel = db.execute('SELECT * FROM panels WHERE name = ?', (panel_name,)).fetchone()
    if not panel:
        return "Panel not found", 404

    version = db.execute(
        'SELECT * FROM versions WHERE panel_id = ? AND name = ?',
        (panel['id'], version_name)
    ).fetchone()
    if not version:
        return "Version not found", 404

    # Get the latest run for this version
    latest_run = db.execute(
        'SELECT * FROM test_runs WHERE version_id = ? ORDER BY timestamp DESC LIMIT 1',
        (version['id'],)
    ).fetchone()

    if not latest_run:
        return render_template('version_metrics.html', panel_name=panel_name, version_name=version_name, modules=[])

    # Get unique module names from this run
    modules_cursor = db.execute(
        'SELECT DISTINCT module_name FROM test_cases WHERE test_run_id = ?',
        (latest_run['id'],)
    ).fetchall()

    modules = [row['module_name'] for row in modules_cursor]

    # The report path is the same for all modules in this run
    report_path = latest_run['report_path']

    # Get filter from query params
    active_filter = request.args.get('filter', 'all')

    return render_template(
        'version_metrics.html',
        panel_name=panel_name,
        version_name=version_name,
        modules=modules,
        report_path=report_path,
        active_filter=active_filter
    )

@bp.route('/<panel_name>/metrics', methods=['GET'])
def panel_metrics(panel_name):
    db = get_db()
    panel = db.execute('SELECT * FROM panels WHERE name = ?', (panel_name,)).fetchone()
    if not panel:
        return "Panel not found", 404

    latest_version = db.execute(
        'SELECT * FROM versions WHERE panel_id = ? ORDER BY id DESC LIMIT 1',
        (panel['id'],)
    ).fetchone()
    if not latest_version:
        return "No versions found for this panel", 404

    latest_run = db.execute(
        'SELECT * FROM test_runs WHERE version_id = ? ORDER BY timestamp DESC LIMIT 1',
        (latest_version['id'],)
    ).fetchone()
    if not latest_run:
        return "No runs found for this version", 404

    test_cases_df = pd.read_sql_query(
        f'SELECT * FROM test_cases WHERE test_run_id = {latest_run["id"]}',
        db
    )

    # Donut chart for test statuses
    status_counts = test_cases_df['status'].value_counts()
    donut_fig = px.pie(
        values=status_counts.values,
        names=status_counts.index,
        title='Статус тестів',
        hole=.3
    )
    donut_json = json.dumps(donut_fig, cls=plotly.utils.PlotlyJSONEncoder)

    # Stacked bar chart for status by module
    module_status_counts = test_cases_df.groupby(['module_name', 'status']).size().reset_index(name='counts')
    stacked_bar_fig = px.bar(
        module_status_counts,
        x='module_name',
        y='counts',
        color='status',
        title='Статус по модулях'
    )
    stacked_bar_json = json.dumps(stacked_bar_fig, cls=plotly.utils.PlotlyJSONEncoder)

    # Duration anomaly chart
    anomalies = []
    for index, row in test_cases_df.iterrows():
        # Get last 10 successful runs for this test
        history = pd.read_sql_query(
            f"SELECT duration FROM test_cases WHERE full_name = '{row['full_name']}' AND status = 'pass' AND test_run_id < {latest_run['id']} ORDER BY id DESC LIMIT 10",
            db
        )
        if len(history) >= 2: # Need at least 2 points to calculate std
            avg_d = history['duration'].mean()
            std_d = history['duration'].std()
            if row['duration'] > avg_d + 3 * std_d:
                anomalies.append({
                    'full_name': row['full_name'],
                    'deviation': row['duration'] - avg_d
                })

    duration_anomaly_json = "{}"
    if anomalies:
        anomalies_df = pd.DataFrame(anomalies).nlargest(20, 'deviation')
        duration_anomaly_fig = px.bar(
            anomalies_df,
            x='full_name',
            y='deviation',
            title='Топ-20 тестів з аномальною тривалістю'
        )
        duration_anomaly_json = json.dumps(duration_anomaly_fig, cls=plotly.utils.PlotlyJSONEncoder)

    return render_template(
        'panel_metrics.html',
        panel_name=panel_name,
        donut_chart=donut_json,
        stacked_bar_chart=stacked_bar_json,
        duration_anomaly_chart=duration_anomaly_json
    )

@bp.route('/', methods=['GET'])
def index():
    db = get_db()
    panels = db.execute('SELECT * FROM panels').fetchall()

    panels_data = []
    for panel in panels:
        versions_data = []
        versions = db.execute('SELECT * FROM versions WHERE panel_id = ? ORDER BY id DESC', (panel['id'],)).fetchall()

        for version in versions:
            all_runs = db.execute('SELECT * FROM test_runs WHERE version_id = ? ORDER BY timestamp DESC', (version['id'],)).fetchall()
            if not all_runs:
                continue

            run_ids = [run['id'] for run in all_runs]
            run_map = {run['id']: run for run in all_runs}

            test_cases_df = pd.read_sql_query(f"SELECT tc.*, tr.timestamp FROM test_cases tc JOIN test_runs tr ON tc.test_run_id = tr.id WHERE tc.test_run_id IN ({','.join(map(str, run_ids))})", db)
            if test_cases_df.empty:
                continue

            # Determine final status for each unique test based on the latest run
            latest_tests_df = test_cases_df.sort_values('timestamp').groupby('full_name').last()

            unique_tests_df = latest_tests_df.rename(columns={'status': 'final_status'}).reset_index()

            # Calculate aggregated stats for modules/classes
            module_stats = unique_tests_df.groupby(['module_name', 'class_name'])['final_status'].value_counts().unstack(fill_value=0)
            if 'pass' not in module_stats: module_stats['pass'] = 0
            if 'fail' not in module_stats: module_stats['fail'] = 0
            module_stats['total'] = module_stats['pass'] + module_stats['fail']

            modules_data = []
            for (module_name, class_name), stats in module_stats.iterrows():
                # Get individual runs for this module/class
                runs_for_module = test_cases_df[(test_cases_df['module_name'] == module_name) & (test_cases_df['class_name'] == class_name)]

                # Create a list of runs with their unique tests for this module
                run_details = []
                for run_id, group in runs_for_module.groupby('test_run_id'):
                    run_info = run_map.get(run_id)
                    if run_info:
                        run_details.append({
                            'timestamp': run_info['timestamp'],
                            'report_path': run_info['report_path'],
                            'passed': group[group['status'] == 'pass'].shape[0],
                            'failed': group[group['status'] == 'fail'].shape[0],
                            'total': group.shape[0]
                        })

                modules_data.append({
                    'name': f"{module_name} - {class_name}",
                    'passed': stats['pass'],
                    'failed': stats['fail'],
                    'total': stats['total'],
                    'runs': sorted(run_details, key=lambda x: x['timestamp'], reverse=True)
                })

            # Calculate summary stats for the entire version
            version_total = module_stats['total'].sum()
            version_passed = module_stats['pass'].sum()
            version_failed = module_stats['fail'].sum()

            versions_data.append({
                'name': version['name'],
                'timestamp': all_runs[0]['timestamp'], # Timestamp of the latest run
                'modules': modules_data,
                'total': version_total,
                'passed': version_passed,
                'failed': version_failed
            })

        # --- Re-implementing metrics for the panel header ---
        flaky_rate = 0
        new_fails_count = 0
        pass_rate_trend = []

        # For these metrics, we consider the latest version
        if versions:
            latest_version = versions[0] # versions are sorted by id DESC
            # Get all runs for the latest version to calculate flaky rate
            latest_version_runs_rows = db.execute('SELECT id FROM test_runs WHERE version_id = ?', (latest_version['id'],)).fetchall()
            latest_version_run_ids = [r['id'] for r in latest_version_runs_rows]

            if latest_version_run_ids:
                # Flaky rate calculation
                flaky_df = pd.read_sql_query(f'SELECT full_name, status FROM test_cases WHERE test_run_id IN ({",".join(map(str, latest_version_run_ids))})', db)
                if not flaky_df.empty:
                    flaky_tests = flaky_df.groupby('full_name')['status'].nunique() > 1
                    flaky_rate = (flaky_tests.sum() / len(flaky_tests)) * 100 if len(flaky_tests) > 0 else 0

            # New Fails calculation (compare latest version with the one before it)
            if len(versions) > 1:
                previous_version = versions[1]
                # ... (rest of new fails logic would go here, simplified for now)
                # This logic is complex and might need a dedicated function. For now, placeholder.

            # Pass-rate trend for last 5 versions
            last_5_versions = versions[:5]
            for v in reversed(last_5_versions):
                last_run = db.execute('SELECT pass_rate FROM test_runs WHERE version_id = ? ORDER BY timestamp DESC LIMIT 1', (v['id'],)).fetchone()
                if last_run:
                    pass_rate_trend.append(last_run['pass_rate'])

        panels_data.append({
            'id': panel['id'],
            'name': panel['name'],
            'versions': versions_data,
            'flaky_rate': flaky_rate,
            'new_fails': new_fails_count,
            'pass_rate_trend': pass_rate_trend,
            'latest_version_name': latest_version['name'] if versions else None
        })

    return render_template('index.html', panels_data=panels_data)

@bp.route('/rest/upload_results', methods=['POST'])
def upload_results():
    if 'file' not in request.files:
        return jsonify(error="No file part"), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify(error="No selected file"), 400
    if file and allowed_file(file.filename):
        # Get form data
        md5_hash = request.form.get('md5')
        panel_name = request.form.get('root_id')
        version_name = request.form.get('panel_id')

        if not all([md5_hash, panel_name, version_name]):
            return jsonify(error="Missing form data"), 400

        # MD5 validation
        file.seek(0)
        file_hash = hashlib.md5(file.read()).hexdigest()
        if file_hash != md5_hash:
            return jsonify(error="MD5 mismatch"), 400
        file.seek(0)

        # Save file
        filename = secure_filename(file.filename)
        run_timestamp = str(int(time.time()))
        save_dir = os.path.join(current_app.config['UPLOADS_FOLDER'], panel_name, version_name, run_timestamp)
        os.makedirs(save_dir, exist_ok=True)
        file_path = os.path.join(save_dir, filename)
        file.save(file_path)

        # Unzip file
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(save_dir)

        # Parse total.json
        total_json_path = os.path.join(save_dir, 'total.json')
        if not os.path.exists(total_json_path):
            return jsonify(error="total.json not found in zip"), 400

        with open(total_json_path, 'r', encoding='utf-8') as f:
            total_data = json.load(f)

        db = get_db()

        # Get or create panel
        panel = db.execute('SELECT id FROM panels WHERE name = ?', (panel_name,)).fetchone()
        if panel is None:
            cursor = db.execute('INSERT INTO panels (name) VALUES (?)', (panel_name,))
            db.commit()
            panel_id = cursor.lastrowid
        else:
            panel_id = panel['id']

        # Get or create version
        version = db.execute('SELECT id FROM versions WHERE name = ? AND panel_id = ?', (version_name, panel_id)).fetchone()
        if version is None:
            cursor = db.execute('INSERT INTO versions (name, panel_id) VALUES (?, ?)', (version_name, panel_id))
            db.commit()
            version_id = cursor.lastrowid
        else:
            version_id = version['id']

        # Process test cases from the new format
        test_cases_to_insert = []
        total_tests = 0
        for module in total_data.get('modules', []):
            module_name_full = module.get('name', '')
            for test in module.get('tests', []):
                total_tests += 1
                test_stat = test.get('statistic', {})
                failures = test_stat.get('Failures', 0)
                status = 'fail' if failures > 0 else 'pass'

                # Extract class and test names
                class_name, test_name = test.get('name', '.').split('.', 1)

                test_cases_to_insert.append({
                    'full_name': test.get('name', ''),
                    'module_name': module_name_full,
                    'class_name': class_name,
                    'test_name': test_name,
                    'status': status,
                    'duration': test_stat.get('Duration', 0.0)
                })

        # Process summary from the new format
        summary_stat = total_data.get('statistic', {})
        failed_tests = summary_stat.get('Failures', 0)
        ignored_tests = summary_stat.get('Ignored', 0)
        skipped_tests = 0 # Not present in the new format
        passed_tests = total_tests - failed_tests - ignored_tests - skipped_tests
        pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0

        # Create test run
        cursor = db.execute(
            'INSERT INTO test_runs (version_id, timestamp, total_tests, passed_tests, failed_tests, skipped_tests, ignored_tests, pass_rate, report_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (version_id, int(run_timestamp), total_tests, passed_tests, failed_tests, skipped_tests, ignored_tests, pass_rate, os.path.join(save_dir, 'total.html'))
        )
        db.commit()
        test_run_id = cursor.lastrowid

        # Create test cases
        for test_case_data in test_cases_to_insert:
            db.execute(
                'INSERT INTO test_cases (test_run_id, full_name, module_name, class_name, test_name, status, duration) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (test_run_id, test_case_data['full_name'], test_case_data['module_name'], test_case_data['class_name'], test_case_data['test_name'], test_case_data['status'], test_case_data['duration'])
            )
        db.commit()

        return jsonify(success=True, message="File uploaded and processed successfully.")
    else:
        return jsonify(error="File type not allowed"), 400

@bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOADS_FOLDER'], filename, as_attachment=False)
