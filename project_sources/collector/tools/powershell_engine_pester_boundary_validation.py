#!/usr/bin/env python3
"""Boundary document and dependency-report validation helpers."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from powershell_engine_pester_boundary_contract import (
    BOUNDARY_SCHEMA_VERSION,
    DEFAULT_ASSEMBLY_REPORT,
    DEFAULT_CUSTOM_REPORT,
    DEFAULT_GOVERNANCE_REPORT,
    DEFAULT_RULE_RISK_REPORT,
    EngineBoundaryError,
    EXPLICIT_ARTIFACT_STATUSES,
    ISSUE_NUMBER,
    PARENT_ISSUE_NUMBER,
    PESTER_EVIDENCE_FIELDS,
    REPORT_SCHEMAS,
    REQUIRED_CHECK_CATEGORIES,
    REQUIRED_MATRIX_FIELDS,
    is_repo_artifact_path,
    read_json,
    report_finding_count,
    report_success,
    report_success_state,
    resolve_repo_artifact_path,
    resolve_repo_input_path,
    scalar,
    summary_count,
)


def has_text(value: Any) -> bool:
    return bool(scalar(value).strip())


def fail_if_missing_fields(prefix: str, item: dict[str, Any], fields: tuple[str, ...], errors: list[str]) -> None:
    for field in fields:
        if field not in item or (field != "blocking" and not has_text(item.get(field))):
            errors.append(f"{prefix} missing {field}")


def validate_boundary_doc(boundary: dict[str, Any]) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    if boundary.get("schema_version") != BOUNDARY_SCHEMA_VERSION:
        errors.append(
            "PowerShell engine/Pester boundary schema mismatch: "
            f"expected {BOUNDARY_SCHEMA_VERSION}, got {boundary.get('schema_version')!r}"
        )
    if boundary.get("issue") != ISSUE_NUMBER:
        errors.append(f"PowerShell engine/Pester boundary issue must be {ISSUE_NUMBER}")
    if boundary.get("parent_issue") != PARENT_ISSUE_NUMBER:
        errors.append(f"PowerShell engine/Pester boundary parent_issue must be {PARENT_ISSUE_NUMBER}")
    policy = boundary.get("policy")
    if not isinstance(policy, dict):
        errors.append("PowerShell engine/Pester boundary policy must be an object")
        policy = {}
    if policy.get("workflow_readiness_claimed") is not False:
        errors.append("workflow readiness must not be claimed by #267 boundary artifacts")
    if policy.get("pester_may_replace_analyzer_or_custom_checks") is not False:
        errors.append("Pester must not be allowed to replace analyzer or custom-check enforcement")
    if policy.get("engine_evidence_must_be_separate") is not True:
        errors.append("engine evidence separation must be required")
    if policy.get("independent_analyzer_enforcement_required") is not True:
        errors.append("independent analyzer enforcement proof must be required")

    matrix = boundary.get("engine_matrix")
    if not isinstance(matrix, list) or not matrix:
        errors.append("engine_matrix must be a non-empty list")
        matrix = []
    seen_categories: set[str] = set()
    matrix_rows: list[dict[str, Any]] = []
    for index, row in enumerate(matrix, start=1):
        if not isinstance(row, dict):
            errors.append(f"engine_matrix[{index}] must be an object")
            continue
        row_id = scalar(row.get("id")).strip() or f"<row-{index}>"
        fail_if_missing_fields(f"engine matrix row {row_id}", row, REQUIRED_MATRIX_FIELDS, errors)
        category = scalar(row.get("check_category")).strip()
        if category:
            if category in seen_categories:
                errors.append(f"duplicate engine matrix category {category}")
            seen_categories.add(category)
        if not isinstance(row.get("blocking"), bool):
            errors.append(f"engine matrix row {row_id} blocking must be boolean")
        engine = scalar(row.get("required_engine")).strip().casefold()
        runner_os = scalar(row.get("runner_os")).strip()
        if engine in {"pwsh", "powershell", "powershell core", "windows powershell"}:
            errors.append(f"engine matrix row {row_id} uses ambiguous engine {row.get('required_engine')!r}")
        if "windows powerShell 5.1".casefold() in engine and "windows" not in runner_os.casefold():
            errors.append(f"engine matrix row {row_id} asserts Windows PowerShell 5.1 without Windows runner")
        matrix_rows.append(row)
    missing_categories = sorted(REQUIRED_CHECK_CATEGORIES - seen_categories)
    if missing_categories:
        errors.append(f"engine_matrix missing categories: {', '.join(missing_categories)}")

    pester = boundary.get("pester_boundary")
    if not isinstance(pester, dict):
        errors.append("pester_boundary must be an object")
        pester = {}
    if scalar(pester.get("scope_decision")).strip() not in {
        "supporting-in-scope-not-analyzer-substitute",
        "out-of-scope-for-260-static-validation",
    }:
        errors.append("pester_boundary scope_decision must explicitly define in-scope or out-of-scope status")
    if pester.get("blocking_for_static_security_validation") is not False:
        errors.append("Pester must not be blocking for static security validation in #267")
    must_not_replace = {
        scalar(item).strip()
        for item in pester.get("must_not_replace", [])
        if scalar(item).strip()
    }
    for required in ("#262 analyzer wrapper enforcement", "#264 DCOIR custom checks"):
        if required not in must_not_replace:
            errors.append(f"pester_boundary must_not_replace missing {required}")
    evidence = {
        scalar(item).strip()
        for item in pester.get("required_evidence_when_used", [])
        if scalar(item).strip()
    }
    missing_evidence = sorted(PESTER_EVIDENCE_FIELDS - evidence)
    if missing_evidence:
        errors.append(f"pester_boundary required_evidence_when_used missing: {', '.join(missing_evidence)}")
    responsibilities = pester.get("owned_responsibilities")
    if not isinstance(responsibilities, list) or not responsibilities:
        errors.append("pester_boundary owned_responsibilities must be a non-empty list")
    else:
        for index, responsibility in enumerate(responsibilities, start=1):
            if not isinstance(responsibility, dict):
                errors.append(f"pester responsibility {index} must be an object")
                continue
            fail_if_missing_fields(
                f"pester responsibility {scalar(responsibility.get('surface')).strip() or index}",
                responsibility,
                ("surface", "owner", "blocking", "notes"),
                errors,
            )
            if not isinstance(responsibility.get("blocking"), bool):
                errors.append(f"pester responsibility {index} blocking must be boolean")

    proof = boundary.get("independent_analyzer_enforcement_proof")
    if not isinstance(proof, dict):
        errors.append("independent_analyzer_enforcement_proof must be an object")
        proof = {}
    if proof.get("requires_pester") is not False:
        errors.append("independent analyzer enforcement proof must not require Pester")
    source_reports = proof.get("source_reports")
    if not isinstance(source_reports, list) or not source_reports:
        errors.append("independent analyzer enforcement proof source_reports must be a non-empty list")
        source_reports = []
    if not isinstance(proof.get("required_conditions"), list) or not proof.get("required_conditions"):
        errors.append("independent analyzer enforcement proof required_conditions must be a non-empty list")

    metadata = {
        "matrix_rows": matrix_rows,
        "category_counts": dict(Counter(scalar(row.get("check_category")).strip() for row in matrix_rows)),
        "pester_scope_decision": scalar(pester.get("scope_decision")).strip(),
        "source_reports": [scalar(report).strip() for report in source_reports if scalar(report).strip()],
    }
    if not errors and len(seen_categories) == len(REQUIRED_CHECK_CATEGORIES):
        warnings.append("workflow readiness remains a later explicit gate; #267 only defines evidence ownership")
    return errors, warnings, metadata


def declared_output_artifacts(
    repo_root: Path,
    matrix_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    artifacts: list[dict[str, Any]] = []
    for row in matrix_rows:
        artifact = scalar(row.get("output_artifact")).strip()
        row_id = scalar(row.get("id")).strip()
        status = scalar(row.get("artifact_status")).strip()
        if status and status not in EXPLICIT_ARTIFACT_STATUSES:
            errors.append(f"engine matrix row {row_id} has unsupported artifact_status {status!r}")
        repo_path = is_repo_artifact_path(artifact)
        path_error: str | None = None
        exists: bool | None = None
        if repo_path:
            artifact_path, path_error = resolve_repo_artifact_path(artifact, repo_root)
            if path_error:
                errors.append(f"engine matrix row {row_id} {path_error}: {artifact}")
                exists = False
            else:
                exists = artifact_path.is_file() if artifact_path is not None else False
        evidence_claimed = bool(repo_path and exists and path_error is None)
        if status == "not_committed_in_267_boundary":
            evidence_claimed = False
            warnings.append(
                f"engine matrix row {row_id} artifact is not committed or claimed by this #267 boundary: {artifact}"
            )
        elif repo_path and row.get("blocking") is True and not exists and path_error is None:
            errors.append(f"blocking engine matrix artifact missing: {artifact} ({row_id})")
        artifacts.append(
            {
                "id": row_id,
                "check_category": scalar(row.get("check_category")).strip(),
                "path": artifact,
                "repo_path": repo_path,
                "exists": exists,
                "blocking": row.get("blocking"),
                "artifact_status": status or ("present" if exists else "external_or_future"),
                "evidence_claimed_by_boundary": evidence_claimed,
            }
        )
    return artifacts, errors, warnings


def validate_source_reports(
    repo_root: Path,
    source_reports: list[str],
    extra_reports: list[Path],
) -> tuple[list[dict[str, Any]], list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    report_facts: list[dict[str, Any]] = []
    loaded: dict[str, dict[str, Any]] = {}
    requested = [scalar(path).strip() for path in source_reports]
    extra_requested = [path.as_posix() for path in extra_reports]
    for report_value in requested + extra_requested:
        report_path, repo_path, path_error = resolve_repo_input_path(report_value, repo_root, "dependency report")
        if path_error:
            errors.append(f"PowerShell #267 dependency report {path_error}: {report_value}")
            continue
        if report_path is None:
            errors.append(f"PowerShell #267 dependency report path could not be resolved: {report_value}")
            continue
        if repo_path in loaded:
            continue
        try:
            report = read_json(report_path, "PowerShell #267 dependency report")
        except EngineBoundaryError as exc:
            errors.append(str(exc))
            continue
        if not isinstance(report, dict):
            errors.append(f"PowerShell #267 dependency report must be an object: {repo_path}")
            continue
        expected_schema = REPORT_SCHEMAS.get(repo_path)
        schema = scalar(report.get("schema_version")).strip()
        if expected_schema and schema != expected_schema:
            errors.append(f"{repo_path} schema mismatch: expected {expected_schema}, got {schema!r}")
        success, success_reason = report_success_state(report)
        if not success:
            errors.append(f"{repo_path} does not report successful validation: {success_reason}")
        loaded[repo_path] = report
        report_facts.append(
            {
                "path": repo_path,
                "schema_version": schema,
                "success": success,
                "finding_count": report_finding_count(report),
                "exists": True,
            }
        )
    proof = {
        "rule_risk_fixture_findings": summary_count(loaded.get(DEFAULT_RULE_RISK_REPORT.as_posix(), {}), "observed_finding_count"),
        "custom_check_findings": summary_count(loaded.get(DEFAULT_CUSTOM_REPORT.as_posix(), {}), "finding_count"),
        "governance_unclassified_findings": 0,
        "governance_classified_findings": 0,
        "assembly_parity_success": report_success(loaded.get(DEFAULT_ASSEMBLY_REPORT.as_posix(), {})),
    }
    governance_report = loaded.get(DEFAULT_GOVERNANCE_REPORT.as_posix(), {})
    governance_summary = governance_report.get("summary") if isinstance(governance_report, dict) else {}
    if isinstance(governance_summary, dict):
        proof["governance_unclassified_findings"] = governance_summary.get("unclassified_finding_count", 0)
        proof["governance_classified_findings"] = governance_summary.get("classified_finding_count", 0)
    if proof["rule_risk_fixture_findings"] < 1:
        errors.append("independent analyzer proof missing rule-risk fixture findings")
    if proof["custom_check_findings"] < 1:
        errors.append("independent analyzer proof missing custom check findings")
    if proof["governance_unclassified_findings"] != 0:
        errors.append("independent analyzer proof has unclassified governance findings")
    if proof["governance_classified_findings"] < 1:
        errors.append("independent analyzer proof missing classified governance findings")
    if not proof["assembly_parity_success"]:
        errors.append("assembly parity report must remain successful for engine-boundary readback")
    if not errors and DEFAULT_ASSEMBLY_REPORT.as_posix() in loaded:
        warnings.append("Windows PowerShell 5.1 runtime evidence remains separate from local static report generation")
    return report_facts, errors, warnings, proof


__all__ = [
    "declared_output_artifacts",
    "fail_if_missing_fields",
    "has_text",
    "validate_boundary_doc",
    "validate_source_reports",
]
