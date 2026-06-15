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
from yts_core.text_utils import find_span
from yts_core.timeutil import now_utc


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect claims from latest summary for a run_id.")
    parser.add_argument("--db", default="youtube_summarizer.sqlite")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    logger = configure_logging()
    conn = connect(args.db)
    init_db(conn)
    step = get_step(conn, "collect_claims")

    summary = conn.execute("SELECT * FROM summaries WHERE run_id=? ORDER BY created_at DESC LIMIT 1", (args.run_id,)).fetchone()
    if summary is None:
        raise SystemExit(f"No summary for run_id {args.run_id}")
    items = conn.execute("SELECT * FROM summary_items WHERE summary_id=? ORDER BY ordinal", (summary["summary_id"],)).fetchall()
    item_map = {row["summary_item_id"]: row for row in items}
    summary_payload = {
        "summary_id": summary["summary_id"],
        "items": [
            {
                "summary_item_id": row["summary_item_id"],
                "section_title": row["section_title"],
                "text": row["text"],
            }
            for row in items
        ],
    }
    summary_json = json.dumps(summary_payload, ensure_ascii=False, indent=2)
    prompt = step["template"].replace("{summary_json}", summary_json)

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
        logger.exception("collect_claims failed")
        raise
    finally:
        record_model_call(
            conn,
            run_id=args.run_id,
            step_name="collect_claims",
            model_id=step["model_id"],
            prompt_id=step["prompt_id"],
            input_ref=summary["summary_id"],
            input_sha256=sha256_text(summary_json),
            rendered_prompt_sha256=sha256_text(prompt),
            raw_response=raw,
            parsed_json=jdump(parsed) if parsed else "",
            error=error,
            started_at=started,
            ended_at=now_utc(),
        )

    claims = parsed.get("claims", []) if isinstance(parsed, dict) else []
    if not isinstance(claims, list):
        claims = []

    inserted = 0
    for ordinal, item in enumerate(claims, start=1):
        if not isinstance(item, dict):
            continue
        claim_text = str(item.get("claim", "")).strip()
        summary_item_id = str(item.get("summary_item_id", "")).strip()
        if not claim_text or summary_item_id not in item_map:
            continue
        summary_context = str(item.get("summary_context") or item_map[summary_item_id]["text"]).strip()
        source_fragment = str(item.get("claim_source_text", "")).strip()

        span = find_span(item_map[summary_item_id]["text"], source_fragment)
        if span is None:
            proposed_span = item.get("claim_span") if isinstance(item.get("claim_span"), dict) else {}
            start = proposed_span.get("start_char")
            end = proposed_span.get("end_char")
            if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(item_map[summary_item_id]["text"]):
                if not source_fragment or item_map[summary_item_id]["text"][start:end] == source_fragment:
                    span = {"start_char": start, "end_char": end}
        if span is None:
            span = {"start_char": None, "end_char": None}

        claim_id = f"claim_{ordinal:04d}"
        # Keep claim IDs stable within the run but avoid conflict if script is rerun.
        existing = conn.execute("SELECT claim_id FROM claims WHERE run_id=? AND claim_id=?", (args.run_id, claim_id)).fetchone()
        if existing:
            claim_id = new_id("claim")

        conn.execute(
            """
            INSERT INTO claims(
                claim_id, run_id, summary_id, summary_item_id, ordinal, claim_text,
                summary_context, claim_source_text, start_char, end_char, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                claim_id, args.run_id, summary["summary_id"], summary_item_id, ordinal,
                claim_text, summary_context, source_fragment,
                span["start_char"], span["end_char"], now_utc(),
            ),
        )
        inserted += 1

    conn.execute("UPDATE runs SET status='claims_collected', updated_at=? WHERE run_id=?", (now_utc(), args.run_id))
    conn.commit()
    print(f"Inserted {inserted} claims")


if __name__ == "__main__":
    main()
