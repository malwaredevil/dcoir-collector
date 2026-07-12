#!/usr/bin/env python3
"""Shared constants and path/report helpers for PowerShell engine/Pester boundary validation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "dcoir_powershell_engine_pester_boundary_report_v1"
BOUNDARY_SCHEMA_VERSION = "dcoir_powershell_engine_pester_boundary_v1"
ISSUE_NUMBER = 267
PARENT_ISSUE_NUMBER = 260
DEFAULT_BOUNDARY = Path("project_sources/collector/powershell_engine_pester_boundary.json")
DEFAULT_JSON_OUTPUT = Path("project_sources/collector/powershell_engine_pester_boundary_report.json")
DEFAULT_MARKDOWN_OUTPUT = Path("project_sources/collector/powershell_engine_pester_boundary_report.md")
DEFAULT_RULE_RISK_REPORT = Path("project_sources/collector/powershell_rule_risk_fixture_report.json")
DEFAULT_CUSTOM_REPORT = Path("project_sources/collector/powershell_custom_check_report.json")
DEFAULT_GOVERNANCE_REPORT = Path("project_sources/collector/powershell_finding_governance_report.json")
DEFAULT_ASSEMBLY_REPORT = Path("project_sources/collector/powershell_assembly_parity_report.json")

REQUIRED_CHECK_CATEGORIES = {
    "surface_inventory",
    "windows_powershell_51_parser_runtime_compatibility",
    "powershell_7_static_analyzer",
    "rule_risk_negative_fixture_proof",
    "dcoir_custom_static_checks",
    "assembly_aware_source_generated_parity",
    "baseline_remediation_suppression_governance",
    "pester_supporting_tests",
}
REQUIRED_MATRIX_FIELDS = (
    "id",
    "check_category",
    "required_engine",
    "runner_os",
    "module_or_tool_dependency",
    "evidence_type",
    "output_artifact",
    "blocking",
    "owner",
    "boundary",
)
PESTER_EVIDENCE_FIELDS = {
    "discovery command",
    "Pester version",
    "PowerShell engine and version",
    "runner OS",
    "test count",
    "pass/fail count",
    "machine-readable test result artifact",
    "human-readable summary",
    "owning issue or workflow gate",
    "failure behavior",
}
REPORT_SCHEMAS = {
    DEFAULT_RULE_RISK_REPORT.as_posix(): "dcoir_powershell_rule_risk_fixture_report_v1",
    DEFAULT_CUSTOM_REPORT.as_posix(): "dcoir_powershell_custom_check_report_v1",
    DEFAULT_GOVERNANCE_REPORT.as_posix(): "dcoir_powershell_finding_governance_report_v1",
    DEFAULT_ASSEMBLY_REPORT.as_posix(): "dcoir_powershell_assembly_parity_report_v1",
}
REPO_ARTIFACT_PREFIXES = (
    ".github/",
    "operator_tools/",
    "project_sources/",
    "scripts/",
    "tools/",
)
EXPLICIT_ARTIFACT_STATUSES = {
    "not_committed_in_267_boundary",
}


class EngineBoundaryError(RuntimeError):
    """Raised for fail-closed #267 validation errors."""


def scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EngineBoundaryError(f"{label} missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EngineBoundaryError(f"{label} invalid JSON: {path}: {exc}") from exc
    except OSError as exc:
        raise EngineBoundaryError(f"{label} could not be read: {path}: {exc}") from exc


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_repo_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except (OSError, RuntimeError, ValueError):
        return path.as_posix()


def report_success_state(report: dict[str, Any]) -> tuple[bool, str]:
    validation = report.get("validation")
    if isinstance(validation, dict):
        if "success" not in validation:
            return False, "validation.success is missing"
        success = validation.get("success")
        if success is True:
            return True, "validation.success is true"
        if success is False:
            return False, "validation.success is false"
        return False, "validation.success must be boolean true"
    if validation is not None:
        return False, "validation must be an object with success=true"
    if "success" in report:
        success = report.get("success")
        if success is True:
            return True, "top-level success is true"
        if success is False:
            return False, "top-level success is false"
        return False, "top-level success must be boolean true"
    return False, "missing explicit validation.success or top-level success"


def report_success(report: dict[str, Any]) -> bool:
    success, _reason = report_success_state(report)
    return success


def summary_count(report: dict[str, Any], key: str) -> int:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        return 0
    value = summary.get(key)
    return value if isinstance(value, int) else 0


def report_finding_count(report: dict[str, Any]) -> int:
    for key in ("finding_count", "observed_finding_count", "classified_finding_count"):
        count = summary_count(report, key)
        if count:
            return count
    return 0


def artifact_slash_path(value: str) -> str:
    return value.strip().replace("\\", "/")


def is_windows_drive_path(value: str) -> bool:
    return len(value) >= 2 and value[0].isalpha() and value[1] == ":"


def resolve_repo_input_path(value: str, repo_root: Path, label: str) -> tuple[Path | None, str, str | None]:
    slash_path = artifact_slash_path(value)
    parts = tuple(part for part in slash_path.split("/") if part)
    if not slash_path or slash_path.startswith("/") or is_windows_drive_path(slash_path) or ".." in parts:
        return None, slash_path, f"{label} path must be a repo-relative path without traversal"
    candidate = repo_root.joinpath(*parts)
    try:
        candidate.resolve().relative_to(repo_root.resolve())
    except (OSError, RuntimeError, ValueError):
        return None, slash_path, f"{label} path must resolve inside the repository root"
    return candidate, slash_path, None


def is_repo_artifact_path(value: str) -> bool:
    return artifact_slash_path(value).startswith(REPO_ARTIFACT_PREFIXES)


def resolve_repo_artifact_path(artifact: str, repo_root: Path) -> tuple[Path | None, str | None]:
    candidate, _repo_path, path_error = resolve_repo_input_path(artifact, repo_root, "output_artifact")
    return candidate, path_error


__all__ = [
    "BOUNDARY_SCHEMA_VERSION",
    "DEFAULT_ASSEMBLY_REPORT",
    "DEFAULT_BOUNDARY",
    "DEFAULT_CUSTOM_REPORT",
    "DEFAULT_GOVERNANCE_REPORT",
    "DEFAULT_JSON_OUTPUT",
    "DEFAULT_MARKDOWN_OUTPUT",
    "DEFAULT_RULE_RISK_REPORT",
    "EngineBoundaryError",
    "EXPLICIT_ARTIFACT_STATUSES",
    "ISSUE_NUMBER",
    "PARENT_ISSUE_NUMBER",
    "PESTER_EVIDENCE_FIELDS",
    "REPORT_SCHEMAS",
    "REPO_ARTIFACT_PREFIXES",
    "REQUIRED_CHECK_CATEGORIES",
    "REQUIRED_MATRIX_FIELDS",
    "SCHEMA_VERSION",
    "artifact_slash_path",
    "is_repo_artifact_path",
    "is_windows_drive_path",
    "read_json",
    "report_finding_count",
    "report_success",
    "report_success_state",
    "resolve_repo_artifact_path",
    "resolve_repo_input_path",
    "safe_repo_path",
    "scalar",
    "summary_count",
    "write_json",
]
