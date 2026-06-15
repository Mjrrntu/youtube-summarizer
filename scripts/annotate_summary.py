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

DEFAULT_MAPPING = {
    "FOUND_SUPPORTING_EVIDENCE": ("strong", "normal"),
    "FOUND_CONTRADICTING_EVIDENCE": ("contradicted", "review"),
    "NO_SUPPORTING_EVIDENCE_FOUND": ("missing", "review"),
    "UNCLEAR_FROM_TRANSCRIPT": ("unclear", "caution"),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Annotate summary items based on verifications.")
    parser.add_argument("--db", default="youtube_summarizer.sqlite")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--deterministic", action="store_true", help="Skip AI annotation and use direct status mapping")
    args = parser.parse_args()

    configure_logging()
    conn = connect(args.db)
    init_db(conn)

    rows = conn.execute(
        """
        SELECT c.claim_id, c.summary_item_id, c.claim_text, v.transcript_relationship, v.reason
        FROM claims c
        JOIN verifications v ON v.claim_id = c.claim_id
        WHERE c.run_id=?
        ORDER BY c.ordinal
        """,
        (args.run_id,),
    ).fetchall()

    annotations = []
    if args.deterministic:
        for row in rows:
            evidence_strength, display_risk = DEFAULT_MAPPING.get(row["transcript_relationship"], ("unclear", "caution"))
            annotations.append({
                "summary_item_id": row["summary_item_id"],
                "claim_id": row["claim_id"],
                "evidence_strength": evidence_strength,
                "display_risk": display_risk,
                "reason": row["reason"],
            })
    else:
        step = get_step(conn, "annotate_summary")
        annotation_input = {
            "run_id": args.run_id,
            "items": [dict(row) for row in rows],
        }
        annotation_input_json = json.dumps(annotation_input, ensure_ascii=False, indent=2)
        prompt = step["template"].replace("{annotation_input_json}", annotation_input_json)
        started = now_utc()
        raw = ""
        parsed = {}
        error = ""
        try:
            raw = ollama_generate(
                model=step["model_name"],
                prompt=prompt,
                temperature=float(step["temperature"]),
                num_ctx=int(step["num_ctx"]),
                expects_json=bool(step["expects_json"]),
            )
            parsed = extract_json(raw)
            annotations = parsed.get("annotations", []) if isinstance(parsed, dict) else []
        except Exception as exc:
            error = str(exc)
            # Safe fallback: direct deterministic mapping.
            for row in rows:
                evidence_strength, display_risk = DEFAULT_MAPPING.get(row["transcript_relationship"], ("unclear", "caution"))
                annotations.append({
                    "summary_item_id": row["summary_item_id"],
                    "claim_id": row["claim_id"],
                    "evidence_strength": evidence_strength,
                    "display_risk": display_risk,
                    "reason": row["reason"],
                })
        finally:
            record_model_call(
                conn,
                run_id=args.run_id,
                step_name="annotate_summary",
                model_id=step["model_id"],
                prompt_id=step["prompt_id"],
                input_ref="verifications",
                input_sha256=sha256_text(annotation_input_json),
                rendered_prompt_sha256=sha256_text(prompt),
                raw_response=raw,
                parsed_json=jdump(parsed) if parsed else "",
                error=error,
                started_at=started,
                ended_at=now_utc(),
            )

    inserted = 0
    for item in annotations:
        if not isinstance(item, dict):
            continue
        summary_item_id = str(item.get("summary_item_id", ""))
        claim_id = item.get("claim_id") or None
        evidence_strength = str(item.get("evidence_strength", "unclear"))
        display_risk = str(item.get("display_risk", "caution"))
        reason = str(item.get("reason", ""))
        if not summary_item_id:
            continue
        conn.execute(
            """
            INSERT INTO annotations(annotation_id, run_id, summary_item_id, claim_id, evidence_strength, display_risk, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id("annotation"), args.run_id, summary_item_id, claim_id, evidence_strength, display_risk, reason, now_utc()),
        )
        inserted += 1

    conn.execute("UPDATE runs SET status='annotated', updated_at=? WHERE run_id=?", (now_utc(), args.run_id))
    conn.commit()
    print(f"Inserted {inserted} annotations")


if __name__ == "__main__":
    main()
