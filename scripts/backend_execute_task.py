#!/usr/bin/env python3

import argparse
import json
import sqlite3
import subprocess
import html
import re
from pathlib import Path
from datetime import datetime, UTC
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import YouTubeTranscriptApi


DEFAULT_DB = "youtube_summary.db"

def utc_now():
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(Path(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def get_video_id(url: str) -> str:
    parsed = urlparse(url)

    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        return parsed.path.lstrip("/")

    return parse_qs(parsed.query).get("v", [""])[0]


def load_transcript(input_data: dict, previous_outputs: dict, step) -> dict:
    url = input_data.get("url")
    if not url:
        raise ValueError("Missing url in run input_contents")

    video_id = get_video_id(url)
    if not video_id:
        raise ValueError(f"Could not parse YouTube video id from url: {url}")

    ytt_api = YouTubeTranscriptApi()
    transcript_list = ytt_api.list(video_id)

    try:
        transcript_obj = transcript_list.find_transcript(["fi", "en"])
        transcript_source = "youtube_captions"
    except Exception:
        transcript_obj = transcript_list.find_generated_transcript(["fi", "en"])
        transcript_source = "youtube_generated_captions"

    fetched = transcript_obj.fetch()
    transcript_text = "\n".join(item.text for item in fetched)

    return {
        "output_contents": transcript_text,
        "metadata": {
            "ok": True,
            "source": transcript_source,
            "video_id": video_id,
            "language_code": getattr(transcript_obj, "language_code", None),
            "line_count": len(fetched),
            "char_count": len(transcript_text),
        },
    }


def get_run(conn: sqlite3.Connection, run_id: int):
    return conn.execute(
        """
        SELECT *
        FROM runs
        WHERE id = ?
        """,
        (run_id,),
    ).fetchone()


def get_task_steps(conn: sqlite3.Connection, task_type: str):
    return conn.execute(
        """
        SELECT
            td.*,
            p.prompt_name,
            p.prompt_text
        FROM task_definitions td
        LEFT JOIN prompts p ON p.id = td.prompt_id
        WHERE td.task_type = ?
          AND td.enabled = 1
        ORDER BY td.step_order
        """,
        (task_type,),
    ).fetchall()


def update_run_status(conn, run_id, status, error_text=None):
    conn.execute(
        """
        UPDATE runs
        SET status = ?,
            error_text = ?,
            row_updated_at = ?
        WHERE id = ?
        """,
        (status, error_text, utc_now(), run_id),
    )


def insert_step_result(
    conn,
    run_id: int,
    step,
    input_contents: dict,
    metadata: dict,
    output_contents: str,
    output_format: str,
    status: str,
    error_text: str | None = None,
):
    now = utc_now()

    conn.execute(
        """
        INSERT INTO run_step_results (
            run_id,
            step_order,
            step_name,
            step_handler,
            input_contents,
            metadata,
            output_contents,
            output_format,
            status,
            error_text,
            row_created_at,
            row_updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            step["step_order"],
            step["step_name"],
            step["step_handler"],
            json.dumps(input_contents, ensure_ascii=False),
            json.dumps(metadata, ensure_ascii=False),
            output_contents,
            output_format,
            status,
            error_text,
            now,
            now,
        ),
    )

def summarize(input_data: dict, previous_outputs: dict, step) -> dict:
    model_name = step["model_name"]
    prompt_text = step["prompt_text"]

    if not model_name:
        raise ValueError("summarize step is missing model_name")

    if not prompt_text:
        raise ValueError("summarize step is missing prompt_text")

    transcript_step = previous_outputs.get("load_transcript")

    if not transcript_step:
        raise ValueError("Missing previous output: load_transcript")

    transcript = transcript_step.get("output_contents", "").strip()

    if not transcript:
        raise ValueError("load_transcript output_contents is empty")

    full_prompt = prompt_text.replace("{{transcript}}", transcript)

    result = subprocess.run(
        [
            "ollama",
            "run",
            model_name,
            full_prompt,
        ],
        capture_output=True,
        text=True,
        timeout=7200,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ollama summarize failed")

    summary = result.stdout.strip()

    return {
        "output_contents": summary,
        "metadata": {
            "ok": True,
            "model": model_name,
            "prompt_id": step["prompt_id"],
            "prompt_name": step["prompt_name"],
            "input_step": "load_transcript",
            "char_count": len(summary),
        },
    }



def collect_claims(input_data: dict, previous_outputs: dict, step) -> dict:
    model_name = step["model_name"]
    prompt_text = step["prompt_text"]

    if not model_name:
        raise ValueError("collect_claims step is missing model_name")

    if not prompt_text:
        raise ValueError("collect_claims step is missing prompt_text")

    summary_step = previous_outputs.get("summarize")

    if not summary_step:
        raise ValueError("Missing previous output: summarize")

    summary = summary_step.get("output_contents", "").strip()

    if not summary:
        raise ValueError("summarize output_contents is empty")

    full_prompt = prompt_text.replace("{{summary}}", summary)

    result = subprocess.run(
        [
            "ollama",
            "run",
            model_name,
            full_prompt,
        ],
        capture_output=True,
        text=True,
        timeout=7200,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ollama collect_claims failed")

    claims_text = result.stdout.strip()

    return {
        "output_contents": claims_text,
        "metadata": {
            "ok": True,
            "model": model_name,
            "prompt_id": step["prompt_id"],
            "prompt_name": step["prompt_name"],
            "input_step": "summarize",
            "char_count": len(claims_text),
        },
    }


def verify_claims(input_data, previous_outputs, step):

    model_name = step["model_name"]
    prompt_text = step["prompt_text"]

    transcript_step = previous_outputs.get("load_transcript")
    claims_step = previous_outputs.get("collect_claims")

    if not transcript_step:
        raise ValueError("Missing load_transcript output")

    if not claims_step:
        raise ValueError("Missing collect_claims output")

    transcript = transcript_step["output_contents"]
    claims = claims_step["output_contents"]

    full_prompt = (
        prompt_text
        .replace("{{transcript}}", transcript)
        .replace("{{claims}}", claims)
    )

    result = subprocess.run(
        [
            "ollama",
            "run",
            model_name,
            full_prompt,
        ],
        capture_output=True,
        text=True,
        timeout=7200,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())

    verification_report = result.stdout.strip()

    return {
        "output_contents": verification_report,
        "metadata": {
            "ok": True,
            "model": model_name,
            "prompt_id": step["prompt_id"],
            "prompt_name": step["prompt_name"],
            "char_count": len(verification_report),
        },
    }


def annotate_summary(input_data: dict, previous_outputs: dict, step) -> dict:
    model_name = step["model_name"]
    prompt_text = step["prompt_text"]

    if not model_name:
        raise ValueError("annotate_summary step is missing model_name")

    if not prompt_text:
        raise ValueError("annotate_summary step is missing prompt_text")

    summary_step = previous_outputs.get("summarize")
    verification_step = previous_outputs.get("verify_claims")

    if not summary_step:
        raise ValueError("Missing previous output: summarize")

    if not verification_step:
        raise ValueError("Missing previous output: verify_claims")

    summary = summary_step.get("output_contents", "").strip()
    verification = verification_step.get("output_contents", "").strip()

    if not summary:
        raise ValueError("summarize output_contents is empty")

    if not verification:
        raise ValueError("verify_claims output_contents is empty")

    full_prompt = (
        prompt_text
        .replace("{{summary}}", summary)
        .replace("{{verification}}", verification)
    )

    result = subprocess.run(
        [
            "ollama",
            "run",
            model_name,
            full_prompt,
        ],
        capture_output=True,
        text=True,
        timeout=7200,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ollama annotate_summary failed")

    annotated_summary = result.stdout.strip()

    return {
        "output_contents": annotated_summary,
        "metadata": {
            "ok": True,
            "model": model_name,
            "prompt_id": step["prompt_id"],
            "prompt_name": step["prompt_name"],
            "input_steps": ["summarize", "verify_claims"],
            "char_count": len(annotated_summary),
        },
    }


ANSI_ESCAPE_RE = re.compile(
    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
)

def remove_rewritten_line_fragments(text: str) -> str:
    lines = text.splitlines()
    cleaned = []

    for line in lines:
        current = line.strip()

        if cleaned:
            previous = cleaned[-1].strip()

            # Jos edellinen rivi näyttää olevan seuraavan rivin alku,
            # esim. "Venäj" + "Venäjälle", poistetaan edellinen fragmentti.
            if previous and current.startswith(previous):
                cleaned[-1] = line
                continue

        cleaned.append(line)

    return "\n".join(cleaned)


def clean_for_render(text: str) -> str:
    text = ANSI_ESCAPE_RE.sub("", text)
    text = text.replace("\r", "")
    return text


def remove_wrapped_word_fragments(text: str) -> str:
    lines = text.splitlines()
    cleaned = []

    for line in lines:
        current = line.strip()

        if cleaned and current:
            previous = cleaned[-1]

            previous_words = previous.rstrip().split()
            current_words = current.split()

            if previous_words and current_words:
                prev_last = previous_words[-1]
                curr_first = current_words[0]

                # Esim:
                # "jos" + "jossa"
                # "ede" + "edelleen"
                # "merkittäv" + "merkittävä"
                if (
                    len(prev_last) >= 2
                    and len(curr_first) > len(prev_last)
                    and curr_first.startswith(prev_last)
                ):
                    previous_words[-1] = curr_first
                    cleaned[-1] = " ".join(previous_words)

                    rest = " ".join(current_words[1:])
                    if rest:
                        cleaned[-1] += " " + rest

                    continue

        cleaned.append(current)

    return "\n".join(cleaned)


def render_result(input_data, previous_outputs, step):
    annotated = previous_outputs["annotate_summary"]["output_contents"]

    return {
        "output_contents": annotated,
        "metadata": {
            "ok": True,
            "format": "markdown",
            "char_count": len(annotated),
        },
    }



HANDLERS = {
    "load_transcript": load_transcript,
    "summarize": summarize,
    "collect_claims": collect_claims,
    "verify_claims": verify_claims,
    "annotate_summary": annotate_summary,
    "render_result": render_result,
}



def main():
    parser = argparse.ArgumentParser(description="Execute a pipeline run.")
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--run-id", required=True, type=int)
    args = parser.parse_args()

    conn = connect(args.db)

    try:
        run = get_run(conn, args.run_id)
        if run is None:
            raise ValueError(f"Run {args.run_id} not found")

        run_input = json.loads(run["input_json"])
        steps = get_task_steps(conn, run["task_type"])

        update_run_status(conn, args.run_id, "running")
        conn.commit()

        previous_outputs = {}
        executed_steps = []

        for step in steps:
            step_handler = step["step_handler"]

            step_input = {
                "run_input": run_input,
                "previous_outputs": previous_outputs,
                "config": json.loads(step["config_json"] or "{}"),
                "prompt_name": step["prompt_name"],
                "prompt_text": step["prompt_text"],
                "model_name": step["model_name"],
            }

            handler = HANDLERS.get(step_handler)

            if handler is None:
                metadata = {
                    "ok": True,
                    "note": "dummy completed; handler not implemented yet",
                    "step_handler": step_handler,
                }
                output_contents = ""
                status = "completed"
                error_text = None
            else:
                result = handler(run_input, previous_outputs, step)
                metadata = result.get("metadata", {})
                output_contents = result.get("output_contents", "")
                status = "completed"
                error_text = None

            insert_step_result(
                conn=conn,
                run_id=args.run_id,
                step=step,
                input_contents=step_input,
                metadata=metadata,
                output_contents=output_contents,
                output_format=step["output_format"],
                status=status,
                error_text=error_text,
            )
            conn.commit()

            previous_outputs[step["step_name"]] = {
                "metadata": metadata,
                "output_contents": output_contents,
            }

            executed_steps.append(
                {
                    "step_order": step["step_order"],
                    "step_name": step["step_name"],
                    "step_handler": step_handler,
                    "status": status,
                }
            )

        update_run_status(conn, args.run_id, "completed")
        conn.commit()

        print(json.dumps({
            "ok": True,
            "run_id": args.run_id,
            "status": "completed",
            "steps": executed_steps,
        }, ensure_ascii=False, indent=2))

    except Exception as exc:
        try:
            update_run_status(conn, args.run_id, "failed", str(exc))
            conn.commit()
        except Exception:
            pass

        print(json.dumps({
            "ok": False,
            "run_id": args.run_id,
            "error": str(exc),
        }, ensure_ascii=False))
        raise SystemExit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
