#!/usr/bin/env python3
"""Shared contracts and source-loading helpers for PowerShell review-assist reports."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "dcoir_powershell_review_assist_report_v1"
ISSUE_NUMBER = 268
PARENT_ISSUE_NUMBER = 260
DEFAULT_SCHEMA_PATH = Path("project_sources/collector/powershell_review_assist_report.schema.json")
DEFAULT_JSON_OUTPUT = Path("project_sources/collector/powershell_review_assist_report.json")
DEFAULT_MARKDOWN_OUTPUT = Path("project_sources/collector/powershell_review_assist_report.md")
DEFAULT_SURFACE_INVENTORY = Path("project_sources/collector/powershell_surface_inventory.json")
DEFAULT_RULE_RISK_REPORT = Path("project_sources/collector/powershell_rule_risk_fixture_report.json")
DEFAULT_RULE_RISK_MATRIX = Path("project_sources/collector/powershell_rule_risk_matrix.json")
DEFAULT_CUSTOM_REPORT = Path("project_sources/collector/powershell_custom_check_report.json")
DEFAULT_ASSEMBLY_PARITY_REPORT = Path("project_sources/collector/powershell_assembly_parity_report.json")
DEFAULT_GOVERNANCE_REPORT = Path("project_sources/collector/powershell_finding_governance_report.json")
DEFAULT_ENGINE_BOUNDARY_REPORT = Path("project_sources/collector/powershell_engine_pester_boundary_report.json")
DEFAULT_ANALYZER_REPORT = Path("project_sources/collector/powershell_analyzer_report.json")
DEFAULT_FUNCTION_REACHABILITY_REPORT = Path("project_sources/collector/powershell_function_reachability_report.json")

SCHEMA_VERSIONS = {
    "surface_inventory": "dcoir_powershell_surface_inventory_v1",
    "rule_risk_report": "dcoir_powershell_rule_risk_fixture_report_v1",
    "rule_risk_matrix": "dcoir_powershell_rule_risk_matrix_v1",
    "custom_report": "dcoir_powershell_custom_check_report_v1",
    "assembly_parity_report": "dcoir_powershell_assembly_parity_report_v1",
    "governance_report": "dcoir_powershell_finding_governance_report_v1",
    "engine_boundary_report": "dcoir_powershell_engine_pester_boundary_report_v1",
    "analyzer_report": "dcoir_powershell_analyzer_report_v1",
    "function_reachability_report": "dcoir_powershell_function_reachability_report_v1",
}

SOURCE_ISSUES = {
    "surface_inventory": 261,
    "analyzer_report": 262,
    "rule_risk_report": 263,
    "rule_risk_matrix": 263,
    "custom_report": 264,
    "assembly_parity_report": 265,
    "governance_report": 266,
    "engine_boundary_report": 267,
    "function_reachability_report": 306,
}

SOURCE_LABELS = {
    "surface_inventory": "#261 surface inventory",
    "rule_risk_report": "#263 rule-risk fixture report",
    "rule_risk_matrix": "#263 rule-risk matrix companion",
    "custom_report": "#264 DCOIR custom-check report",
    "assembly_parity_report": "#265 assembly parity report",
    "governance_report": "#266 finding governance report",
    "engine_boundary_report": "#267 engine/Pester boundary report",
    "analyzer_report": "#262 optional PowerShell analyzer report",
    "function_reachability_report": "#306 function reachability report",
}

REQUIRED_SOURCE_KEYS = (
    "surface_inventory",
    "rule_risk_report",
    "rule_risk_matrix",
    "custom_report",
    "assembly_parity_report",
    "governance_report",
    "engine_boundary_report",
    "function_reachability_report",
)

SOURCE_PATH_PREFIXES = (
    ".github/",
    "chatgpt_staging/",
    "compiled_runtime/",
    "knowledge/",
    "operator_tools/",
    "project_sources/",
    "scripts/",
    "tools/",
)

NON_CLAIMS = [
    "No workflow YAML was changed by #268.",
    "No SARIF file is generated or uploaded by #268.",
    "No GitHub code-scanning alert or required-check behavior is enabled by #268.",
    "No workflow artifact retention behavior is configured by #268.",
    "No Pester result is promoted to blocking static-validation evidence by #268.",
    "No changed-file execution, path-filter behavior, PR-diff coverage, or changed-file gating is claimed by #268.",
    "No live PSScriptAnalyzer evidence is claimed when the #262 analyzer report is absent.",
    "No Windows PowerShell 5.1 runtime validation is claimed by #268.",
    "No #269, #270, PR/workflow readiness, or parent #260 closeability claim is made by #268.",
    "No function deletion readiness or dead-code removal claim is made by #306 reachability reporting.",
]

FUTURE_HANDOFF_CONSUMERS = [
    {
        "issue": 269,
        "consumer": "SARIF decision gate",
        "may_consume": [
            "normalized findings",
            "evidence channel states",
            "missing analyzer evidence",
            "explicit non-claims",
        ],
        "not_claimed_by_268": "SARIF generation, SARIF upload, code scanning, or required-check readiness.",
    },
    {
        "issue": 270,
        "consumer": "workflow/local integration planning",
        "may_consume": [
            "local report artifact names",
            "source report contract",
            "warning carry-forward behavior",
            "handoff metadata",
        ],
        "not_claimed_by_268": "workflow mutation, artifact retention, or changed-file gating.",
    },
]

class ReviewAssistError(RuntimeError):
    """Raised for fail-closed review-assist validation errors."""


@dataclass(frozen=True)
class SourceContract:
    key: str
    path: Path
    required: bool
    expected_schema: str
    require_validation_success: bool
    finding_count_keys: tuple[str, ...] = ("finding_count", "observed_finding_count")


SOURCE_CONTRACTS = {
    "surface_inventory": SourceContract(
        "surface_inventory",
        DEFAULT_SURFACE_INVENTORY,
        True,
        SCHEMA_VERSIONS["surface_inventory"],
        True,
        (),
    ),
    "rule_risk_report": SourceContract(
        "rule_risk_report",
        DEFAULT_RULE_RISK_REPORT,
        True,
        SCHEMA_VERSIONS["rule_risk_report"],
        True,
    ),
    "rule_risk_matrix": SourceContract(
        "rule_risk_matrix",
        DEFAULT_RULE_RISK_MATRIX,
        True,
        SCHEMA_VERSIONS["rule_risk_matrix"],
        False,
        (),
    ),
    "custom_report": SourceContract(
        "custom_report",
        DEFAULT_CUSTOM_REPORT,
        True,
        SCHEMA_VERSIONS["custom_report"],
        True,
    ),
    "assembly_parity_report": SourceContract(
        "assembly_parity_report",
        DEFAULT_ASSEMBLY_PARITY_REPORT,
        True,
        SCHEMA_VERSIONS["assembly_parity_report"],
        True,
        (),
    ),
    "governance_report": SourceContract(
        "governance_report",
        DEFAULT_GOVERNANCE_REPORT,
        True,
        SCHEMA_VERSIONS["governance_report"],
        True,
    ),
    "engine_boundary_report": SourceContract(
        "engine_boundary_report",
        DEFAULT_ENGINE_BOUNDARY_REPORT,
        True,
        SCHEMA_VERSIONS["engine_boundary_report"],
        True,
        (),
    ),
    "analyzer_report": SourceContract(
        "analyzer_report",
        DEFAULT_ANALYZER_REPORT,
        False,
        SCHEMA_VERSIONS["analyzer_report"],
        True,
    ),
    "function_reachability_report": SourceContract(
        "function_reachability_report",
        DEFAULT_FUNCTION_REACHABILITY_REPORT,
        True,
        SCHEMA_VERSIONS["function_reachability_report"],
        True,
        ("function_count",),
    ),
}

def scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)

def slash_path(value: str) -> str:
    return value.strip().replace("\\", "/")

def is_windows_drive_path(value: str) -> bool:
    return len(value) >= 2 and value[0].isalpha() and value[1] == ":"

def path_has_traversal(value: str) -> bool:
    return any(part == ".." for part in value.split("/"))

def resolve_repo_path(value: str | Path, repo_root: Path, label: str) -> tuple[Path, str]:
    normalized = slash_path(value.as_posix() if isinstance(value, Path) else scalar(value))
    if not normalized:
        raise ReviewAssistError(f"{label} path must not be blank")
    if normalized.startswith("/") or is_windows_drive_path(normalized) or path_has_traversal(normalized):
        raise ReviewAssistError(f"{label} path must be repo-relative without traversal: {normalized}")
    parts = tuple(part for part in normalized.split("/") if part)
    candidate = repo_root.joinpath(*parts)
    try:
        candidate.resolve().relative_to(repo_root.resolve())
    except (OSError, RuntimeError, ValueError) as exc:
        raise ReviewAssistError(f"{label} path must resolve inside the repository root: {normalized}") from exc
    return candidate, normalized

def resolve_existing_input_path(value: str | Path, repo_root: Path, label: str) -> tuple[Path, str]:
    path, repo_path = resolve_repo_path(value, repo_root, label)
    if not path.exists():
        raise ReviewAssistError(f"{label} is missing: {repo_path}")
    return path, repo_path

def repo_path_if_safe(value: str, repo_root: Path, label: str) -> str:
    _path, repo_path = resolve_repo_path(value, repo_root, label)
    return repo_path

def resolve_report_output_path(repo_root: Path, output_path: Path, label: str, suffix: str) -> tuple[Path, str]:
    path, repo_path = resolve_repo_path(output_path, repo_root, label)
    if not repo_path.startswith("project_sources/collector/"):
        raise ReviewAssistError(f"{label} must stay under project_sources/collector/: {repo_path}")
    if path.suffix != suffix:
        raise ReviewAssistError(f"{label} must use {suffix} suffix: {repo_path}")
    return path, repo_path

def looks_like_repo_path(value: str) -> bool:
    normalized = slash_path(value)
    return normalized.startswith(SOURCE_PATH_PREFIXES)

def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReviewAssistError(f"{label} is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReviewAssistError(f"{label} is invalid JSON: {path}: {exc}") from exc
    except OSError as exc:
        raise ReviewAssistError(f"{label} could not be read: {path}: {exc}") from exc

def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def validate_source_path_aliases(repo_root: Path, source_paths: dict[str, Path]) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}
    for key, path in source_paths.items():
        try:
            absolute, repo_path = resolve_repo_path(path, repo_root, SOURCE_LABELS[key])
            resolved = absolute.resolve().as_posix()
        except ReviewAssistError as exc:
            errors.append(str(exc))
            continue
        prior = seen.get(resolved)
        if prior:
            errors.append(
                f"duplicate or aliased source report path: {SOURCE_LABELS[prior]} and {SOURCE_LABELS[key]} both use {repo_path}"
            )
        else:
            seen[resolved] = key
    return errors

def validation_state(report: dict[str, Any], repo_path: str) -> tuple[bool, list[str], list[str]]:
    validation = report.get("validation")
    if not isinstance(validation, dict):
        return False, [f"{repo_path} validation must be an object"], []
    errors = validation.get("errors", [])
    warnings = validation.get("warnings", [])
    if not isinstance(errors, list):
        return False, [f"{repo_path} validation.errors must be a list"], []
    if not isinstance(warnings, list):
        return False, [f"{repo_path} validation.warnings must be a list"], []
    success = validation.get("success")
    if success is not True:
        reason = "validation.success is false" if success is False else "validation.success must be boolean true"
        return False, [f"{repo_path} does not report successful validation: {reason}"], [scalar(item) for item in warnings]
    return True, [], [scalar(item) for item in warnings]

def require_object(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    errors.append(f"{label} must be an object")
    return {}

def require_list(value: Any, label: str, errors: list[str]) -> list[Any]:
    if isinstance(value, list):
        return value
    errors.append(f"{label} must be a list")
    return []

def require_field(doc: dict[str, Any], key: str, label: str, errors: list[str]) -> Any:
    if key not in doc:
        errors.append(f"{label} missing {key}")
        return None
    return doc[key]

def summary_finding_count(report: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        return None
    for key in keys:
        value = summary.get(key)
        if isinstance(value, int):
            return value
    findings = report.get("findings")
    if isinstance(findings, list):
        return len(findings)
    return None

def source_entry(
    contract: SourceContract,
    repo_path: str,
    present: bool,
    schema_version: str | None,
    validation_status: str,
    finding_count: int | None,
    warnings: list[str],
    errors: list[str],
    absent_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "source_key": contract.key,
        "source_issue": SOURCE_ISSUES[contract.key],
        "label": SOURCE_LABELS[contract.key],
        "path": repo_path,
        "expected_schema_version": contract.expected_schema,
        "schema_version": schema_version,
        "required": contract.required,
        "present": present,
        "validation_status": validation_status,
        "finding_count": finding_count,
        "warnings": warnings,
        "errors": errors,
        "absent_reason": absent_reason,
    }

from powershell_review_assist_sources import load_source
