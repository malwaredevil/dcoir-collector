#!/usr/bin/env python3
"""Report construction and rendering helpers for PowerShell engine/Pester boundary validation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from powershell_engine_pester_boundary_contract import (
    EngineBoundaryError,
    ISSUE_NUMBER,
    PARENT_ISSUE_NUMBER,
    REQUIRED_CHECK_CATEGORIES,
    SCHEMA_VERSION,
    read_json,
    resolve_repo_input_path,
    safe_repo_path,
    scalar,
)
from powershell_engine_pester_boundary_validation import (
    declared_output_artifacts,
    validate_boundary_doc,
    validate_source_reports,
)


def write_outputs(repo_root: Path, report: dict[str, Any], json_output: Path, markdown_output: Path) -> list[str]:
    errors: list[str] = []
    json_path, _json_repo_path, json_error = resolve_repo_input_path(
        json_output.as_posix(),
        repo_root,
        "PowerShell engine/Pester boundary JSON report output",
    )
    markdown_path, _markdown_repo_path, markdown_error = resolve_repo_input_path(
        markdown_output.as_posix(),
        repo_root,
        "PowerShell engine/Pester boundary Markdown report output",
    )
    if json_error:
        errors.append(f"PowerShell engine/Pester boundary JSON report output {json_error}: {json_output.as_posix()}")
    if markdown_error:
        errors.append(f"PowerShell engine/Pester boundary Markdown report output {markdown_error}: {markdown_output.as_posix()}")
    if json_path is not None and markdown_path is not None:
        try:
            if json_path.resolve() == markdown_path.resolve():
                errors.append("PowerShell engine/Pester boundary JSON and Markdown report output paths must be different")
        except (OSError, RuntimeError):
            errors.append("PowerShell engine/Pester boundary report output paths must resolve inside the repository root")
    if errors:
        return errors
    outputs = [
        (json_path, json.dumps(report, indent=2, sort_keys=True) + "\n"),
        (markdown_path, build_markdown(report)),
    ]
    for path, content in outputs:
        if path is None:
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            errors.append(f"PowerShell engine/Pester boundary report write failure: {safe_repo_path(path, repo_root)}: {exc}")
    return errors


def build_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# PowerShell Engine and Pester Boundary Report",
        "",
        f"- Schema: `{report['schema_version']}`",
        f"- Issue: `#{report['issue']}`",
        f"- Validation: `{'pass' if report['validation']['success'] else 'fail'}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Matrix rows | {summary['matrix_row_count']} |",
        f"| Required categories covered | {summary['required_category_count']} / {summary['expected_required_category_count']} |",
        f"| Dependency reports | {summary['dependency_report_count']} |",
        f"| Declared output artifacts | {summary['declared_output_artifact_count']} |",
        f"| Missing blocking output artifacts | {summary['missing_blocking_output_artifact_count']} |",
        f"| Unclaimed blocking output artifacts | {summary['unclaimed_blocking_output_artifact_count']} |",
        f"| Pester blocking for static validation | `{summary['pester_blocking_for_static_validation']}` |",
        f"| Independent enforcement requires Pester | `{summary['independent_enforcement_requires_pester']}` |",
        "",
        "## Engine Matrix",
        "",
        "| Check | Engine | Runner | Evidence | Blocking | Owner |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["engine_matrix"]:
        lines.append(
            "| `{id}` | {engine} | {runner} | {evidence} | `{blocking}` | {owner} |".format(
                id=row["id"],
                engine=row["required_engine"],
                runner=row["runner_os"],
                evidence=row["evidence_type"],
                blocking=row["blocking"],
                owner=row["owner"],
            )
        )
    lines.extend(
        [
            "",
            "## Declared Output Artifacts",
            "",
            "| Check | Artifact | Repo path | Exists | Claimed by #267 boundary | Status |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for artifact in report["declared_output_artifacts"]:
        lines.append(
            "| `{id}` | `{path}` | `{repo_path}` | `{exists}` | `{claimed}` | `{status}` |".format(
                id=artifact["id"],
                path=artifact["path"],
                repo_path=artifact["repo_path"],
                exists=artifact["exists"],
                claimed=artifact["evidence_claimed_by_boundary"],
                status=artifact["artifact_status"],
            )
        )
    lines.extend(
        [
            "",
            "## Pester Boundary",
            "",
            f"- Decision: `{report['pester_boundary']['scope_decision']}`",
            f"- Static-security blocking: `{report['pester_boundary']['blocking_for_static_security_validation']}`",
            f"- Analyzer/custom-check substitute: `{report['pester_boundary']['pester_may_replace_analyzer_or_custom_checks']}`",
            "",
            "## Independent Analyzer Enforcement Proof",
            "",
            "| Proof | Count/State |",
            "| --- | ---: |",
        ]
    )
    proof = report["independent_analyzer_enforcement_proof"]
    lines.extend(
        [
            f"| Rule-risk fixture findings | {proof['rule_risk_fixture_findings']} |",
            f"| Custom-check findings | {proof['custom_check_findings']} |",
            f"| Governance classified findings | {proof['governance_classified_findings']} |",
            f"| Governance unclassified findings | {proof['governance_unclassified_findings']} |",
            f"| Assembly parity success | `{proof['assembly_parity_success']}` |",
            f"| Requires Pester | `{proof['requires_pester']}` |",
            "",
            "## Dependency Reports",
            "",
            "| Report | Schema | Success | Findings |",
            "| --- | --- | --- | ---: |",
        ]
    )
    for dependency in report["dependency_reports"]:
        lines.append(
            f"| `{dependency['path']}` | `{dependency['schema_version']}` | `{dependency['success']}` | {dependency['finding_count']} |"
        )
    if report["validation"]["warnings"]:
        lines.extend(["", "## Warnings", ""])
        for warning in report["validation"]["warnings"]:
            lines.append(f"- {warning}")
    if report["validation"]["errors"]:
        lines.extend(["", "## Errors", ""])
        for error in report["validation"]["errors"]:
            lines.append(f"- {error}")
    lines.append("")
    return "\n".join(lines)


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], list[str], list[str]]:
    repo_root = Path(args.repo_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    boundary_policy_path = str(args.boundary)
    try:
        boundary_path, boundary_policy_path, boundary_path_error = resolve_repo_input_path(
            str(args.boundary), repo_root, "PowerShell engine/Pester boundary"
        )
        if boundary_path_error:
            raise EngineBoundaryError(f"PowerShell engine/Pester boundary {boundary_path_error}: {args.boundary}")
        if boundary_path is None:
            raise EngineBoundaryError(f"PowerShell engine/Pester boundary path could not be resolved: {args.boundary}")
        boundary = read_json(boundary_path, "PowerShell engine/Pester boundary")
    except EngineBoundaryError as exc:
        boundary = {}
        errors.append(str(exc))
    if not isinstance(boundary, dict):
        errors.append("PowerShell engine/Pester boundary must be a JSON object")
        boundary = {}

    boundary_errors, boundary_warnings, metadata = validate_boundary_doc(boundary)
    errors.extend(boundary_errors)
    warnings.extend(boundary_warnings)

    source_reports = metadata.get("source_reports", [])
    dependency_reports, dependency_errors, dependency_warnings, proof_counts = validate_source_reports(
        repo_root,
        [str(path) for path in source_reports],
        [Path(path) for path in args.extra_report],
    )
    errors.extend(dependency_errors)
    warnings.extend(dependency_warnings)

    matrix_rows = metadata.get("matrix_rows", [])
    output_artifacts, artifact_errors, artifact_warnings = declared_output_artifacts(repo_root, matrix_rows)
    errors.extend(artifact_errors)
    warnings.extend(artifact_warnings)
    pester = boundary.get("pester_boundary", {}) if isinstance(boundary.get("pester_boundary"), dict) else {}
    policy = boundary.get("policy", {}) if isinstance(boundary.get("policy"), dict) else {}
    required_categories_covered = {
        scalar(row.get("check_category")).strip()
        for row in matrix_rows
        if scalar(row.get("check_category")).strip() in REQUIRED_CHECK_CATEGORIES
    }
    missing_blocking_artifacts = [
        artifact
        for artifact in output_artifacts
        if artifact["repo_path"] and artifact["blocking"] is True and artifact["exists"] is False
    ]
    unclaimed_blocking_artifacts = [
        artifact
        for artifact in output_artifacts
        if artifact["blocking"] is True and artifact["evidence_claimed_by_boundary"] is False
    ]
    proof = dict(proof_counts)
    proof["requires_pester"] = bool(
        isinstance(boundary.get("independent_analyzer_enforcement_proof"), dict)
        and boundary["independent_analyzer_enforcement_proof"].get("requires_pester") is True
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "issue": ISSUE_NUMBER,
        "parent_issue": PARENT_ISSUE_NUMBER,
        "boundary_policy_path": boundary_policy_path,
        "summary": {
            "matrix_row_count": len(matrix_rows),
            "required_category_count": len(required_categories_covered),
            "expected_required_category_count": len(REQUIRED_CHECK_CATEGORIES),
            "dependency_report_count": len(dependency_reports),
            "pester_blocking_for_static_validation": pester.get("blocking_for_static_security_validation"),
            "independent_enforcement_requires_pester": proof["requires_pester"],
            "workflow_readiness_claimed": policy.get("workflow_readiness_claimed"),
            "declared_output_artifact_count": len(output_artifacts),
            "missing_blocking_output_artifact_count": len(missing_blocking_artifacts),
            "unclaimed_blocking_output_artifact_count": len(unclaimed_blocking_artifacts),
        },
        "engine_matrix": matrix_rows,
        "declared_output_artifacts": output_artifacts,
        "pester_boundary": {
            "scope_decision": scalar(pester.get("scope_decision")).strip(),
            "blocking_for_static_security_validation": pester.get("blocking_for_static_security_validation"),
            "pester_may_replace_analyzer_or_custom_checks": policy.get(
                "pester_may_replace_analyzer_or_custom_checks"
            ),
            "required_evidence_when_used": pester.get("required_evidence_when_used", []),
            "owned_responsibilities": pester.get("owned_responsibilities", []),
        },
        "independent_analyzer_enforcement_proof": proof,
        "dependency_reports": dependency_reports,
        "validation": {
            "success": not errors,
            "errors": errors,
            "warnings": warnings,
        },
    }
    return report, errors, warnings


__all__ = [
    "build_markdown",
    "build_report",
    "write_outputs",
]
