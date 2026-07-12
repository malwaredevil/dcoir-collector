#!/usr/bin/env python3
"""Shared constants, models, and path helpers for finding governance."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "dcoir_powershell_finding_governance_report_v1"
GOVERNANCE_SCHEMA_VERSION = "dcoir_powershell_finding_governance_v1"
ISSUE_NUMBER = 266
DEFAULT_GOVERNANCE = Path("project_sources/collector/powershell_finding_governance.json")
DEFAULT_CUSTOM_REPORT = Path("project_sources/collector/powershell_custom_check_report.json")
DEFAULT_RULE_RISK_REPORT = Path("project_sources/collector/powershell_rule_risk_fixture_report.json")
DEFAULT_ANALYZER_REPORT = Path("project_sources/collector/powershell_analyzer_report.json")
DEFAULT_ASSEMBLY_PARITY_REPORT = Path("project_sources/collector/powershell_assembly_parity_report.json")
DEFAULT_JSON_OUTPUT = Path("project_sources/collector/powershell_finding_governance_report.json")
DEFAULT_MARKDOWN_OUTPUT = Path("project_sources/collector/powershell_finding_governance_report.md")
ASSEMBLY_PARITY_SCHEMA_VERSION = "dcoir_powershell_assembly_parity_report_v1"

REPORT_SCHEMAS = {
    DEFAULT_CUSTOM_REPORT.as_posix(): "dcoir_powershell_custom_check_report_v1",
    DEFAULT_RULE_RISK_REPORT.as_posix(): "dcoir_powershell_rule_risk_fixture_report_v1",
    DEFAULT_ANALYZER_REPORT.as_posix(): "dcoir_powershell_analyzer_report_v1",
}

ALLOWED_DECISIONS = {
    "remediate-now",
    "baseline-temporary",
    "advisory",
    "false positive",
    "accepted risk",
}
SEVERITY_ORDER = {
    "information": 0,
    "info": 0,
    "warning": 1,
    "warn": 1,
    "error": 2,
    "critical": 3,
}
REVIEW_FIELDS = ("rationale", "owner", "reviewer", "review_date")
LINE_OR_LOCATOR_FIELDS = ("line", "stable_locator")
EXPIRY_OR_REVISIT_FIELDS = ("expires_on", "revisit_condition")


@dataclass(frozen=True)
class Finding:
    source_report: str
    source_schema_version: str
    path: str
    line: int | None
    column: int | None
    rule_name: str
    check_id: str
    severity: str
    fingerprint: str
    observed_problem: str
    recommended_fix: str
    raw: dict[str, Any]

    def as_report_item(self) -> dict[str, Any]:
        return {
            "source_report": self.source_report,
            "source_schema_version": self.source_schema_version,
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "rule_name": self.rule_name,
            "check_id": self.check_id,
            "severity": self.severity,
            "fingerprint": self.fingerprint,
            "observed_problem": self.observed_problem,
            "recommended_fix": self.recommended_fix,
        }


class GovernanceError(Exception):
    """Raised for fail-closed governance validation errors."""


def scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_repo_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except (OSError, RuntimeError, ValueError):
        return path.as_posix()


def slash_path(value: str) -> str:
    return value.strip().replace("\\", "/")


def is_windows_drive_path(value: str) -> bool:
    return len(value) >= 2 and value[0].isalpha() and value[1] == ":"


def resolve_repo_input_path(value: str, repo_root: Path, label: str) -> tuple[Path | None, str, str | None]:
    normalized = slash_path(value)
    parts = tuple(part for part in normalized.split("/") if part)
    if not normalized or normalized.startswith("/") or is_windows_drive_path(normalized) or ".." in parts:
        return None, normalized, f"{label} path must be a repo-relative path without traversal"
    candidate = repo_root.joinpath(*parts)
    try:
        candidate.resolve().relative_to(repo_root.resolve())
    except (OSError, RuntimeError, ValueError):
        return None, normalized, f"{label} path must resolve inside the repository root"
    return candidate, normalized, None


def validate_governance_path(value: str, repo_root: Path, label: str) -> str:
    path_value = scalar(value).strip()
    if is_blanket_selector(path_value):
        raise GovernanceError(f"{label} uses a blanket or wildcard path; path must be a bounded repo-relative path")
    _candidate, repo_path, path_error = resolve_repo_input_path(path_value, repo_root, label)
    if path_error:
        raise GovernanceError(f"{path_error}: {path_value}")
    if not repo_path:
        raise GovernanceError(f"{label} path could not be resolved: {path_value}")
    return repo_path


def validate_governance_path_prefix(value: str, repo_root: Path, label: str) -> str:
    prefix_value = slash_path(scalar(value).strip())
    if is_blanket_selector(prefix_value):
        raise GovernanceError(f"{label} uses a blanket or wildcard prefix; prefix must be a bounded repo-relative prefix")
    parts = tuple(part for part in prefix_value.split("/") if part)
    if prefix_value.startswith("/") or is_windows_drive_path(prefix_value) or ".." in parts:
        raise GovernanceError(f"{label} prefix must be a repo-relative prefix without traversal: {prefix_value}")
    candidate = repo_root.joinpath(*parts)
    try:
        candidate.resolve().relative_to(repo_root.resolve())
    except (OSError, RuntimeError, ValueError) as exc:
        raise GovernanceError(f"{label} prefix must resolve inside the repository root: {prefix_value}") from exc
    return prefix_value


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GovernanceError(f"{label} is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise GovernanceError(f"{label} is invalid JSON: {path}: {exc}") from exc
    except OSError as exc:
        raise GovernanceError(f"{label} could not be read: {path}: {exc}") from exc


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_repo_output_path(repo_root: Path, output_path: Path, label: str) -> Path:
    absolute_path, _repo_path, path_error = resolve_repo_input_path(output_path.as_posix(), repo_root, label)
    if path_error:
        raise GovernanceError(f"{label} {path_error}: {output_path.as_posix()}")
    if absolute_path is None:
        raise GovernanceError(f"{label} path could not be resolved: {output_path.as_posix()}")
    return absolute_path


def mark_report_write_failure(report: dict[str, Any], message: str) -> None:
    validation = report.setdefault("validation", {})
    validation["success"] = False
    errors = validation.setdefault("errors", [])
    if isinstance(errors, list):
        errors.append(message)
    else:
        validation["errors"] = [message]


def normalize_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def severity_rank(severity: str) -> int:
    return SEVERITY_ORDER.get(severity.casefold(), 99)


def is_blanket_selector(value: str) -> bool:
    stripped = value.strip().casefold()
    return (
        not stripped
        or stripped in {".", "./", "*", "**", "**/*", "all", "repo", "repository", "<repo>"}
        or "*" in stripped
    )


def has_any_text(item: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return any(scalar(item.get(key)).strip() for key in keys)
