from __future__ import annotations

import json
import re
from typing import Any


def extract_json(text: str) -> Any:
    """Extract JSON from raw LLM output, including accidental markdown fences."""
    text = text.strip()

    fence_match = re.search(
        r"```(?:json)?\s*(.*?)\s*```",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start_obj = text.find("{")
    end_obj = text.rfind("}")
    if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
        return json.loads(text[start_obj : end_obj + 1])

    start_arr = text.find("[")
    end_arr = text.rfind("]")
    if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
        return json.loads(text[start_arr : end_arr + 1])

    raise ValueError("Model did not return valid JSON")


def dumps(data: Any, *, pretty: bool = True) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2 if pretty else None)
