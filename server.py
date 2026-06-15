#!/usr/bin/env python3

import json
import pathlib
import subprocess

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


PROJECT_DIR = pathlib.Path.home() / "git" / "youtube-summarizer"
PYTHON = PROJECT_DIR / ".venv" / "bin" / "python"
ENTRYPOINT = PROJECT_DIR / "scripts" / "summarize_url.py"


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class SummarizeRequest(BaseModel):
    url: str


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/summarize")
def summarize(req: SummarizeRequest):
    result = subprocess.run(
        [
            str(PYTHON),
            str(ENTRYPOINT),
            "--url",
            req.url,
        ],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=7200,
    )

    if result.returncode != 0:
        return {
            "ok": False,
            "content": "",
            "summary": "",
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "content": "",
            "summary": "",
            "error": f"Backend did not return valid JSON: {exc}",
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
