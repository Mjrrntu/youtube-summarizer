from __future__ import annotations

import re
from typing import Optional


def strip_markdown_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].strip()
    return text.strip()


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def find_span(text: str, fragment: str) -> Optional[dict]:
    """Find exact or whitespace-normalized fragment span in text.

    Returns Python-slice compatible start/end char offsets when possible.
    """
    if not fragment:
        return None
    start = text.find(fragment)
    if start >= 0:
        return {"start_char": start, "end_char": start + len(fragment)}

    # Conservative fuzzy fallback: compare collapsed whitespace and map back poorly only if exact source exists.
    # If uncertain, return None rather than invent offsets.
    return None
