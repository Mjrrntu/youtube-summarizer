#!/usr/bin/env python3

import sys
import requests
from pathlib import Path


def read_text_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text_file(path: str, content: str) -> None:
    Path(path).write_text(content, encoding="utf-8")


def build_prompt(transcript: str) -> str:
    return f"""
You are creating study notes from a YouTube video transcript.

Provide:

# Main Topic

# Key Points

# Conclusions

# Practical Takeaways

# TL;DR

Requirements:
- Use clear English.
- Be factual.
- Do not add information that is not present in the transcript.
- Prefer concise bullet points.
- Preserve important names, places, numbers, and claims.
- If the transcript is unclear, say so rather than guessing.

Transcript:

{transcript}
"""


def summarize_with_ollama(transcript: str, ai_model: str) -> str:
    prompt = build_prompt(transcript)

    print(f"Ollama model: {ai_model}")

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": ai_model,
            "prompt": prompt,
            "stream": False,
        },
        timeout=3600,
    )

    print("HTTP:", response.status_code)

    if response.status_code != 200:
        print(response.text[:1000])

    response.raise_for_status()
    return response.json()["response"]


def usage() -> None:
    print(
        """
Usage:

python3 summarize_transcript.py <transcript-file> [ai-model] [output-file]

Examples:

python3 summarize_transcript.py transcript.txt qwen2.5:32b summary-qwen.md

python3 summarize_transcript.py transcript.txt gpt-oss:20b summary-gptoss.md

python3 summarize_transcript.py transcript.txt deepseek-r1:32b summary-deepseek.md
"""
    )


def main() -> None:
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    transcript_file = sys.argv[1]
    ai_model = sys.argv[2] if len(sys.argv) > 2 else "qwen2.5:32b"
    output_file = sys.argv[3] if len(sys.argv) > 3 else "summary.md"

    transcript = read_text_file(transcript_file)

    print(f"Transcript : {transcript_file}")
    print(f"Characters : {len(transcript):,}")
    print(f"Output     : {output_file}")

    summary = summarize_with_ollama(transcript, ai_model)

    write_text_file(output_file, summary)

    print()
    print("Done.")
    print(f"Saved: {output_file}")


if __name__ == "__main__":
    main()
