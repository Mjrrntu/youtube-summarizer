from __future__ import annotations

import requests


def ollama_generate(
    *,
    model: str,
    prompt: str,
    temperature: float,
    num_ctx: int,
    expects_json: bool = False,
    timeout: int = 1800,
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_ctx": num_ctx,
        },
    }
    if expects_json:
        payload["format"] = "json"

    response = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()["response"]
