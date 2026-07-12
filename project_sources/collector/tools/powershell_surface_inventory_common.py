#!/usr/bin/env python3
"""Shared constants and file helpers for the PowerShell surface inventory."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from powershell_analyzer_contract import AnalyzerContractError, repo_relative_input_path

SCHEMA_VERSION = "dcoir_powershell_surface_inventory_v1"
ISSUE_NUMBER = 261
DEFAULT_JSON_OUTPUT = Path("project_sources/collector/powershell_surface_inventory.json")
DEFAULT_MARKDOWN_OUTPUT = Path("project_sources/collector/powershell_surface_inventory.md")
REQUIRED_SOURCE_TYPES = [".ps1", ".psm1", ".psd1", ".ps1xml", ".ps1.txt", "workflow_yaml"]
KNOWN_CATEGORIES = [
    "archive_temp_vendor_artifact",
    "collector_harness_script",
    "collector_harness_source_part",
    "collector_runtime_source_part",
    "collector_runtime_wrapper",
    "collector_validation_tooling",
    "fixture_or_example",
    "generated_or_assembled_output",
    "github_workflow_support_script",
    "invalid_workflow_surface",
    "missing_authoritative_surface",
    "missing_changed_powershell_surface",
    "missing_changed_workflow_surface",
    "operator_tooling",
    "staging_artifact",
    "unclassified_powershell_surface",
    "validation_tooling",
    "workflow_embedded_powershell",
]
PRIMARY_COLLECTOR_CATEGORIES = {
    "collector_runtime_wrapper",
    "collector_runtime_source_part",
}
PRIMARY_HARNESS_CATEGORIES = {
    "collector_harness_script",
    "collector_harness_source_part",
}
REQUIRED_FULL_MODE_CATEGORIES = PRIMARY_COLLECTOR_CATEGORIES | PRIMARY_HARNESS_CATEGORIES
IGNORED_DISCOVERY_SEGMENTS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    ".venv",
    "venv",
}
POWERSHELL_FILE_SUFFIXES = (".ps1", ".psm1", ".psd1", ".ps1xml", ".ps1.txt")
WORKFLOW_MARKER_RE = re.compile(
    r"(?im)(shell:\s*(?:pwsh|powershell)\b|(?<![-.\w])pwsh(?![-.\w])|(?<![-.\w])powershell(?:\.exe)?(?![-.\w]))"
)
MANIFEST_PATH = Path("project_sources/collector/manifests/Collector_Runtime_Package_Manifest.json")
HARNESS_PARTS_ROOT = Path("project_sources/collector/harness/source/parts")
HARNESS_GENERATED_OUTPUT = Path("project_sources/collector/harness/run_DCOIR_Tests.generated.ps1")
REQUIRED_SURFACE_PROFILES_PATH = Path("project_sources/github_actions/workflow_required_surface_profiles.json")
REQUIRED_SURFACE_PROFILE_SUPPLEMENTS_PATH = Path("project_sources/github_actions/workflow_required_surface_profile_supplements.json")
FLOW_STEP_KEYS = {
    "continue-on-error",
    "env",
    "id",
    "if",
    "name",
    "run",
    "shell",
    "timeout-minutes",
    "uses",
    "with",
    "working-directory",
}


def relpath(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def path_parts(rel: str) -> tuple[str, ...]:
    return tuple(part.casefold() for part in Path(rel).parts)


def is_ignored_discovery_path(rel: str) -> bool:
    return any(part in IGNORED_DISCOVERY_SEGMENTS for part in path_parts(rel))


def has_prefix(rel: str, prefix: str) -> bool:
    normalized = rel.casefold()
    return normalized == prefix.casefold() or normalized.startswith(prefix.casefold().rstrip("/") + "/")


def is_powershell_file(rel: str) -> bool:
    lowered = rel.casefold()
    return lowered.endswith(POWERSHELL_FILE_SUFFIXES)


def is_workflow_yaml(rel: str) -> bool:
    lowered = rel.casefold()
    if not lowered.endswith((".yml", ".yaml")):
        return False
    return has_prefix(rel, ".github/workflows") or has_prefix(rel, ".github/actions")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def normalized_text_fact_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def path_resolves_inside_repo(path: Path, repo_root: Path) -> bool:
    try:
        path.resolve().relative_to(repo_root.resolve())
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def path_is_file_inside_repo(path: Path, repo_root: Path) -> bool:
    return path_resolves_inside_repo(path, repo_root) and path.is_file()


def path_is_dir_inside_repo(path: Path, repo_root: Path) -> bool:
    return path_resolves_inside_repo(path, repo_root) and path.is_dir()


def repo_file_exists(repo_root: Path, rel: str) -> bool:
    return path_is_file_inside_repo(repo_root / rel, repo_root)


def file_facts(repo_root: Path, rel: str, exists: bool) -> dict[str, Any]:
    path = repo_root / rel
    if not path_resolves_inside_repo(path, repo_root):
        return {
            "size_bytes": None,
            "line_count": None,
            "sha256": None,
        }
    if not exists:
        return {
            "size_bytes": None,
            "line_count": None,
            "sha256": None,
        }
    try:
        data = path.read_bytes()
    except OSError:
        return {
            "size_bytes": None,
            "line_count": None,
            "sha256": None,
        }
    fact_data = normalized_text_fact_bytes(data)
    return {
        "size_bytes": len(fact_data),
        "line_count": fact_data.count(b"\n") + (1 if fact_data and not fact_data.endswith(b"\n") else 0),
        "sha256": hashlib.sha256(fact_data).hexdigest(),
    }


def source_type_for(rel: str) -> str:
    lowered = rel.casefold()
    if lowered.endswith(".ps1.txt"):
        return ".ps1.txt"
    if is_workflow_yaml(rel):
        return "workflow_yaml"
    for suffix in (".ps1xml", ".psm1", ".psd1", ".ps1"):
        if lowered.endswith(suffix):
            return suffix
    return "unknown"


def generated_like(rel: str) -> bool:
    parts = path_parts(rel)
    generated_segments = {
        "compiled_runtime",
        "generated",
        "generated_output",
        "dist",
        "build",
        "output",
        "outputs",
    }
    if any(part in generated_segments for part in parts):
        return True
    return any(part.startswith("out_") or part.startswith("out-") for part in parts)


def fixture_like(rel: str) -> bool:
    parts = path_parts(rel)
    return any(part in {"fixture", "fixtures", "examples", "example", "samples", "sample"} for part in parts)


def staging_like(rel: str) -> bool:
    return has_prefix(rel, "chatgpt_staging")


def archive_temp_vendor_like(rel: str) -> bool:
    parts = path_parts(rel)
    return any(part in {"archive", "archived", "temp", "tmp", "vendor", "third_party"} for part in parts)


def make_surface(
    repo_root: Path,
    rel: str,
    category: str,
    status: str,
    decision: str,
    reason: str,
    exists: bool,
    marker_lines: list[int] | None = None,
    embedded_snippets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    surface = {
        "path": rel,
        "category": category,
        "source_type": source_type_for(rel),
        "status": status,
        "inclusion_decision": decision,
        "decision_reason": reason,
        "exists": exists,
        "marker_lines": marker_lines or [],
        "embedded_snippets": embedded_snippets or [],
    }
    surface.update(file_facts(repo_root, rel, exists))
    return surface


def load_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"JSON file is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"JSON file could not be read: {path}: {exc}") from exc


def repo_relative_cli_path(repo_root: Path, value: str | Path, label: str) -> Path:
    try:
        return repo_relative_input_path(repo_root, value, label)
    except AnalyzerContractError as exc:
        raise ValueError(str(exc)) from exc


__all__ = [
    "AnalyzerContractError",
    "repo_relative_input_path",
    "SCHEMA_VERSION",
    "ISSUE_NUMBER",
    "DEFAULT_JSON_OUTPUT",
    "DEFAULT_MARKDOWN_OUTPUT",
    "REQUIRED_SOURCE_TYPES",
    "KNOWN_CATEGORIES",
    "PRIMARY_COLLECTOR_CATEGORIES",
    "PRIMARY_HARNESS_CATEGORIES",
    "REQUIRED_FULL_MODE_CATEGORIES",
    "IGNORED_DISCOVERY_SEGMENTS",
    "POWERSHELL_FILE_SUFFIXES",
    "WORKFLOW_MARKER_RE",
    "MANIFEST_PATH",
    "HARNESS_PARTS_ROOT",
    "HARNESS_GENERATED_OUTPUT",
    "REQUIRED_SURFACE_PROFILES_PATH",
    "REQUIRED_SURFACE_PROFILE_SUPPLEMENTS_PATH",
    "FLOW_STEP_KEYS",
    "relpath",
    "path_parts",
    "is_ignored_discovery_path",
    "has_prefix",
    "is_powershell_file",
    "is_workflow_yaml",
    "read_text",
    "normalized_text_fact_bytes",
    "path_resolves_inside_repo",
    "path_is_file_inside_repo",
    "path_is_dir_inside_repo",
    "repo_file_exists",
    "file_facts",
    "source_type_for",
    "generated_like",
    "fixture_like",
    "staging_like",
    "archive_temp_vendor_like",
    "make_surface",
    "load_json_file",
    "repo_relative_cli_path",
]
