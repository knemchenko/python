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
    for panel in panels:
        versions = db.execute('SELECT * FROM versions WHERE panel_id = ?', (panel['id'],)).fetchall()
        settings = db.execute('SELECT * FROM panel_settings WHERE panel_id = ?', (panel['id'],)).fetchone()
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

    # Get all test cases for this version
    runs_in_version = db.execute(
        'SELECT id FROM test_runs WHERE version_id = ?',
        (version['id'],)
    ).fetchall()
    run_ids = [run['id'] for run in runs_in_version]

    test_cases_df = pd.DataFrame()
    if run_ids:
        query = f"""
            SELECT tc.*, tr.report_path
            FROM test_cases tc
            JOIN test_runs tr ON tc.test_run_id = tr.id
            WHERE tc.test_run_id IN ({",".join(map(str, run_ids))})
        """
        test_cases_df = pd.read_sql_query(query, db)

    if test_cases_df.empty:
        return render_template('version_metrics.html', panel_name=panel_name, version_name=version_name, test_cases=[])

    # Get latest status for each test
    latest_tests = test_cases_df.sort_values('test_run_id').groupby('full_name').last()

    # Get average duration
    avg_duration = test_cases_df.groupby('full_name')['duration'].mean()

    # Combine data
    latest_tests = latest_tests.merge(avg_duration.rename('avg_duration'), on='full_name')

    # Calculate first fail and duration anomaly
    latest_tests['is_first_fail'] = False
    latest_tests['is_duration_anomaly'] = False

    for index, row in latest_tests.iterrows():
        # First Fail
        if row['status'] == 'fail':
            history = test_cases_df[test_cases_df['full_name'] == row['full_name']].sort_values('test_run_id')
            if len(history) > 1 and history.iloc[-2]['status'] == 'pass':
                latest_tests.loc[index, 'is_first_fail'] = True

        # Duration Anomaly (for the latest run of the test)
        history = db.execute(
            f"SELECT duration FROM test_cases WHERE full_name = '{row['full_name']}' AND status = 'pass' AND id < {row['id']} ORDER BY id DESC LIMIT 10"
        ).fetchall()

        if len(history) >= 2:
            durations = [h['duration'] for h in history]
            avg_d = sum(durations) / len(durations)
            std_d = pd.Series(durations).std()
            if row['duration'] > avg_d + 3 * std_d:
                latest_tests.loc[index, 'is_duration_anomaly'] = True

    # Calculate is_flaky and is_new_fail
    latest_tests['is_flaky'] = False
    latest_tests['is_new_fail'] = False

    previous_version = db.execute(
        'SELECT * FROM versions WHERE panel_id = ? AND id < ? ORDER BY id DESC LIMIT 1',
        (panel['id'], version['id'])
    ).fetchone()

    for index, row in latest_tests.iterrows():
        # is_flaky
        statuses = test_cases_df[test_cases_df['full_name'] == row['full_name']]['status'].unique()
        if 'pass' in statuses and 'fail' in statuses:
            latest_tests.loc[index, 'is_flaky'] = True

        # is_new_fail
        if row['status'] == 'fail' and previous_version:
            latest_run_prev = db.execute(
                'SELECT id FROM test_runs WHERE version_id = ? ORDER BY timestamp DESC LIMIT 1',
                (previous_version['id'],)
            ).fetchone()
            if latest_run_prev:
                status_prev = db.execute(
                    'SELECT status FROM test_cases WHERE test_run_id = ? AND full_name = ?',
                    (latest_run_prev['id'], row.name)
                ).fetchone()
                if status_prev and status_prev['status'] == 'pass':
                    latest_tests.loc[index, 'is_new_fail'] = True


    # Calculate history for modal
    def get_history(full_name):
        history_df = test_cases_df[test_cases_df['full_name'] == full_name][['status', 'duration']]
        return history_df.to_json(orient='records')

    latest_tests['history'] = latest_tests.index.to_series().apply(get_history)

    return render_template(
        'version_metrics.html',
        panel_name=panel_name,
        version_name=version_name,
        test_cases=latest_tests.to_dict('records')
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
        versions = db.execute(
            'SELECT * FROM versions WHERE panel_id = ? ORDER BY id DESC',
            (panel['id'],)
        ).fetchall()

        for version in versions:
            latest_run = db.execute(
                'SELECT * FROM test_runs WHERE version_id = ? ORDER BY timestamp DESC LIMIT 1',
                (version['id'],)
            ).fetchone()

            if latest_run:
                versions_data.append({
                    'name': version['name'],
                    'pass_rate': latest_run['pass_rate'],
                    'tests_summary': f"{latest_run['passed_tests']}/{latest_run['total_tests']}",
                    'timestamp': latest_run['timestamp']
                })

        panels_data.append({
            'id': panel['id'],
            'name': panel['name'],
            'versions': versions_data
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
