#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from yts_core.db import connect, init_db

STYLE = """
body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; max-width: 1100px; margin: 2rem auto; padding: 0 1rem; line-height: 1.55; }
.stage { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; margin: 1rem 0 2rem; }
.node { border: 1px solid #bbb; border-radius: 999px; padding: .35rem .75rem; background: #f8f8f8; }
.arrow { color: #777; }
.summary-item { padding: .5rem .75rem; border-left: 4px solid #ddd; margin: .5rem 0; }
.summary-item.caution { background: #fff3e0; border-left-color: #e69500; }
.summary-item.review { background: #ffe8e8; border-left-color: #cc3333; }
.summary-item.normal { background: #fff; }
details { margin: .5rem 0; }
pre { white-space: pre-wrap; background: #f6f6f6; padding: .75rem; overflow-x: auto; }
.badge { font-size: .85em; border: 1px solid #aaa; border-radius: .3rem; padding: .1rem .35rem; margin-left: .35rem; }
.badge.normal { background: #eee; }
.badge.caution { background: #ffe0a6; }
.badge.review { background: #ffc4c4; }
"""


def risk_for_item(annotations: list[dict]) -> str:
    ranks = {"normal": 0, "caution": 1, "review": 2}
    risk = "normal"
    for ann in annotations:
        current = str(ann.get("display_risk", "normal"))
        if ranks.get(current, 0) > ranks.get(risk, 0):
            risk = current
    return risk


def main() -> None:
    parser = argparse.ArgumentParser(description="Render audited HTML output for a run_id.")
    parser.add_argument("--db", default="youtube_summarizer.sqlite")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", default="exports/summary.html")
    args = parser.parse_args()

    conn = connect(args.db)
    init_db(conn)

    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (args.run_id,)).fetchone()
    if run is None:
        raise SystemExit(f"No run {args.run_id}")
    summary = conn.execute("SELECT * FROM summaries WHERE run_id=? ORDER BY created_at DESC LIMIT 1", (args.run_id,)).fetchone()
    if summary is None:
        raise SystemExit(f"No summary for run {args.run_id}")

    items = conn.execute("SELECT * FROM summary_items WHERE summary_id=? ORDER BY ordinal", (summary["summary_id"],)).fetchall()
    annotations_by_item: dict[str, list[dict]] = {}
    for row in conn.execute("SELECT * FROM annotations WHERE run_id=?", (args.run_id,)).fetchall():
        annotations_by_item.setdefault(row["summary_item_id"], []).append(dict(row))

    claims_by_item: dict[str, list[dict]] = {}
    for row in conn.execute(
        """
        SELECT c.*, v.transcript_relationship, v.reason AS verification_reason
        FROM claims c
        LEFT JOIN verifications v ON v.claim_id = c.claim_id
        WHERE c.run_id=?
        ORDER BY c.ordinal
        """,
        (args.run_id,),
    ).fetchall():
        claims_by_item.setdefault(row["summary_item_id"], []).append(dict(row))

    counts = conn.execute(
        """
        SELECT transcript_relationship, COUNT(*) AS count
        FROM verifications WHERE run_id=? GROUP BY transcript_relationship
        """,
        (args.run_id,),
    ).fetchall()

    parts = ["<!doctype html><html><head><meta charset='utf-8'><title>Annotated summary</title>", f"<style>{STYLE}</style></head><body>"]
    parts.append(f"<h1>{html.escape(run['video_title'] or 'Annotated summary')}</h1>")
    parts.append("<p><strong>Scope:</strong> This page reports whether summary claims are supported by the transcript. It does not determine objective truth.</p>")
    parts.append("<div class='stage'><span class='node'>Transcript</span><span class='arrow'>→</span><span class='node'>Summary</span><span class='arrow'>→</span><span class='node'>Claims</span><span class='arrow'>→</span><span class='node'>Verification</span><span class='arrow'>→</span><span class='node'>Annotated result</span></div>")

    parts.append("<h2>Run metadata</h2><pre>")
    parts.append(html.escape(json.dumps(dict(run), ensure_ascii=False, indent=2)))
    parts.append("</pre>")

    parts.append("<h2>Verification summary</h2><ul>")
    for c in counts:
        parts.append(f"<li>{html.escape(c['transcript_relationship'])}: {c['count']}</li>")
    parts.append("</ul>")

    current_section = None
    parts.append("<h2>Annotated summary</h2>")
    for item in items:
        if item["section_title"] != current_section:
            current_section = item["section_title"]
            parts.append(f"<h3>{html.escape(current_section)}</h3>")
        anns = annotations_by_item.get(item["summary_item_id"], [])
        risk = risk_for_item(anns)
        parts.append(f"<div class='summary-item {risk}'>")
        parts.append(f"<p>{html.escape(item['text'])}<span class='badge {risk}'>{html.escape(risk)}</span></p>")
        related_claims = claims_by_item.get(item["summary_item_id"], [])
        if related_claims:
            parts.append("<details><summary>View claims and verification</summary>")
            for claim in related_claims:
                parts.append("<pre>")
                parts.append(html.escape(json.dumps({
                    "claim_id": claim.get("claim_id"),
                    "claim": claim.get("claim_text"),
                    "claim_source_text": claim.get("claim_source_text"),
                    "claim_span": {"start_char": claim.get("start_char"), "end_char": claim.get("end_char")},
                    "transcript_relationship": claim.get("transcript_relationship"),
                    "reason": claim.get("verification_reason"),
                }, ensure_ascii=False, indent=2)))
                parts.append("</pre>")
            parts.append("</details>")
        parts.append("</div>")

    parts.append("<h2>Audit links</h2>")
    parts.append("<p>Use the SQLite database to inspect full input, prompt, model call, and output history. Suggested future UI buttons: View Input, View Prompt, View Output.</p>")
    parts.append("</body></html>")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
