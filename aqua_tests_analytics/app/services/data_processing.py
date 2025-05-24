import datetime
import datetime # Already imported
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from flask import current_app # Import current_app for logging
from app import db
from app.models import Version, TestRun, TestAgg, TestStatus

def process_test_data(version_id: int, total_json_data: dict):
    """
    Processes the total.json data and populates TestRun records.
    Deletes existing TestRun and TestAgg data for the version_id.
    """
    # Ensure version_id is for an existing Version
    version = db.session.get(Version, version_id)
    if not version:
        # Or raise an error, log, etc.
        print(f"Version with id {version_id} not found.")
        return

    # Delete existing data for this version to ensure idempotency
    TestAgg.query.filter_by(version_id=version_id).delete()
    TestRun.query.filter_by(version_id=version_id).delete()
    # It's usually good to commit deletions before adding new bulk data
    # but if the process fails mid-way, we might want to rollback everything.
    # For now, let's commit deletions separately. If issues arise, reconsider.
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error committing deletions: {e}")
        # Potentially re-raise or handle more gracefully
        raise

    test_runs_to_create = []

    for module in total_json_data.get('modules', []):
        class_name = module.get('name')
        for test_data in module.get('tests', []):
            test_name = test_data.get('name')

            # Exclude Helper Tests
            if test_name in ["CreateEnvironment", "RemoveEnvironment"]:
                continue

            statistic = test_data.get('statistic', {})
            failures = statistic.get('Failures', 0)
            warnings = statistic.get('Warnings', 0)
            ignored = statistic.get('Ignored', 0)
            duration = statistic.get('Duration', 0.0)
            # Assuming 'Started' is Unix timestamp in seconds
            started_unix_ts = statistic.get('Started')

            status = TestStatus.PASS # Default
            if failures > 0:
                status = TestStatus.FAIL
            elif warnings > 0:
                status = TestStatus.WARNING
            elif ignored > 0:
                status = TestStatus.IGNORED
            
            started_datetime = None
            if started_unix_ts is not None:
                try:
                    # Ensure timestamp is treated as numeric (it's specified as 'number' in schema)
                    started_datetime = datetime.datetime.fromtimestamp(float(started_unix_ts), tz=datetime.timezone.utc)
                except (ValueError, TypeError) as e:
                    print(f"Warning: Could not parse timestamp '{started_unix_ts}' for test '{test_name}'. Error: {e}")
                    # Decide if you want to skip this TestRun or save with None timestamp
                    # For now, let's save with None if it's invalid
                    started_datetime = None


            test_run = TestRun(
                version_id=version_id,
                test_id=test_name,
                class_name=class_name,
                status=status,
                duration_seconds=duration,
                started_ts=started_datetime
            )
            test_runs_to_create.append(test_run)

    if test_runs_to_create:
        try:
            db.session.bulk_save_objects(test_runs_to_create)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error bulk saving TestRuns: {e}")
            # Potentially re-raise
            raise


def aggregate_test_data(version_id: int):
    """
    Aggregates TestRun data into TestAgg records for a given version_id.
    """
    # version is the current version object being processed
    version = db.session.get(Version, version_id) 
    if not version:
        # Use current_app.logger if available, or print
        # from flask import current_app # Add this import at the top if not already there
        current_app.logger.error(f"Version with id {version_id} not found for aggregation.")
        # print(f"Version with id {version_id} not found for aggregation.") # Keep print if logger not set up here
        return

    # Fetch all TestRuns for the version_id, ordered by test_id and then by started_ts
    # This helps in grouping and then processing runs in chronological order for each test
    all_runs_for_version = db.session.query(TestRun).filter_by(version_id=version_id).order_by(TestRun.test_id, TestRun.started_ts).all()

    if not all_runs_for_version:
        print(f"No TestRuns found for version_id {version_id} to aggregate.")
        return

    # Group runs by test_id using pandas for convenience
    df_runs = pd.DataFrame([{
        'test_id': run.test_id,
        'class_name': run.class_name, # Add class_name for aggregation
        'status': run.status.value, # Use enum value for comparisons
        'duration_seconds': float(run.duration_seconds) if run.duration_seconds is not None else np.nan,
        'started_ts': run.started_ts
    } for run in all_runs_for_version])

    if df_runs.empty:
        print(f"DataFrame is empty for version_id {version_id}. No data to aggregate.")
        return

    test_aggs_to_create_or_update = []

    for test_id, group in df_runs.groupby('test_id'):
        # Ensure runs are sorted by time for flip calculations, etc.
        # The initial query already sorts by started_ts, but if groupby doesn't preserve it, re-sort.
        group = group.sort_values(by='started_ts', ascending=True).reset_index()

        num_runs = len(group)
        last_run = group.iloc[-1]

        last_status_enum = TestStatus(last_run['status'])
        last_started_ts_val = last_run['started_ts']
        # Get class_name from the last run (it should be consistent for a given test_id within a version)
        class_name_val = last_run['class_name'] 

        passes = sum(group['status'] == TestStatus.PASS.value)
        fails = sum(group['status'] == TestStatus.FAIL.value)
        ignores = sum(group['status'] == TestStatus.IGNORED.value)
        # 'skipped' status is not generated by process_test_data from current total.json structure
        skips = sum(group['status'] == TestStatus.SKIPPED.value) 


        flips = 0
        if num_runs > 1:
            for i in range(1, num_runs):
                if group['status'].iloc[i] != group['status'].iloc[i-1]:
                    flips += 1
        
        flips_current_version = flips # Renaming for clarity in new logic
        t1_transition_rate = flips_current_version / (num_runs - 1) if num_runs > 1 else 0.0

        # New T4 Flaky Flag Logic
        # 'version' is the current Version object, passed or fetched at the start of the function
        t4_flaky_flag = False
        if flips_current_version > 0:
            t4_flaky_flag = True
        else:
            # version object should be the one for the current version_id, already fetched
            if version: # Ensure current version object is available
                previous_versions = db.session.query(Version).filter(
                    Version.panel_id == version.panel_id,
                    Version.created_ts < version.created_ts
                ).order_by(Version.created_ts.desc()).limit(4).all()

                for prev_ver in previous_versions:
                    # test_id is the current test_id being processed in the outer loop
                    prev_agg = db.session.query(TestAgg).filter_by(
                        version_id=prev_ver.id,
                        test_id=test_id 
                    ).first()
                    if prev_agg and prev_agg.flips > 0:
                        t4_flaky_flag = True
                        break
            else:
                current_app.logger.warning(f"Current version object not found for version_id {version_id} during T4 calculation for test_id {test_id}.")
        
        t2_fail_after_pass = 0.0
        first_pass_index = group[group['status'] == TestStatus.PASS.value].index.min() # Pandas index, not iloc index
        
        if pd.notna(first_pass_index): # Check if first_pass_index is not NaN (i.e., a pass occurred)
            # Need to use .iloc for positional indexing if using reset_index() results.
            # Or, more robustly, filter the dataframe from that point onwards.
            # Assuming 'first_pass_index' is the actual index in the 'group' DataFrame
            runs_after_first_pass = group[group.index > first_pass_index] # Filter rows after the first pass
            if not runs_after_first_pass.empty:
                fails_after_first_pass = sum(runs_after_first_pass['status'] == TestStatus.FAIL.value)
                if len(runs_after_first_pass) > 0 : # Denominator check
                     t2_fail_after_pass = fails_after_first_pass / len(runs_after_first_pass)
                else: # Should not happen if runs_after_first_pass is not empty
                    t2_fail_after_pass = 0.0 
            else: # No runs after the first pass
                 t2_fail_after_pass = 0.0
        else: # No pass found
            t2_fail_after_pass = 0.0 # Or None, depending on requirements for "no pass"


        t3_retry_success = None # Placeholder as per requirements

        # t4_flaky_flag is now calculated above

        t5_weighted_instab = 0.0
        if num_runs > 1: # flips_current_version are only possible with more than one run
            for i in range(1, num_runs): # Iterate from the second run (index 1)
                if group['status'].iloc[i] != group['status'].iloc[i-1]:
                    t5_weighted_instab += (1 / (i + 1)) # Using (i+1) because question implies 1-based run index (R1, R2, R3 -> indices 0,1,2)

        avg_duration = group['duration_seconds'].mean()
        median_duration = group['duration_seconds'].median()
        
        # Handle NaN from pandas mean/median if all durations were NaN (e.g. all null in DB)
        avg_duration = None if pd.isna(avg_duration) else avg_duration
        median_duration = None if pd.isna(median_duration) else median_duration

        # Check if TestAgg already exists to update, otherwise create
        test_agg = db.session.query(TestAgg).filter_by(version_id=version_id, test_id=test_id).first()
        if test_agg:
            test_agg.class_name = class_name_val # Update class_name
            test_agg.last_status = last_status_enum
            test_agg.last_started_ts = last_started_ts_val
            test_agg.passes = passes
            test_agg.fails = fails
            test_agg.ignores = ignores
            test_agg.skips = skips # Will be 0
            test_agg.flips = flips_current_version # Store flips from current version
            test_agg.t1_transition_rate = t1_transition_rate
            test_agg.t2_fail_after_pass = t2_fail_after_pass
            test_agg.t3_retry_success = t3_retry_success
            test_agg.t4_flaky_flag = t4_flaky_flag
            test_agg.t5_weighted_instab = t5_weighted_instab
            test_agg.avg_duration = avg_duration
            test_agg.median_duration = median_duration
        else:
            test_agg = TestAgg(
                version_id=version_id,
                test_id=test_id,
                class_name=class_name_val, # Add class_name
                last_status=last_status_enum,
                last_started_ts=last_started_ts_val,
                passes=passes,
                fails=fails,
                ignores=ignores,
                skips=skips, # Will be 0
                flips=flips_current_version, # Store flips from current version
                t1_transition_rate=t1_transition_rate,
                t2_fail_after_pass=t2_fail_after_pass,
                t3_retry_success=t3_retry_success, # Placeholder
                t4_flaky_flag=t4_flaky_flag,
                t5_weighted_instab=t5_weighted_instab,
                avg_duration=avg_duration,
                median_duration=median_duration
            )
            db.session.add(test_agg)
        # No need to append to a list and bulk_update, can add to session directly
        # SQLAlchemy tracks changes on existing objects and adds new ones to the session.

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error saving TestAggs: {e}")
        # Potentially re-raise
        raise
