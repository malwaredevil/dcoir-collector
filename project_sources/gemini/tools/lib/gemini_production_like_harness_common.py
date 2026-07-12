"""Shared helpers for the Gemini production-like harness validator."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED_GITIGNORE_PATTERNS = [
    "project_sources/validation/out_*/",
    "project_sources/TestResults/",
    "project_sources/gemini/fixtures/behavioral_replay/blind_artifacts/**",
    "project_sources/collector/fixtures/blind_artifacts/**",
    "chatgpt_workflow_report_section/",
]

EXPECTED_CONSTRUCT_COUNTS = {
    "prime_chunks": 21,
    "sub_agents": 11,
    "knowledge_sources": 28,
}

BANNED_PROMPT_TERMS = [
    "expected_behavior",
    "forbidden_behavior",
    "expected_verdict",
    "artifact_expectations",
    "must_find",
    "must_not_find",
    "answer key",
    "rubric",
    "grader",
]


def load_json(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def repo_relative(path: Path | str, root: Path) -> str:
    try:
        return Path(path).relative_to(root).as_posix()
    except ValueError:
        return Path(path).as_posix()


def add_message(messages: list[dict[str, str]], level: str, message: str, path: str = "") -> None:
    entry = {"level": level, "message": message}
    if path:
        entry["path"] = path
    messages.append(entry)


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_gitignore(root: Path, messages: list[dict[str, str]]) -> dict[str, Any]:
    gitignore_path = root / ".gitignore"
    text = gitignore_path.read_text(encoding="utf-8") if gitignore_path.is_file() else ""
    missing_patterns = [pattern for pattern in REQUIRED_GITIGNORE_PATTERNS if pattern not in text]
    for pattern in missing_patterns:
        add_message(messages, "error", f".gitignore missing {pattern}", ".gitignore")
    return {"present": bool(text), "missing_patterns": missing_patterns}
