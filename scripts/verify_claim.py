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

RELATIONSHIP_MAP = {
    "FOUND_SUPPORTING_EVIDENCE": "FOUND_SUPPORTING_EVIDENCE",
    "FOUND_CONTRADICTING_EVIDENCE": "FOUND_CONTRADICTING_EVIDENCE",
    "NO_SUPPORTING_EVIDENCE_FOUND": "NO_SUPPORTING_EVIDENCE_FOUND",
    "UNCLEAR_FROM_TRANSCRIPT": "UNCLEAR_FROM_TRANSCRIPT",
    "SUPPORTED": "FOUND_SUPPORTING_EVIDENCE",
    "SUPPORTED_BY_TRANSCRIPT": "FOUND_SUPPORTING_EVIDENCE",
    "CONTRADICTED": "FOUND_CONTRADICTING_EVIDENCE",
    "CONTRADICTED_BY_TRANSCRIPT": "FOUND_CONTRADICTING_EVIDENCE",
    "NOT_IN_TRANSCRIPT": "NO_SUPPORTING_EVIDENCE_FOUND",
    "NOT_FOUND_IN_TRANSCRIPT": "NO_SUPPORTING_EVIDENCE_FOUND",
    "UNCLEAR": "UNCLEAR_FROM_TRANSCRIPT",
}


def verify_one(conn, run_id: str, claim_id: str) -> None:
    step = get_step(conn, "verify_claim")
    claim = conn.execute("SELECT * FROM claims WHERE run_id=? AND claim_id=?", (run_id, claim_id)).fetchone()
    if claim is None:
        raise SystemExit(f"No claim {claim_id} for run_id {run_id}")
    transcript = conn.execute("SELECT text FROM transcripts WHERE run_id=? ORDER BY created_at DESC LIMIT 1", (run_id,)).fetchone()
    if transcript is None:
        raise SystemExit(f"No transcript for run_id {run_id}")

    claim_json = json.dumps({
        "claim_id": claim["claim_id"],
        "claim": claim["claim_text"],
        "summary_item_id": claim["summary_item_id"],
        "summary_context": claim["summary_context"],
        "claim_source_text": claim["claim_source_text"],
    }, ensure_ascii=False, indent=2)
    prompt = step["template"].replace("{claim_json}", claim_json).replace("{transcript}", transcript["text"])

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
    except Exception as exc:
        error = str(exc)
        parsed = {
            "claim": claim["claim_text"],
            "transcript_relationship": "UNCLEAR_FROM_TRANSCRIPT",
            "reason": f"Verification failed: {exc}",
            "suggested_fix": "",
        }
    finally:
        record_model_call(
            conn,
            run_id=run_id,
            step_name="verify_claim",
            model_id=step["model_id"],
            prompt_id=step["prompt_id"],
            input_ref=claim_id,
            input_sha256=sha256_text(claim_json + transcript["text"]),
            rendered_prompt_sha256=sha256_text(prompt),
            raw_response=raw,
            parsed_json=jdump(parsed) if parsed else "",
            error=error,
            started_at=started,
            ended_at=now_utc(),
        )

    relationship = RELATIONSHIP_MAP.get(str(parsed.get("transcript_relationship", "")).strip(), "UNCLEAR_FROM_TRANSCRIPT")
    verification_id = new_id("verification")
    conn.execute(
        """
        INSERT INTO verifications(
            verification_id, claim_id, run_id, transcript_relationship,
            reason, suggested_fix, raw_response, parsed_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            verification_id, claim_id, run_id, relationship,
            str(parsed.get("reason", "")), str(parsed.get("suggested_fix", "")),
            raw, jdump(parsed), now_utc(),
        ),
    )
    conn.commit()
    print(verification_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify one claim, or all unverified claims for a run_id.")
    parser.add_argument("--db", default="youtube_summarizer.sqlite")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--claim-id", default="")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    configure_logging()
    conn = connect(args.db)
    init_db(conn)

    if args.all:
        rows = conn.execute(
            """
            SELECT c.claim_id FROM claims c
            WHERE c.run_id=? AND NOT EXISTS (
                SELECT 1 FROM verifications v WHERE v.claim_id = c.claim_id
            )
            ORDER BY c.ordinal
            """,
            (args.run_id,),
        ).fetchall()
        for row in rows:
            verify_one(conn, args.run_id, row["claim_id"])
        conn.execute("UPDATE runs SET status='claims_verified', updated_at=? WHERE run_id=?", (now_utc(), args.run_id))
        conn.commit()
        print(f"Verified {len(rows)} claims")
    elif args.claim_id:
        verify_one(conn, args.run_id, args.claim_id)
    else:
        raise SystemExit("Use --claim-id CLAIM_ID or --all")


if __name__ == "__main__":
    main()
