#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from yts_core.db import connect, get_step, init_db, jdump, new_id, record_model_call
from yts_core.hashutil import sha256_text
from yts_core.json_utils import extract_json
from yts_core.llm import ollama_generate
from yts_core.logging_config import configure_logging
from yts_core.timeutil import now_utc


def flatten_summary(summary_json: dict) -> tuple[str, list[dict]]:
    parts: list[str] = []
    items: list[dict] = []
    pos = 0
    ordinal = 1

    title = str(summary_json.get("title", "")).strip()
    if title:
        header = f"# {title}\n\n"
        parts.append(header)
        pos += len(header)

    for s_idx, section in enumerate(summary_json.get("sections", []), start=1):
        section_id = str(section.get("section_id") or f"sec_{s_idx:03d}")
        section_title = str(section.get("title") or f"Section {s_idx}").strip()
        section_header = f"## {section_title}\n\n"
        parts.append(section_header)
        pos += len(section_header)

        for item in section.get("items", []):
            item_id = str(item.get("summary_item_id") or f"sum_{ordinal:03d}")
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            bullet = f"- {text}\n"
            start = pos + 2
            end = start + len(text)
            parts.append(bullet)
            pos += len(bullet)
            items.append({
                "summary_item_id": item_id,
                "section_id": section_id,
                "section_title": section_title,
                "ordinal": ordinal,
                "text": text,
                "start_char": start,
                "end_char": end,
            })
            ordinal += 1
        parts.append("\n")
        pos += 1

    tldr = summary_json.get("tldr", [])
    if tldr:
        parts.append("## TL;DR\n\n")
        pos += len("## TL;DR\n\n")
        for takeaway in tldr:
            text = str(takeaway).strip()
            if text:
                parts.append(f"- {text}\n")
                pos += len(text) + 3

    return "".join(parts).strip() + "\n", items


def main() -> None:
    parser = argparse.ArgumentParser(description="Run summarize step for a run_id.")
    parser.add_argument("--db", default="youtube_summarizer.sqlite")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    logger = configure_logging()
    conn = connect(args.db)
    init_db(conn)
    step = get_step(conn, "summarize")

    transcript_row = conn.execute("SELECT text FROM transcripts WHERE run_id = ? ORDER BY created_at DESC LIMIT 1", (args.run_id,)).fetchone()
    if transcript_row is None:
        raise SystemExit(f"No transcript for run_id {args.run_id}")
    transcript = transcript_row["text"]

    prompt = step["template"].replace("{transcript}", transcript)
    started = now_utc()
    error = ""
    parsed = {}
    raw = ""
    try:
        raw = ollama_generate(
            model=step["model_name"],
            prompt=prompt,
            temperature=float(step["temperature"]),
            num_ctx=int(step["num_ctx"]),
            expects_json=bool(step["expects_json"]),
        )
        parsed = extract_json(raw)
    except Exception as exc:
        error = str(exc)
        logger.exception("summarize failed")
        raise
    finally:
        record_model_call(
            conn,
            run_id=args.run_id,
            step_name="summarize",
            model_id=step["model_id"],
            prompt_id=step["prompt_id"],
            input_ref="transcript",
            input_sha256=sha256_text(transcript),
            rendered_prompt_sha256=sha256_text(prompt),
            raw_response=raw,
            parsed_json=jdump(parsed) if parsed else "",
            error=error,
            started_at=started,
            ended_at=now_utc(),
        )

    summary_text, items = flatten_summary(parsed)
    summary_id = new_id("summary")
    conn.execute(
        "INSERT INTO summaries(summary_id, run_id, text, raw_response, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (summary_id, args.run_id, summary_text, raw, jdump(parsed), now_utc()),
    )
    for item in items:
        conn.execute(
            """
            INSERT INTO summary_items(summary_item_id, summary_id, run_id, section_id, section_title, ordinal, text, start_char, end_char)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["summary_item_id"], summary_id, args.run_id, item["section_id"], item["section_title"],
                item["ordinal"], item["text"], item["start_char"], item["end_char"],
            ),
        )
    conn.execute("UPDATE runs SET status='summarized', updated_at=? WHERE run_id=?", (now_utc(), args.run_id))
    conn.commit()
    print(summary_id)


if __name__ == "__main__":
    main()
