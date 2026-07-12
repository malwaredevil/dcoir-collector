#!/usr/bin/env python3
"""Shared constants and validation helpers for rule-risk fixture reporting."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from powershell_analyzer_contract import AnalyzerContractError, repo_relative_input_path

SCHEMA_VERSION = "dcoir_powershell_rule_risk_fixture_report_v1"
MATRIX_SCHEMA_VERSION = "dcoir_powershell_rule_risk_matrix_v1"
MANIFEST_SCHEMA_VERSION = "dcoir_powershell_rule_risk_fixture_manifest_v1"
ISSUE_NUMBER = 263
DEFAULT_MATRIX = Path("project_sources/collector/powershell_rule_risk_matrix.json")
DEFAULT_MANIFEST = Path("project_sources/collector/fixtures/powershell_analysis/rule_fixture_manifest.json")
DEFAULT_JSON_OUTPUT = Path("project_sources/collector/powershell_rule_risk_fixture_report.json")
DEFAULT_MARKDOWN_OUTPUT = Path("project_sources/collector/powershell_rule_risk_fixture_report.md")
DEFAULT_MATRIX_MARKDOWN_OUTPUT = Path("project_sources/collector/powershell_rule_risk_matrix.md")
FIXTURE_ROOT = Path("project_sources/collector/fixtures/powershell_analysis")
FACADE_PATH = Path(__file__).resolve().with_name("run_powershell_rule_risk_fixtures.py")
MINIMUM_RISK_CLASSES = {
    "analyzer_policy_inventory_skip_or_tool_failure_reported_success",
    "stale_or_unchecked_last_exit_code_or_success_status",
    "external_command_nonzero_exit_treated_success",
    "fail_rows_reports_or_fixture_outputs_not_causing_failure",
    "source_part_assembly_drift_or_stale_generated_output",
    "unsafe_or_wildcard_deletion_outside_controlled_roots",
    "unbounded_or_materializing_event_query_patterns",
    "broad_suppression_or_baseline_growth_hiding_risk",
    "swallowed_exception_or_write_only_catch",
}

class RuleRiskFixtureError(Exception):
    """Raised for invalid #263 matrix or fixture contract state."""

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuleRiskFixtureError(f"{label} is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuleRiskFixtureError(f"{label} is invalid JSON: {path}: {exc}") from exc
    except OSError as exc:
        raise RuleRiskFixtureError(f"{label} could not be read: {path}: {exc}") from exc

def relpath(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()

def safe_relpath(path: Path, repo_root: Path) -> str:
    try:
        return relpath(path, repo_root)
    except (OSError, RuntimeError, ValueError):
        return path.as_posix()

def repo_relative_path_or_error(repo_root: Path, value: str | Path, label: str, errors: list[str]) -> Path | None:
    try:
        return repo_relative_input_path(repo_root, value, label)
    except AnalyzerContractError as exc:
        errors.append(str(exc))
        return None

def scalar(value: Any) -> str:
    return "" if value is None else str(value)

def require_string(mapping: dict[str, Any], key: str, label: str, errors: list[str]) -> str:
    value = scalar(mapping.get(key)).strip()
    if not value:
        errors.append(f"{label} missing {key}")
    return value

def require_string_list(mapping: dict[str, Any], key: str, label: str, errors: list[str]) -> list[str]:
    value = mapping.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        errors.append(f"{label} must declare non-empty string list {key}")
        return []
    return [item.strip() for item in value]

def safe_fixture_path(value: str, label: str, errors: list[str]) -> str | None:
    invalid = False
    if "\\" in value:
        errors.append(f"{label}: fixture path must use POSIX separators")
        invalid = True
    candidate = Path(value)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        errors.append(f"{label}: fixture path must be repo-relative and must not traverse parents")
        invalid = True
    normalized = candidate.as_posix()
    if not normalized.startswith(FIXTURE_ROOT.as_posix() + "/"):
        errors.append(f"{label}: fixture path must stay under {FIXTURE_ROOT.as_posix()}")
        invalid = True
    if not normalized.endswith(".ps1"):
        errors.append(f"{label}: fixture path must be a .ps1 file")
        invalid = True
    if invalid:
        return None
    return normalized

def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False

def path_contains_symlink(path: Path, root: Path) -> bool:
    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        return path.is_symlink()
    current = root
    for part in relative_parts:
        current = current / part
        if current.is_symlink():
            return True
    return False

def validate_fixture_root(repo_root: Path, errors: list[str]) -> bool:
    fixture_root = repo_root / FIXTURE_ROOT
    if not fixture_root.exists():
        errors.append(f"fixture root is missing: {FIXTURE_ROOT.as_posix()}")
        return False
    if not fixture_root.is_dir():
        errors.append(f"fixture root must be a directory: {FIXTURE_ROOT.as_posix()}")
        return False
    if path_contains_symlink(fixture_root, repo_root):
        errors.append(f"fixture root must not be a symlink: {FIXTURE_ROOT.as_posix()}")
        return False
    if not is_relative_to(fixture_root, repo_root):
        errors.append(f"fixture root resolves outside repository: {FIXTURE_ROOT.as_posix()}")
        return False
    return True
