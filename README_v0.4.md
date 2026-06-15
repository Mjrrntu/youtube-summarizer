# YouTube Summarizer v0.4 scaffold

This is a v0.4 refactor scaffold for an evidence-aware summarization pipeline.

## Core principle

The tool does **not** determine objective truth. It records and displays the relationship between summary claims and the provided transcript.

In short:

> Report evidence, not truth.

## Pipeline

```text
Transcript
  -> Summary JSON
  -> Claims
  -> Claim verification
  -> Evidence annotations
  -> HTML output
```

## Main changes from the current scripts

- `curate_summary.py` is split into separate stages:
  - `scripts/collect_claims.py`
  - `scripts/verify_claim.py`
  - `scripts/annotate_summary.py`
- Prompts are seeded into SQLite instead of being embedded in Python source files.
- Models and step parameters are stored in SQLite.
- AI outputs, raw responses, parsed JSON, and audit metadata are stored in SQLite.
- Debug logging uses rotating logs instead of unbounded debug files.
- HTML is a render/export artifact, not the internal source of truth.

## Files

```text
yts_core/db.py               SQLite schema and helpers
yts_core/default_prompts.py  Seed prompts
yts_core/llm.py              Ollama API wrapper
yts_core/json_utils.py       JSON extraction helpers
yts_core/logging_config.py   Rotating logging setup

scripts/init_db.py           Create schema and seed prompts/models
scripts/create_run.py        Create run from transcript file
scripts/summarize.py         Transcript -> summary + summary_items
scripts/collect_claims.py    Summary items -> claims
scripts/verify_claim.py      One claim or all claims -> verifications
scripts/annotate_summary.py  Verifications -> annotations
scripts/render_html.py       DB -> human-readable HTML
scripts/export_run_json.py   Full audit trail export
scripts/run_pipeline.py      Convenience runner
```

## Quick start

From this directory:

```bash
python scripts/init_db.py --model gemma3:27b

RUN_ID=$(python scripts/create_run.py \
  --transcript transcript.txt \
  --transcript-source youtube_captions \
  --source-url "https://youtube.com/watch?v=..." \
  --video-id "..." \
  --video-title "...")

python scripts/summarize.py --run-id "$RUN_ID"
python scripts/collect_claims.py --run-id "$RUN_ID"
python scripts/verify_claim.py --run-id "$RUN_ID" --all
python scripts/annotate_summary.py --run-id "$RUN_ID"
python scripts/render_html.py --run-id "$RUN_ID" --output exports/summary.html
```

Or:

```bash
python scripts/run_pipeline.py \
  --transcript transcript.txt \
  --transcript-source youtube_captions \
  --model gemma3:27b \
  --output-html exports/summary.html
```

## SQLite as source of truth

The database stores:

- prompts
- models
- pipeline step parameters
- runs
- transcripts
- summaries
- summary items
- claims
- verifications
- annotations
- model calls, including raw response and rendered prompt hash

Filesystem output is intentionally limited to:

- transcript files when useful
- HTML exports
- optional JSON exports
- rotating logs

## Important design notes

- Use IDs as keys, not text matching:
  - `run_id`
  - `summary_id`
  - `summary_item_id`
  - `claim_id`
  - `verification_id`
  - `annotation_id`
- `claim_span` uses Python-slice-compatible offsets:
  - `start_char`
  - `end_char`
- The HTML renderer currently highlights at summary-item level. Claim-span-level highlighting can be added later using the stored offsets.
- `annotate_summary.py --deterministic` can be used to skip the AI annotator and directly map verification statuses to display risk.

## Known limitations

- Does not control the universe as originally intended.
- Does not fact-check the universe.
- Does not determine ultimate truth.
- Does not yet include the future UI buttons: View Input, View Prompt, View Output, Edit Prompt, Upload Input.

## Roadmap note

`v0.5+`: Consider controlled expansion into universal governance.
