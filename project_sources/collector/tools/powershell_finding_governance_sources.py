#!/usr/bin/env python3
"""Source-report ingestion for PowerShell finding governance."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from powershell_finding_governance_common import (
    ASSEMBLY_PARITY_SCHEMA_VERSION,
    Finding,
    GovernanceError,
    REPORT_SCHEMAS,
    read_json,
    resolve_repo_input_path,
    scalar,
    sha256_text,
    slash_path,
    validate_governance_path,
)


def load_doc(repo_root: Path, relative_path: Path, label: str) -> tuple[dict[str, Any], str]:
    absolute_path, repo_path, path_error = resolve_repo_input_path(relative_path.as_posix(), repo_root, label)
    if path_error:
        raise GovernanceError(f"{label} {path_error}: {relative_path.as_posix()}")
    if absolute_path is None:
        raise GovernanceError(f"{label} path could not be resolved: {relative_path.as_posix()}")
    doc = read_json(absolute_path, label)
    if not isinstance(doc, dict):
        raise GovernanceError(f"{label} must be a JSON object: {repo_path}")
    return doc, repo_path


def load_optional_doc(
    repo_root: Path,
    relative_path: Path,
    label: str,
    warnings: list[str],
) -> tuple[dict[str, Any] | None, str]:
    absolute_path, repo_path, path_error = resolve_repo_input_path(relative_path.as_posix(), repo_root, label)
    if path_error:
        raise GovernanceError(f"{label} {path_error}: {relative_path.as_posix()}")
    if absolute_path is None:
        raise GovernanceError(f"{label} path could not be resolved: {relative_path.as_posix()}")
    if not absolute_path.exists():
        warnings.append(f"optional {label} not present: {repo_path}")
        return None, repo_path
    doc = read_json(absolute_path, label)
    if not isinstance(doc, dict):
        raise GovernanceError(f"{label} must be a JSON object: {repo_path}")
    return doc, repo_path


def report_validation_success_state(report: dict[str, Any]) -> tuple[bool, str]:
    validation = report.get("validation")
    if not isinstance(validation, dict):
        return False, "validation must be an object with success=true"
    if "success" not in validation:
        return False, "validation.success is missing"
    success = validation.get("success")
    if success is True:
        return True, "validation.success is true"
    if success is False:
        return False, "validation.success is false"
    return False, "validation.success must be boolean true"


def validate_assembly_parity_report(repo_root: Path, repo_path: str, report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema = scalar(report.get("schema_version")).strip()
    if schema != ASSEMBLY_PARITY_SCHEMA_VERSION:
        errors.append(f"{repo_path} schema mismatch: expected {ASSEMBLY_PARITY_SCHEMA_VERSION}, got {schema!r}")
    success, success_reason = report_validation_success_state(report)
    if not success:
        errors.append(f"{repo_path} does not report successful validation: {success_reason}")
    generated_outputs = report.get("generated_outputs", [])
    if generated_outputs is not None and not isinstance(generated_outputs, list):
        errors.append(f"{repo_path} generated_outputs must be a list when present")
    elif isinstance(generated_outputs, list):
        for index, output in enumerate(generated_outputs, start=1):
            if not isinstance(output, dict):
                continue
            output_path = scalar(output.get("path")).strip()
            if not output_path:
                continue
            _candidate, _normalized_output_path, path_error = resolve_repo_input_path(
                output_path,
                repo_root,
                "PowerShell assembly parity generated output",
            )
            if path_error:
                errors.append(f"{repo_path} generated_outputs[{index}] {path_error}: {output_path}")
    return errors


def stable_fingerprint(source_report: str, raw: dict[str, Any]) -> str:
    basis = {
        "source_report": source_report,
        "path": scalar(raw.get("path") or raw.get("target_path")),
        "rule_name": scalar(raw.get("rule_name")),
        "check_id": scalar(raw.get("check_id") or raw.get("matrix_check_id")),
        "line": raw.get("line"),
        "severity": scalar(raw.get("severity")),
        "observed_problem": scalar(raw.get("observed_problem") or raw.get("message")),
    }
    return sha256_text(json.dumps(basis, sort_keys=True, separators=(",", ":")))


def normalize_finding(raw: dict[str, Any], source_report: str, source_schema: str, repo_root: Path) -> Finding:
    if not isinstance(raw, dict):
        raise GovernanceError(f"{source_report} finding must be an object")
    raw_path = scalar(raw.get("path") or raw.get("target_path")).strip()
    if not raw_path:
        raise GovernanceError(f"{source_report} finding missing path")
    path = validate_governance_path(raw_path, repo_root, f"{source_report} finding")
    rule_name = scalar(raw.get("rule_name") or raw.get("rule")).strip()
    check_id = scalar(raw.get("check_id") or raw.get("matrix_check_id")).strip()
    severity = scalar(raw.get("severity") or "Warning").strip()
    if not rule_name and not check_id:
        raise GovernanceError(f"{source_report} finding missing rule_name/check_id for {path}")
    if not severity:
        raise GovernanceError(f"{source_report} finding missing severity for {path}")
    line_value = raw.get("line")
    column_value = raw.get("column")
    line = int(line_value) if isinstance(line_value, int) or str(line_value).isdigit() else None
    column = int(column_value) if isinstance(column_value, int) or str(column_value).isdigit() else None
    return Finding(
        source_report=source_report,
        source_schema_version=source_schema,
        path=path,
        line=line,
        column=column,
        rule_name=rule_name,
        check_id=check_id,
        severity=severity,
        fingerprint=scalar(raw.get("fingerprint")).strip() or stable_fingerprint(source_report, raw),
        observed_problem=scalar(raw.get("observed_problem") or raw.get("message")).strip(),
        recommended_fix=scalar(raw.get("recommended_fix") or raw.get("fix")).strip(),
        raw=raw,
    )


def collect_findings(
    repo_root: Path,
    required_reports: list[Path],
    optional_reports: list[Path],
    errors: list[str],
    warnings: list[str],
) -> tuple[list[Finding], list[dict[str, Any]]]:
    findings: list[Finding] = []
    input_reports: list[dict[str, Any]] = []

    def process_report(report_path: Path, required: bool, missing_is_warning: bool) -> None:
        label = "PowerShell finding report"
        try:
            if missing_is_warning:
                doc, repo_path = load_optional_doc(repo_root, report_path, label, warnings)
            else:
                doc, repo_path = load_doc(repo_root, report_path, label)
        except GovernanceError as exc:
            errors.append(str(exc))
            return
        if doc is None:
            input_reports.append(
                {
                    "path": repo_path,
                    "schema_version": None,
                    "finding_count": 0,
                    "required": required,
                    "present": False,
                    "validation_success": None,
                }
            )
            return
        report_findings = doc.get("findings")
        if not isinstance(report_findings, list):
            qualifier = "optional " if missing_is_warning else ""
            errors.append(f"{qualifier}PowerShell finding report has no findings list: {repo_path}")
            return
        schema = scalar(doc.get("schema_version")).strip()
        success, success_reason = report_validation_success_state(doc)
        input_reports.append(
            {
                "path": repo_path,
                "schema_version": schema,
                "finding_count": len(report_findings),
                "required": required,
                "present": True,
                "validation_success": success,
            }
        )
        expected_schema = REPORT_SCHEMAS.get(repo_path)
        schema_valid = True
        if expected_schema and schema != expected_schema:
            errors.append(f"{repo_path} schema mismatch: expected {expected_schema}, got {schema!r}")
            schema_valid = False
        if not success:
            errors.append(f"{repo_path} does not report successful validation: {success_reason}")
        if not schema_valid or not success:
            return
        for raw in report_findings:
            try:
                findings.append(normalize_finding(raw, repo_path, schema, repo_root))
            except GovernanceError as exc:
                errors.append(str(exc))

    for report_path in required_reports:
        process_report(report_path, required=True, missing_is_warning=False)
    for report_path in optional_reports:
        process_report(report_path, required=False, missing_is_warning=True)
    return findings, input_reports


def generated_output_paths(assembly_report: dict[str, Any] | None) -> set[str]:
    if not isinstance(assembly_report, dict):
        return set()
    return {
        slash_path(scalar(output.get("path")).strip())
        for output in assembly_report.get("generated_outputs", [])
        if isinstance(output, dict) and scalar(output.get("path")).strip()
    }
