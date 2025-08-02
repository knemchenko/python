-- Drop tables if they exist
DROP TABLE IF EXISTS panels;
DROP TABLE IF EXISTS versions;
DROP TABLE IF EXISTS test_runs;
DROP TABLE IF EXISTS test_cases;
DROP TABLE IF EXISTS panel_settings;

-- Panels table
CREATE TABLE panels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    regex TEXT,
    jenkins_url TEXT
);

-- Versions table
CREATE TABLE versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    panel_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (panel_id) REFERENCES panels (id)
);

-- Test runs table
CREATE TABLE test_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    total_tests INTEGER NOT NULL,
    passed_tests INTEGER NOT NULL,
    failed_tests INTEGER NOT NULL,
    skipped_tests INTEGER NOT NULL,
    ignored_tests INTEGER NOT NULL,
    pass_rate REAL NOT NULL,
    report_path TEXT NOT NULL,
    FOREIGN KEY (version_id) REFERENCES versions (id)
);

-- Test cases table
CREATE TABLE test_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_run_id INTEGER NOT NULL,
    full_name TEXT NOT NULL,
    module_name TEXT NOT NULL,
    class_name TEXT NOT NULL,
    test_name TEXT NOT NULL,
    status TEXT NOT NULL,
    duration REAL NOT NULL,
    FOREIGN KEY (test_run_id) REFERENCES test_runs (id)
);

-- Panel settings table
CREATE TABLE panel_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    panel_id INTEGER UNIQUE NOT NULL,
    pass_rate_yellow REAL NOT NULL DEFAULT 95.0,
    pass_rate_red REAL NOT NULL DEFAULT 90.0,
    flaky_rate_yellow REAL NOT NULL DEFAULT 5.0,
    flaky_rate_red REAL NOT NULL DEFAULT 10.0,
    FOREIGN KEY (panel_id) REFERENCES panels (id)
);
