#!/usr/bin/env python3

import argparse
import json
import sqlite3
from pathlib import Path
from datetime import datetime, UTC


DEFAULT_DB = "youtube_summary.db"


def utc_now():
    return datetime.now(UTC).replace(microsecond=0).isoformat()

def create_run(
    conn: sqlite3.Connection,
    task_type: str,
    input_json: str,
) -> int:
    now = utc_now()

    cursor = conn.execute(
        """
        INSERT INTO runs (
            task_type,
            input_json,
            status,
            row_created_at,
            row_updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            task_type,
            input_json,
            "pending",
            now,
            now,
        ),
    )

    conn.commit()

    return cursor.lastrowid


def main():
    parser = argparse.ArgumentParser(
        description="Create a new pipeline run."
    )

    parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help="SQLite database path",
    )

    parser.add_argument(
        "--task-type",
        required=True,
        help="Task type, e.g. youtube_summary",
    )

    parser.add_argument(
        "--input-json",
        required=True,
        help="JSON payload stored in runs.input_json",
    )

    args = parser.parse_args()

    try:
        # Varmistetaan että JSON on validia
        parsed_input = json.loads(args.input_json)

        db_path = Path(args.db)

        conn = sqlite3.connect(db_path)

        try:
            run_id = create_run(
                conn=conn,
                task_type=args.task_type,
                input_json=json.dumps(
                    parsed_input,
                    ensure_ascii=False,
                ),
            )

        finally:
            conn.close()

        print(
            json.dumps(
                {
                    "ok": True,
                    "run_id": run_id,
                    "task_type": args.task_type,
                    "status": "pending",
                },
                ensure_ascii=False,
            )
        )

    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                },
                ensure_ascii=False,
            )
        )

        raise SystemExit(1)


if __name__ == "__main__":
    main()
