import requests

def laske_ollama_tokenit(model: str, tiedostopolku: str) -> int:
    with open(tiedostopolku, "r", encoding="utf-8") as f:
        teksti = f.read()

    response = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json={
            "model": model,
            "prompt": teksti,
            "stream": False,
            "options": {
                "num_predict": 1
            }
        },
        timeout=1800,
    )
    response.raise_for_status()

    data = response.json()
    return data.get("prompt_eval_count", 0)

malli = "gemma3:27b"
tiedosto = "transcript.txt"

token_maara = laske_ollama_tokenit(malli, tiedosto)
print(f"Teksti vie {token_maara} tokenia Ollaman {malli} -mallilla.")
