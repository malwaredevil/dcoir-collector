from __future__ import annotations

import json
import os
import re
import zipfile
from pathlib import Path

ALLOWED_JSON_REPORTS = {
    "project_sources/collector/powershell_review_assist_workflow_report.json": 1_000_000,
    "project_sources/collector/powershell_analyzer_report.json": 1_000_000,
    "project_sources/collector/powershell_duplicate_function_report.json": 1_000_000,
}
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SAFE_METADATA_RE = re.compile(r"^[A-Za-z0-9_.:/@+-]{0,160}$")


def safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    resolved_destination = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise SystemExit(f"Unsafe artifact member path: {member.filename}")
            target = (resolved_destination / member_path).resolve()
            if target != resolved_destination and resolved_destination not in target.parents:
                raise SystemExit(f"Artifact member escapes destination: {member.filename}")
        zf.extractall(resolved_destination)


def read_changed_files(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def safe_metadata(name: str) -> str:
    value = os.getenv(name, "")
    return value if SAFE_METADATA_RE.fullmatch(value) else "invalid-metadata"


def load_json(root: Path, rel_path: str) -> dict:
    if rel_path not in ALLOWED_JSON_REPORTS:
        return {"_load_error": "static context report path is not allowlisted"}
    root_resolved = root.resolve()
    path = (root / rel_path).resolve()
    try:
        path.relative_to(root_resolved)
    except ValueError:
        return {"_load_error": "static context report path escaped extraction root"}
    if not path.exists():
        return {}
    if path.suffix != ".json":
        return {"_load_error": "static context report path must be JSON"}
    if path.stat().st_size > ALLOWED_JSON_REPORTS[rel_path]:
        return {"_load_error": "static context report exceeds bounded size limit"}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"_load_error": str(exc)}
    if not isinstance(loaded, dict):
        return {"_load_error": "static context report root must be a JSON object"}
    return loaded


def trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...(static validation context truncated)"


def clean_text(value: object, limit: int = 240) -> str:
    if value is None:
        text = ""
    elif isinstance(value, (str, int, float, bool)):
        text = str(value)
    else:
        text = json.dumps(value, sort_keys=True, default=str)
    text = CONTROL_CHARS_RE.sub(" ", text)
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "...[truncated]"
    return text


def cell(value: object, limit: int = 240) -> str:
    return clean_text(value, limit).replace("|", "\\|").replace("`", "\\`")


def joined_or_none(values: list[str]) -> str:
    joined = ", ".join(values)
    return joined if joined else "none"
