#!/usr/bin/env python3
"""Path, validation, and source-loading helpers for review-assist reports."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from powershell_review_assist_contract import (
    SCHEMA_VERSION,
    ISSUE_NUMBER,
    PARENT_ISSUE_NUMBER,
    DEFAULT_SCHEMA_PATH,
    DEFAULT_JSON_OUTPUT,
    DEFAULT_MARKDOWN_OUTPUT,
    DEFAULT_SURFACE_INVENTORY,
    DEFAULT_RULE_RISK_REPORT,
    DEFAULT_RULE_RISK_MATRIX,
    DEFAULT_CUSTOM_REPORT,
    DEFAULT_ASSEMBLY_PARITY_REPORT,
    DEFAULT_GOVERNANCE_REPORT,
    DEFAULT_ENGINE_BOUNDARY_REPORT,
    DEFAULT_ANALYZER_REPORT,
    DEFAULT_FUNCTION_REACHABILITY_REPORT,
    SCHEMA_VERSIONS,
    SOURCE_ISSUES,
    SOURCE_LABELS,
    REQUIRED_SOURCE_KEYS,
    SOURCE_PATH_PREFIXES,
    NON_CLAIMS,
    FUTURE_HANDOFF_CONSUMERS,
    ReviewAssistError,
    SourceContract,
    SOURCE_CONTRACTS,
)

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


def load_source(
    repo_root: Path,
    contract: SourceContract,
    relative_path: Path,
    errors: list[str],
    carried_forward_warnings: list[dict[str, Any]],
    missing_artifacts: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    label = SOURCE_LABELS[contract.key]
    try:
        absolute, repo_path = resolve_repo_path(relative_path, repo_root, label)
    except ReviewAssistError as exc:
        errors.append(str(exc))
        return None, source_entry(contract, relative_path.as_posix(), False, None, "path_error", None, [], [str(exc)])
    if not absolute.exists():
        reason = (
            "optional analyzer evidence is absent; #268 does not claim live PSScriptAnalyzer evidence"
            if not contract.required
            else "required source report is missing"
        )
        entry = source_entry(
            contract,
            repo_path,
            False,
            None,
            "optional_missing" if not contract.required else "missing",
            0,
            [],
            [],
            reason,
        )
        missing_artifacts.append(
            {
                "source_issue": SOURCE_ISSUES[contract.key],
                "path": repo_path,
                "required": contract.required,
                "reason": reason,
            }
        )
        if contract.required:
            errors.append(f"{label} is missing: {repo_path}")
        else:
            carried_forward_warnings.append(
                {
                    "source_issue": SOURCE_ISSUES[contract.key],
                    "source_report": repo_path,
                    "warning": reason,
                }
            )
        return None, entry
    try:
        doc = read_json(absolute, label)
    except ReviewAssistError as exc:
        errors.append(str(exc))
        return None, source_entry(contract, repo_path, True, None, "read_error", None, [], [str(exc)])
    if not isinstance(doc, dict):
        message = f"{repo_path} must be a JSON object"
        errors.append(message)
        return None, source_entry(contract, repo_path, True, None, "malformed", None, [], [message])
    schema = scalar(doc.get("schema_version")).strip()
    local_errors: list[str] = []
    local_warnings: list[str] = []
    if schema != contract.expected_schema:
        local_errors.append(f"{repo_path} schema mismatch: expected {contract.expected_schema}, got {schema!r}")
    if contract.require_validation_success:
        success, validation_errors, validation_warnings = validation_state(doc, repo_path)
        local_warnings.extend(validation_warnings)
        if not success:
            local_errors.extend(validation_errors)
    else:
        if "validation" in doc:
            success, validation_errors, validation_warnings = validation_state(doc, repo_path)
            local_warnings.extend(validation_warnings)
            if not success:
                local_errors.extend(validation_errors)
    for warning in local_warnings:
        carried_forward_warnings.append(
            {
                "source_issue": SOURCE_ISSUES[contract.key],
                "source_report": repo_path,
                "warning": warning,
            }
        )
    errors.extend(local_errors)
    if contract.key == "analyzer_report" and doc:
        carried_forward_warnings.append(
            {
                "source_issue": 262,
                "source_report": repo_path,
                "warning": "Optional analyzer report is present and was validated as explicit analyzer evidence.",
            }
        )
    validation_status = "success" if not local_errors else "failed"
    if not contract.require_validation_success and not local_errors:
        validation_status = "schema_only_success"
    return doc, source_entry(
        contract,
        repo_path,
        True,
        schema,
        validation_status,
        summary_finding_count(doc, contract.finding_count_keys),
        local_warnings,
        local_errors,
    )


__all__ = ['scalar', 'slash_path', 'is_windows_drive_path', 'path_has_traversal', 'resolve_repo_path', 'resolve_existing_input_path', 'repo_path_if_safe', 'resolve_report_output_path', 'looks_like_repo_path', 'read_json', 'write_json', 'validate_source_path_aliases', 'validation_state', 'require_object', 'require_list', 'require_field', 'summary_finding_count', 'source_entry', 'load_source']
