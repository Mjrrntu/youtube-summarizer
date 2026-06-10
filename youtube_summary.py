#!/usr/bin/env python3

import re
import sys
import subprocess
import requests

from youtube_transcript_api import YouTubeTranscriptApi
from faster_whisper import WhisperModel


def get_video_id(url: str) -> str:
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if not match:
        raise ValueError(f"Videon ID:tä ei löytynyt URL:sta: {url}")
    return match.group(1)


def try_get_transcript(video_id: str) -> str | None:
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(
            video_id,
            languages=["fi", "en"],
        )

        return "\n".join(
            item.text
            for item in transcript
        )

    except Exception as e:
        print(f"YouTube-transkriptia ei löytynyt: {e}")
        return None

def download_audio(url: str) -> str:
    cmd = [
        "yt-dlp",
        "-f", "bestaudio",
        "-x",
        "--audio-format", "m4a",
        "-o", "audio.%(ext)s",
        url,
    ]

    subprocess.run(cmd, check=True)
    return "audio.m4a"


def transcribe_audio(
    audio_path: str,
    whisper_model: str,
    device: str,
    compute_type: str,
    cpu_threads: int,
) -> str:
    print(
        f"Ladataan Whisper-malli {whisper_model} "
        f"(device={device}, compute_type={compute_type}, cpu_threads={cpu_threads})"
    )

    model = WhisperModel(
        whisper_model,
        device=device,
        compute_type=compute_type,
        cpu_threads=cpu_threads,
    )

    segments, info = model.transcribe(audio_path, language=None)

    print(f"Tunnistettu kieli: {info.language} ({info.language_probability:.2f})")

    transcript_parts = []
    for segment in segments:
        transcript_parts.append(segment.text.strip())

    return "\n".join(transcript_parts)


def summarize_with_ollama(transcript: str, ai_model: str) -> str:
    print(f"Ollama model: {ai_model}")

    prompt = f"""
You are creating study notes from a YouTube video.

Provide:

# Main Topic

# Key Points

# Conclusions

# Practical Takeaways

# TL;DR

Be factual.
Do not add information not present in the transcript.
Use concise English.

Transcript:

{transcript}
"""

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


def main() -> None:
    if len(sys.argv) < 2:
        print(
            """
Käyttö:

python3 youtube_summary.py <youtube-url> [whisper_model] [ai_model] [device] [compute_type] [cpu_threads]

Esimerkki:

python3 youtube_summary.py "https://www.youtube.com/watch?v=SofikHvGMYs" large-v3 qwen2.5:32b cuda float16 24
"""
        )
        sys.exit(1)

    video_url = sys.argv[1]
    whisper_model = sys.argv[2] if len(sys.argv) > 2 else "medium"
    ai_model = sys.argv[3] if len(sys.argv) > 3 else "qwen2.5:32b"
    device = sys.argv[4] if len(sys.argv) > 4 else "cpu"
    compute_type = sys.argv[5] if len(sys.argv) > 5 else "int8"
    cpu_threads = int(sys.argv[6]) if len(sys.argv) > 6 else 24

    print("=" * 80)
    print("YouTube Summary Tool")
    print("=" * 80)
    print(f"Video URL     : {video_url}")
    print(f"Whisper Model : {whisper_model}")
    print(f"AI Model      : {ai_model}")
    print(f"Device        : {device}")
    print(f"Compute Type  : {compute_type}")
    print(f"CPU Threads   : {cpu_threads}")
    print()

    video_id = get_video_id(video_url)

    print("Haetaan YouTube-transkriptiota...")
    transcript = try_get_transcript(video_id)

    if transcript is None:
        print("Transkriptiota ei löytynyt. Ladataan ääniraita...")
        audio_path = download_audio(video_url)

        print("Tehdään paikallinen puheentunnistus...")
        transcript = transcribe_audio(
            audio_path,
            whisper_model,
            device,
            compute_type,
            cpu_threads,
        )

    with open("transcript.txt", "w", encoding="utf-8") as f:
        f.write(transcript)

    print(f"Transkriptio tallennettu transcript.txt ({len(transcript):,} merkkiä)")

    print()
    print("Tehdään yhteenveto...")

    summary = summarize_with_ollama(transcript, ai_model)

    with open("summary.md", "w", encoding="utf-8") as f:
        f.write(summary)

    print()
    print("=" * 80)
    print("VALMIS")
    print("=" * 80)
    print("Transkriptio : transcript.txt")
    print("Yhteenveto   : summary.md")


if __name__ == "__main__":
    main()
