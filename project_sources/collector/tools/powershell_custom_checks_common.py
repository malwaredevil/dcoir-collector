#!/usr/bin/env python3
"""Shared constants and path helpers for custom PowerShell checks."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_powershell_surface_inventory as inventory_builder
from powershell_analyzer_contract import AnalyzerContractError, repo_relative_input_path

SCHEMA_VERSION = "dcoir_powershell_custom_check_report_v1"
CHECKS_SCHEMA_VERSION = "dcoir_powershell_custom_checks_v1"
FIXTURE_MANIFEST_SCHEMA_VERSION = "dcoir_powershell_custom_check_fixture_manifest_v1"
MATRIX_SCHEMA_VERSION = "dcoir_powershell_rule_risk_matrix_v1"
INVENTORY_SCHEMA_VERSION = inventory_builder.SCHEMA_VERSION
ISSUE_NUMBER = 264
PARENT_ISSUE_NUMBER = 260
DEFAULT_CHECKS = Path("project_sources/collector/powershell_custom_checks.json")
DEFAULT_MATRIX = Path("project_sources/collector/powershell_rule_risk_matrix.json")
DEFAULT_INVENTORY = Path("project_sources/collector/powershell_surface_inventory.json")
DEFAULT_FIXTURE_MANIFEST = Path("project_sources/collector/fixtures/powershell_analysis/custom_check_fixture_manifest.json")
DEFAULT_JSON_OUTPUT = Path("project_sources/collector/powershell_custom_check_report.json")
DEFAULT_MARKDOWN_OUTPUT = Path("project_sources/collector/powershell_custom_check_report.md")
ANALYZABLE_SOURCE_TYPES = {".ps1", ".psm1", ".psd1", ".ps1xml", ".ps1.txt"}
SEVERITY_ORDER = {"information": 0, "warning": 1, "error": 2}
REQUIRED_CHECK_FIELDS = [
    "id",
    "rule_name",
    "matrix_check_id",
    "expected_severity",
    "risk_classes",
    "target_surfaces",
    "intent",
    "target",
    "detection",
    "limitations",
    "false_positive_controls",
    "failure_impact",
    "recommended_fix",
]


class CustomCheckError(RuntimeError):
    """Raised for invalid #264 custom-check contract state."""

def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CustomCheckError(f"{label} missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CustomCheckError(f"{label} is not valid JSON: {path}: {exc}") from exc
    except OSError as exc:
        raise CustomCheckError(f"{label} could not be read: {path}: {exc}") from exc


def safe_relpath(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except (OSError, RuntimeError, ValueError):
        return path.as_posix()


def repo_relative_cli_path(repo_root: Path, value: str | Path, label: str, errors: list[str]) -> Path | None:
    try:
        return repo_relative_input_path(repo_root, value, label)
    except AnalyzerContractError as exc:
        errors.append(str(exc))
        return None


def repo_input_metadata(path: Path | None, raw_value: str | Path, repo_root: Path, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": safe_relpath(path, repo_root) if path is not None else str(raw_value),
        "accepted": path is not None,
        "schema_version": data.get("schema_version") if path is not None else None,
        "sha256": sha256_file(path) if path is not None and path.is_file() else None,
    }


def scalar(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def require_string(mapping: dict[str, Any], key: str, label: str, errors: list[str]) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: {key} must be a non-empty string")
        return ""
    return value.strip()


def require_string_list(mapping: dict[str, Any], key: str, label: str, errors: list[str]) -> list[str]:
    value = mapping.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        errors.append(f"{label}: {key} must be a non-empty list of strings")
        return []
    return [item.strip() for item in value]


def normalize_repo_path(value: str) -> str:
    slash_path = value.replace("\\", "/")
    while slash_path.startswith("./"):
        slash_path = slash_path[2:]
    return Path(slash_path).as_posix()


def is_absolute_repo_input(value: str) -> bool:
    raw = value.strip()
    slash_path = raw.replace("\\", "/")
    return slash_path.startswith("/") or re.match(r"^[A-Za-z]:", slash_path) is not None or Path(raw).is_absolute()

def safe_fixture_path(value: str, label: str, errors: list[str]) -> str:
    raw = value.strip()
    rel = normalize_repo_path(raw)
    raw_parts = Path(raw.replace("\\", "/")).parts
    parts = Path(rel).parts
    if not raw or is_absolute_repo_input(raw) or ".." in raw_parts or rel.startswith("../") or ".." in parts or Path(rel).is_absolute():
        errors.append(f"{label}: path must be a repo-relative path without traversal")
        return rel
    if not rel.startswith("project_sources/collector/fixtures/powershell_analysis/"):
        errors.append(f"{label}: fixture path must stay under project_sources/collector/fixtures/powershell_analysis")
    return rel


def safe_inventory_path(value: str, label: str, repo_root: Path, errors: list[str]) -> str:
    raw = value.strip()
    rel = normalize_repo_path(raw)
    slash_path = raw.replace("\\", "/")
    raw_parts = tuple(part for part in slash_path.split("/") if part)
    parts = Path(rel).parts
    if not raw or is_absolute_repo_input(raw) or ".." in raw_parts or rel.startswith("../") or ".." in parts or Path(rel).is_absolute():
        errors.append(f"{label}: path must be a repo-relative path without traversal")
        return ""
    root = repo_root.resolve()
    try:
        resolved = (root / rel).resolve()
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        errors.append(f"{label}: path must resolve inside the repository root")
        return ""
    return rel
