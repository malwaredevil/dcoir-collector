#!/usr/bin/env python3
"""Report assembly and output persistence for PowerShell review-assist reports."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from powershell_review_assist_common import (
    DEFAULT_SCHEMA_PATH,
    ISSUE_NUMBER,
    NON_CLAIMS,
    PARENT_ISSUE_NUMBER,
    REQUIRED_SOURCE_KEYS,
    SCHEMA_VERSION,
    SOURCE_CONTRACTS,
    ReviewAssistError,
    load_source,
    read_json,
    resolve_report_output_path,
    resolve_repo_path,
    scalar,
    validate_source_path_aliases,
    write_json,
)
from powershell_review_assist_findings import (
    collect_normalized_findings,
    collect_unclaimed_artifacts,
    evidence_channels,
    surface_inventory_section,
    validate_normalized_findings,
)
from powershell_review_assist_rendering import (
    artifact_contract,
    render_markdown,
    validate_against_schema_contract,
    validate_markdown_parity,
)
from powershell_review_assist_validators import validate_loaded_sources

def count_required_present(source_reports: list[dict[str, Any]]) -> int:
    return len([entry for entry in source_reports if entry["required"] and entry["present"]])

def summarize(source_reports: list[dict[str, Any]], findings: list[dict[str, Any]], warnings: list[dict[str, Any]], missing: list[dict[str, Any]], unclaimed: list[dict[str, Any]]) -> dict[str, Any]:
    severity_counts = Counter(finding["severity"] for finding in findings)
    evidence_counts = Counter(finding["evidence_kind"] for finding in findings)
    governance_counts = Counter(finding["governance_classification"] for finding in findings)
    return {
        "required_source_report_count": len([entry for entry in source_reports if entry["required"]]),
        "required_source_reports_present": count_required_present(source_reports),
        "optional_source_reports_missing": len([entry for entry in source_reports if not entry["required"] and not entry["present"]]),
        "source_report_count": len(source_reports),
        "normalized_finding_count": len(findings),
        "finding_count_by_evidence_kind": dict(sorted(evidence_counts.items())),
        "finding_count_by_severity": dict(sorted(severity_counts.items())),
        "finding_count_by_governance_classification": dict(sorted(governance_counts.items())),
        "carried_forward_warning_count": len(warnings),
        "missing_artifact_count": len(missing),
        "unclaimed_artifact_count": len(unclaimed),
        "non_claim_count": len(NON_CLAIMS),
        "validation_success": True,
    }

def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], list[str], list[str]]:
    repo_root = Path(args.repo_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    carried_forward_warnings: list[dict[str, Any]] = []
    missing_artifacts: list[dict[str, Any]] = []
    source_paths = {
        "surface_inventory": Path(args.surface_inventory),
        "rule_risk_report": Path(args.rule_risk_report),
        "rule_risk_matrix": Path(args.rule_risk_matrix),
        "custom_report": Path(args.custom_report),
        "assembly_parity_report": Path(args.assembly_parity_report),
        "governance_report": Path(args.governance_report),
        "engine_boundary_report": Path(args.engine_boundary_report),
        "function_reachability_report": Path(args.function_reachability_report),
        "analyzer_report": Path(args.analyzer_report),
    }
    errors.extend(validate_source_path_aliases(repo_root, source_paths))
    docs: dict[str, dict[str, Any]] = {}
    source_reports: list[dict[str, Any]] = []
    for key in (*REQUIRED_SOURCE_KEYS, "analyzer_report"):
        doc, entry = load_source(
            repo_root,
            SOURCE_CONTRACTS[key],
            source_paths[key],
            errors,
            carried_forward_warnings,
            missing_artifacts,
        )
        if doc is not None:
            docs[key] = doc
        source_reports.append(entry)
    validate_loaded_sources(repo_root, docs, source_reports, errors)
    source_report_paths = {entry["source_key"]: entry["path"] for entry in source_reports}
    findings = collect_normalized_findings(docs, source_report_paths) if not errors else []
    errors.extend(validate_normalized_findings(findings))
    engine_report = docs.get("engine_boundary_report", {})
    unclaimed_artifacts = collect_unclaimed_artifacts(engine_report)
    for item in unclaimed_artifacts:
        carried_forward_warnings.append(
            {
                "source_issue": item["source_issue"],
                "source_report": source_report_paths.get("engine_boundary_report"),
                "warning": f"{item.get('path')}: {item.get('artifact_status')} is not claimed by #267/#268",
            }
        )
    rule_risk = docs.get("rule_risk_report", {})
    if scalar(rule_risk.get("environment_gap")).strip():
        carried_forward_warnings.append(
            {
                "source_issue": 263,
                "source_report": source_report_paths.get("rule_risk_report"),
                "warning": scalar(rule_risk.get("environment_gap")).strip(),
            }
        )
    source_entry_by_key = {entry["source_key"]: entry for entry in source_reports}
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "issue": ISSUE_NUMBER,
        "parent_issue": PARENT_ISSUE_NUMBER,
        "depends_on": [261, 263, 264, 265, 266, 267, 306],
        "generated_from": {
            "tool": "project_sources/collector/tools/run_powershell_review_assist_report.py",
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "source_reports": [entry["path"] for entry in source_reports],
            "schema_contract": DEFAULT_SCHEMA_PATH.as_posix(),
        },
        "source_reports": source_reports,
        "summary": {},
        "changed_file_context": {
            "changed_file_count": None,
            "changed_file_surface_count": None,
            "unavailable_reason": "No validated changed-file inventory or base/head changed-file source was supplied to #268.",
            "claim": "Full-scope inventory counts are present; changed-file execution or gating is not claimed.",
        },
        "surface_inventory": surface_inventory_section(docs.get("surface_inventory", {})),
        "findings": findings,
        "evidence_channels": evidence_channels(docs, source_entry_by_key, findings),
        "carried_forward_warnings": carried_forward_warnings,
        "missing_artifacts": missing_artifacts,
        "unclaimed_artifacts": unclaimed_artifacts,
        "non_claims": list(NON_CLAIMS),
        "artifact_contract": artifact_contract(),
        "validation": {
            "success": False,
            "errors": errors,
            "warnings": warnings,
        },
    }
    report["summary"] = summarize(source_reports, findings, carried_forward_warnings, missing_artifacts, unclaimed_artifacts)
    if errors:
        report["summary"]["validation_success"] = False
        report["validation"]["success"] = False
        return report, errors, warnings
    report["validation"]["success"] = True
    report["summary"]["validation_success"] = True
    markdown = render_markdown(report)
    parity_errors = validate_markdown_parity(report, markdown)
    try:
        schema_path, _schema_repo_path = resolve_repo_path(Path(args.schema), repo_root, "PowerShell review-assist schema")
    except ReviewAssistError as exc:
        parity_errors.append(str(exc))
        schema_path = None
    if schema_path is not None and schema_path.exists():
        try:
            schema = read_json(schema_path, "PowerShell review-assist schema")
            if isinstance(schema, dict):
                schema_errors = validate_against_schema_contract(report, schema)
                parity_errors.extend(schema_errors)
            else:
                parity_errors.append("PowerShell review-assist schema must be a JSON object")
        except ReviewAssistError as exc:
            parity_errors.append(str(exc))
    elif schema_path is not None:
        parity_errors.append(f"PowerShell review-assist schema is missing: {args.schema}")
    report["validation"]["errors"].extend(parity_errors)
    report["validation"]["success"] = not report["validation"]["errors"]
    report["summary"]["validation_success"] = report["validation"]["success"]
    return report, report["validation"]["errors"], warnings

def mark_report_write_failure(report: dict[str, Any], message: str) -> None:
    report.setdefault("validation", {})["success"] = False
    report.setdefault("summary", {})["validation_success"] = False
    errors = report["validation"].setdefault("errors", [])
    if isinstance(errors, list):
        errors.append(message)
    else:
        report["validation"]["errors"] = [message]

def write_outputs(repo_root: Path, report: dict[str, Any], json_output: Path, markdown_output: Path) -> None:
    json_path, json_repo_path = resolve_report_output_path(
        repo_root,
        json_output,
        "PowerShell review-assist JSON report output",
        ".json",
    )
    markdown_path, markdown_repo_path = resolve_report_output_path(
        repo_root,
        markdown_output,
        "PowerShell review-assist Markdown report output",
        ".md",
    )
    try:
        if json_path.resolve() == markdown_path.resolve():
            raise ReviewAssistError("PowerShell review-assist JSON and Markdown report output paths must be different")
    except OSError as exc:
        raise ReviewAssistError("PowerShell review-assist output paths must resolve inside the repository root") from exc
    markdown = render_markdown(report)
    try:
        write_json(json_path, report)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
    except OSError as exc:
        message = f"PowerShell review-assist report write failure: {exc}"
        mark_report_write_failure(report, message)
        try:
            write_json(json_path, report)
        except OSError as rewrite_exc:
            mark_report_write_failure(report, f"failed to persist failed JSON status: {rewrite_exc}")
            raise ReviewAssistError(f"{message}; failed to persist failed JSON status: {rewrite_exc}") from rewrite_exc
        raise ReviewAssistError(f"{message}; failed report persisted to {json_repo_path}") from exc
    if json_repo_path == markdown_repo_path:
        raise ReviewAssistError("PowerShell review-assist JSON and Markdown report output paths must be different")
