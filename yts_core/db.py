from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Optional

from .timeutil import now_utc

DEFAULT_DB = "youtube_summarizer.sqlite"


def connect(db_path: str = DEFAULT_DB) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True) if Path(db_path).parent != Path('.') else None
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def jdump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def jload(text: Optional[str], default: Any = None) -> Any:
    if text is None or text == "":
        return default
    return json.loads(text)


SCHEMA = """
CREATE TABLE IF NOT EXISTS models (
    model_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'ollama',
    default_options_json TEXT NOT NULL DEFAULT '{}',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prompts (
    prompt_id TEXT PRIMARY KEY,
    step_name TEXT NOT NULL,
    version INTEGER NOT NULL,
    template TEXT NOT NULL,
    expects_json INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(step_name, version)
);

CREATE TABLE IF NOT EXISTS pipeline_steps (
    step_name TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id),
    model_id TEXT NOT NULL REFERENCES models(model_id),
    temperature REAL NOT NULL,
    num_ctx INTEGER NOT NULL,
    expects_json INTEGER NOT NULL DEFAULT 1,
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL DEFAULT 'youtube',
    source_url TEXT NOT NULL DEFAULT '',
    video_id TEXT NOT NULL DEFAULT '',
    video_title TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL DEFAULT '',
    transcript_source TEXT NOT NULL DEFAULT 'unknown',
    transcript_path TEXT NOT NULL DEFAULT '',
    transcript_sha256 TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'created',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transcripts (
    transcript_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'unknown',
    path TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS summaries (
    summary_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    raw_response TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS summary_items (
    summary_item_id TEXT PRIMARY KEY,
    summary_id TEXT NOT NULL REFERENCES summaries(summary_id) ON DELETE CASCADE,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    section_id TEXT NOT NULL DEFAULT '',
    section_title TEXT NOT NULL DEFAULT '',
    ordinal INTEGER NOT NULL,
    text TEXT NOT NULL,
    start_char INTEGER,
    end_char INTEGER
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    summary_id TEXT NOT NULL REFERENCES summaries(summary_id) ON DELETE CASCADE,
    summary_item_id TEXT NOT NULL REFERENCES summary_items(summary_item_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    claim_text TEXT NOT NULL,
    summary_context TEXT NOT NULL DEFAULT '',
    claim_source_text TEXT NOT NULL DEFAULT '',
    start_char INTEGER,
    end_char INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS verifications (
    verification_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    transcript_relationship TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    suggested_fix TEXT NOT NULL DEFAULT '',
    raw_response TEXT NOT NULL DEFAULT '',
    parsed_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS annotations (
    annotation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    summary_item_id TEXT NOT NULL REFERENCES summary_items(summary_item_id) ON DELETE CASCADE,
    claim_id TEXT REFERENCES claims(claim_id) ON DELETE SET NULL,
    evidence_strength TEXT NOT NULL,
    display_risk TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_calls (
    call_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    step_name TEXT NOT NULL,
    model_id TEXT NOT NULL REFERENCES models(model_id),
    prompt_id TEXT NOT NULL REFERENCES prompts(prompt_id),
    input_ref TEXT NOT NULL DEFAULT '',
    input_sha256 TEXT NOT NULL DEFAULT '',
    rendered_prompt_sha256 TEXT NOT NULL DEFAULT '',
    raw_response TEXT NOT NULL DEFAULT '',
    parsed_json TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def upsert_model(conn: sqlite3.Connection, model_id: str, name: str, *, provider: str = "ollama", options: Optional[dict] = None) -> None:
    conn.execute(
        """
        INSERT INTO models(model_id, name, provider, default_options_json, active, created_at)
        VALUES(?, ?, ?, ?, 1, ?)
        ON CONFLICT(model_id) DO UPDATE SET
            name=excluded.name,
            provider=excluded.provider,
            default_options_json=excluded.default_options_json,
            active=1
        """,
        (model_id, name, provider, jdump(options or {}), now_utc()),
    )
    conn.commit()


def upsert_prompt(conn: sqlite3.Connection, prompt_id: str, step_name: str, version: int, template: str, *, expects_json: bool = True) -> None:
    conn.execute(
        """
        INSERT INTO prompts(prompt_id, step_name, version, template, expects_json, active, created_at)
        VALUES(?, ?, ?, ?, ?, 1, ?)
        ON CONFLICT(step_name, version) DO UPDATE SET
            template=excluded.template,
            expects_json=excluded.expects_json,
            active=1
        """,
        (prompt_id, step_name, version, template, 1 if expects_json else 0, now_utc()),
    )
    conn.commit()


def upsert_step(conn: sqlite3.Connection, step_name: str, prompt_id: str, model_id: str, *, temperature: float, num_ctx: int, expects_json: bool = True) -> None:
    conn.execute(
        """
        INSERT INTO pipeline_steps(step_name, prompt_id, model_id, temperature, num_ctx, expects_json, enabled)
        VALUES(?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(step_name) DO UPDATE SET
            prompt_id=excluded.prompt_id,
            model_id=excluded.model_id,
            temperature=excluded.temperature,
            num_ctx=excluded.num_ctx,
            expects_json=excluded.expects_json,
            enabled=1
        """,
        (step_name, prompt_id, model_id, temperature, num_ctx, 1 if expects_json else 0),
    )
    conn.commit()


def get_step(conn: sqlite3.Connection, step_name: str) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT ps.*, p.template, p.prompt_id, p.expects_json AS prompt_expects_json,
               m.name AS model_name, m.provider, m.default_options_json
        FROM pipeline_steps ps
        JOIN prompts p ON p.prompt_id = ps.prompt_id
        JOIN models m ON m.model_id = ps.model_id
        WHERE ps.step_name = ? AND ps.enabled = 1
        """,
        (step_name,),
    ).fetchone()
    if row is None:
        raise KeyError(f"No enabled pipeline step found: {step_name}")
    return row


def record_model_call(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    step_name: str,
    model_id: str,
    prompt_id: str,
    input_ref: str,
    input_sha256: str,
    rendered_prompt_sha256: str,
    raw_response: str,
    parsed_json: str = "",
    error: str = "",
    started_at: str,
    ended_at: str,
) -> str:
    call_id = new_id("call")
    conn.execute(
        """
        INSERT INTO model_calls(
            call_id, run_id, step_name, model_id, prompt_id, input_ref,
            input_sha256, rendered_prompt_sha256, raw_response, parsed_json,
            error, started_at, ended_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            call_id, run_id, step_name, model_id, prompt_id, input_ref,
            input_sha256, rendered_prompt_sha256, raw_response, parsed_json,
            error, started_at, ended_at,
        ),
    )
    conn.commit()
    return call_id
