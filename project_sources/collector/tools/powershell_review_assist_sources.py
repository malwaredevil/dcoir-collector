#!/usr/bin/env python3
"""Source loading for PowerShell review-assist reports."""
from pathlib import Path
from typing import Any

from powershell_review_assist_common import (
    ReviewAssistError, SOURCE_ISSUES, SOURCE_LABELS, SourceContract, read_json,
    resolve_repo_path, scalar, source_entry, summary_finding_count, validation_state,
)

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
