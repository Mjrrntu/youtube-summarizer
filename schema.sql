CREATE TABLE task_definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            task_type TEXT NOT NULL,
            step_order INTEGER NOT NULL,
            step_name TEXT NOT NULL,
            step_handler TEXT NOT NULL,

            enabled INTEGER NOT NULL DEFAULT 1,
            config_json TEXT DEFAULT '{}',

            row_created_at TEXT,
            row_updated_at TEXT, prompt_id INTEGER, model_name TEXT,

            UNIQUE(task_type, step_order)
        );
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            task_type TEXT NOT NULL,
            input_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',

            error_text TEXT,

            row_created_at TEXT,
            row_updated_at TEXT
        );
CREATE TABLE run_step_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            run_id INTEGER NOT NULL,

            step_order INTEGER NOT NULL,
            step_name TEXT NOT NULL,
            step_handler TEXT NOT NULL,

            input_json TEXT DEFAULT '{}',
            output_json TEXT DEFAULT '{}',
            output_text TEXT DEFAULT '',

            status TEXT NOT NULL DEFAULT 'pending',
            error_text TEXT,

            row_created_at TEXT,
            row_updated_at TEXT,

            FOREIGN KEY(run_id) REFERENCES runs(id),

            UNIQUE(run_id, step_order)
        );
CREATE INDEX idx_task_definitions_task_type
            ON task_definitions(task_type);
CREATE INDEX idx_task_definitions_enabled
            ON task_definitions(enabled);
CREATE INDEX idx_runs_task_type
            ON runs(task_type);
CREATE INDEX idx_runs_status
            ON runs(status);
CREATE INDEX idx_run_step_results_run_id
            ON run_step_results(run_id);
CREATE INDEX idx_run_step_results_status
            ON run_step_results(status);
CREATE TABLE prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    prompt_name TEXT NOT NULL UNIQUE,
    prompt_text TEXT NOT NULL,

    row_created_at TEXT,
    row_updated_at TEXT
);
