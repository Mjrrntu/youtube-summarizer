#!/usr/bin/env python3

import sqlite3
from pathlib import Path


DB_PATH = Path("youtube_summary.db")


def create_schema(conn):
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS task_definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            task_type TEXT NOT NULL,
            step_order INTEGER NOT NULL,
            step_name TEXT NOT NULL,
            step_handler TEXT NOT NULL,

            enabled INTEGER NOT NULL DEFAULT 1,
            config_json TEXT DEFAULT '{}',

            row_created_at TEXT,
            row_updated_at TEXT,

            UNIQUE(task_type, step_order)
        );

        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            task_type TEXT NOT NULL,
            input_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',

            error_text TEXT,

            row_created_at TEXT,
            row_updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS run_step_results (
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

        CREATE INDEX IF NOT EXISTS idx_task_definitions_task_type
            ON task_definitions(task_type);

        CREATE INDEX IF NOT EXISTS idx_task_definitions_enabled
            ON task_definitions(enabled);

        CREATE INDEX IF NOT EXISTS idx_runs_task_type
            ON runs(task_type);

        CREATE INDEX IF NOT EXISTS idx_runs_status
            ON runs(status);

        CREATE INDEX IF NOT EXISTS idx_run_step_results_run_id
            ON run_step_results(run_id);

        CREATE INDEX IF NOT EXISTS idx_run_step_results_status
            ON run_step_results(status);
        """
    )


def seed_youtube_summary_pipeline(conn):
    rows = [
        ("youtube_summary", 1, "load_transcript", "load_transcript"),
        ("youtube_summary", 2, "summarize", "summarize"),
        ("youtube_summary", 3, "collect_claims", "collect_claims"),
        ("youtube_summary", 4, "verify_claims", "verify_claims"),
        ("youtube_summary", 5, "annotate_summary", "annotate_summary"),
        ("youtube_summary", 6, "render_result", "render_result"),
    ]

    conn.executemany(
        """
        INSERT OR IGNORE INTO task_definitions (
            task_type,
            step_order,
            step_name,
            step_handler
        )
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )


def main():
    conn = sqlite3.connect(DB_PATH)

    try:
        create_schema(conn)
        seed_youtube_summary_pipeline(conn)
        conn.commit()
        print(f"Database initialized: {DB_PATH}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
