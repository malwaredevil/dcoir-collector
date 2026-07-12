from __future__ import annotations

import re
from pathlib import Path
from typing import List

def csv(raw: str | None) -> List[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]

def safe(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "unknown")).strip("._") or "unknown"

def mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
