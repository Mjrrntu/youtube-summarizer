#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from yts_core.db import connect, init_db


def rows(conn, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a full run audit trail as JSON.")
    parser.add_argument("--db", default="youtube_summarizer.sqlite")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", default="exports/run.json")
    args = parser.parse_args()

    conn = connect(args.db)
    init_db(conn)
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (args.run_id,)).fetchone()
    if run is None:
        raise SystemExit(f"No run {args.run_id}")

    data = {
        "run": dict(run),
        "transcripts": rows(conn, "SELECT transcript_id, run_id, source, path, sha256, created_at FROM transcripts WHERE run_id=?", (args.run_id,)),
        "summaries": rows(conn, "SELECT * FROM summaries WHERE run_id=?", (args.run_id,)),
        "summary_items": rows(conn, "SELECT * FROM summary_items WHERE run_id=? ORDER BY ordinal", (args.run_id,)),
        "claims": rows(conn, "SELECT * FROM claims WHERE run_id=? ORDER BY ordinal", (args.run_id,)),
        "verifications": rows(conn, "SELECT * FROM verifications WHERE run_id=?", (args.run_id,)),
        "annotations": rows(conn, "SELECT * FROM annotations WHERE run_id=?", (args.run_id,)),
        "model_calls": rows(conn, "SELECT * FROM model_calls WHERE run_id=? ORDER BY started_at", (args.run_id,)),
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
