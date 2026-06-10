#!/usr/bin/env python3

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import pathlib
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_DIR = pathlib.Path.home() / "git" / "youtube-summarizer"
PYTHON = PROJECT_DIR / ".venv" / "bin" / "python"


class SummarizeRequest(BaseModel):
    url: str
    whisper_model: str = "large-v3"
    ai_model: str = "gpt-oss:20b"
    device: str = "cuda"
    compute_type: str = "float16"
    cpu_threads: int = 24

@app.get("/health")
def health():
    return {
        "status": "ok"
    }

@app.post("/summarize")
def summarize(req: SummarizeRequest):
    ts = int(time.time())
    output_file = PROJECT_DIR / f"summary-{ts}.md"

    cmd = [
        str(PYTHON),
        str(PROJECT_DIR / "youtube_summary.py"),
        req.url,
        req.whisper_model,
        req.ai_model,
        req.device,
        req.compute_type,
        str(req.cpu_threads),
    ]

    result = subprocess.run(
        cmd,
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=7200,
    )

    summary_path = PROJECT_DIR / "summary.md"
    summary = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""

    output_file.write_text(summary, encoding="utf-8")

    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "summary": summary,
        "file": str(output_file),
    }
