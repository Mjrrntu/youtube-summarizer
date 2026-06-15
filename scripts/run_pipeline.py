#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(cmd: list[str]) -> str:
    print("$ " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Convenience runner for v0.4 pipeline.")
    parser.add_argument("--db", default="youtube_summarizer.sqlite")
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--transcript-source", default="unknown", choices=["youtube_captions", "whisper_generated", "unknown"])
    parser.add_argument("--source-url", default="")
    parser.add_argument("--video-id", default="")
    parser.add_argument("--video-title", default="")
    parser.add_argument("--channel", default="")
    parser.add_argument("--published-at", default="")
    parser.add_argument("--model", default="gemma3:27b")
    parser.add_argument("--output-html", default="exports/summary.html")
    args = parser.parse_args()

    run([PYTHON, "scripts/init_db.py", "--db", args.db, "--model", args.model])
    run_id = run([
        PYTHON, "scripts/create_run.py", "--db", args.db,
        "--transcript", args.transcript,
        "--transcript-source", args.transcript_source,
        "--source-url", args.source_url,
        "--video-id", args.video_id,
        "--video-title", args.video_title,
        "--channel", args.channel,
        "--published-at", args.published_at,
    ])
    print(f"RUN_ID={run_id}")
    run([PYTHON, "scripts/summarize.py", "--db", args.db, "--run-id", run_id])
    run([PYTHON, "scripts/collect_claims.py", "--db", args.db, "--run-id", run_id])
    run([PYTHON, "scripts/verify_claim.py", "--db", args.db, "--run-id", run_id, "--all"])
    run([PYTHON, "scripts/annotate_summary.py", "--db", args.db, "--run-id", run_id])
    run([PYTHON, "scripts/render_html.py", "--db", args.db, "--run-id", run_id, "--output", args.output_html])
    print(f"Done. HTML: {args.output_html}")


if __name__ == "__main__":
    main()
