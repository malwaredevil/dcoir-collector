from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

def csv(raw: str | None) -> List[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]

def safe(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "unknown")).strip("._") or "unknown"

def mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_attempts(value: object) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    allowed = ("attempt", "status_code", "latency_ms")
    return [
        {key: row[key] for key in allowed if key in row}
        for row in value
        if isinstance(row, dict)
    ]


def safe_error(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    if re.fullmatch(r"http_[0-9]{3}|empty_output|unknown", text):
        return text
    return "runtime_error"
