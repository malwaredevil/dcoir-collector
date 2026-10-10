#!/usr/bin/env python3
"""Canonical fail-closed input-path resolution for collector Python tools."""
from __future__ import annotations

import re
from pathlib import Path

class AnalyzerContractError(Exception):
    """Raised for fail-closed analyzer wrapper errors."""


def repo_relative_input_path(repo_root: Path, value: str | Path, label: str) -> Path:
    raw = str(value).strip()
    slash_path = raw.replace("\\", "/")
    while slash_path.startswith("./"):
        slash_path = slash_path[2:]
    raw_parts = tuple(part for part in slash_path.split("/") if part)
    normalized = Path(slash_path).as_posix()
    if (
        not raw
        or slash_path.startswith("/")
        or re.match(r"^[A-Za-z]:", slash_path) is not None
        or Path(raw).is_absolute()
        or ".." in raw_parts
        or normalized.startswith("../")
        or ".." in Path(normalized).parts
        or Path(normalized).is_absolute()
    ):
        raise AnalyzerContractError(f"{label} must be a repo-relative path without traversal")
    try:
        candidate = (repo_root / normalized).resolve()
        candidate.relative_to(repo_root.resolve())
    except (OSError, RuntimeError, ValueError) as exc:
        raise AnalyzerContractError(f"{label} must resolve inside the repository root") from exc
    return candidate



__all__ = ["AnalyzerContractError", "repo_relative_input_path"]
