#!/usr/bin/env python3

import json
import pathlib
import sqlite3
import subprocess

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


PROJECT_DIR = pathlib.Path.home() / "git" / "youtube-summarizer"
DB_PATH = PROJECT_DIR / "youtube_summary.db"
PYTHON = PROJECT_DIR / ".venv" / "bin" / "python"

CREATE_RUN = PROJECT_DIR / "scripts" / "create_run.py"
EXECUTE_TASK = PROJECT_DIR / "scripts" / "backend_execute_task.py"

TASK_TYPE = "youtube_summary"


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class SummarizeRequest(BaseModel):
    url: str


def run_command(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=7200,
    )


def get_rendered_result(run_id: int) -> str:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        row = conn.execute(
            """
            SELECT
                r.output_contents
            FROM run_step_results r
            JOIN task_definitions td
              ON td.task_type = (
                    SELECT task_type
                    FROM runs
                    WHERE id = r.run_id
                 )
             AND td.step_order = r.step_order
            WHERE r.run_id = ?
              AND r.status = 'completed'
              AND td.enabled = 1
            ORDER BY td.step_order DESC
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()

        if row is None:
            return ""

        return row["output_contents"] or ""

    finally:
        conn.close()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/summarize")
def summarize(req: SummarizeRequest):
    input_payload = {
        "url": req.url,
    }

    create_result = run_command(
        [
            str(PYTHON),
            str(CREATE_RUN),
            "--task-type",
            TASK_TYPE,
            "--input-json",
            json.dumps(input_payload, ensure_ascii=False),
        ]
    )

    if create_result.returncode != 0:
        return {
            "ok": False,
            "stage": "create_run",
            "content": "",
            "summary": "",
            "stdout": create_result.stdout,
            "stderr": create_result.stderr,
        }

    try:
        create_data = json.loads(create_result.stdout)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "stage": "create_run",
            "content": "",
            "summary": "",
            "error": f"create_run.py did not return valid JSON: {exc}",
            "stdout": create_result.stdout,
            "stderr": create_result.stderr,
        }

    run_id = create_data.get("run_id")

    if not run_id:
        return {
            "ok": False,
            "stage": "create_run",
            "content": "",
            "summary": "",
            "error": "create_run.py did not return run_id",
            "stdout": create_result.stdout,
            "stderr": create_result.stderr,
        }

    execute_result = run_command(
        [
            str(PYTHON),
            str(EXECUTE_TASK),
            "--run-id",
            str(run_id),
        ]
    )

    if execute_result.returncode != 0:
        return {
            "ok": False,
            "stage": "backend_execute_task",
            "run_id": run_id,
            "content": "",
            "summary": "",
            "stdout": execute_result.stdout,
            "stderr": execute_result.stderr,
        }

    html = get_rendered_result(run_id)

    if not html:
        return {
            "ok": False,
            "stage": "render_result",
            "run_id": run_id,
            "content": "",
            "summary": "",
            "error": "No rendered result found",
            "stdout": execute_result.stdout,
            "stderr": execute_result.stderr,
        }

    return {
        "ok": True,
        "run_id": run_id,
        "kind": "summary",
        "format": "html",
        "content": html,
        "summary": html,
        "stdout": execute_result.stdout,
        "stderr": execute_result.stderr,
    }
