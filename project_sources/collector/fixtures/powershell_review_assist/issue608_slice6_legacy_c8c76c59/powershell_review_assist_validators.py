#!/usr/bin/env python3
"""Source report validators for PowerShell review-assist reports."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from powershell_review_assist_common import (
    ReviewAssistError,
    SOURCE_CONTRACTS,
    require_field,
    require_list,
    require_object,
    repo_path_if_safe,
    scalar,
)
from powershell_review_assist_reachability_validator import validate_function_reachability_report

def validate_inventory(repo_root: Path, report: dict[str, Any], repo_path: str, errors: list[str]) -> None:
    summary = require_object(require_field(report, "summary", repo_path, errors), f"{repo_path} summary", errors)
    surfaces = require_list(require_field(report, "surfaces", repo_path, errors), f"{repo_path} surfaces", errors)
    require_field(report, "mode", repo_path, errors)
    require_field(report, "outputs", repo_path, errors)
    if "total_surfaces" not in summary or not isinstance(summary.get("total_surfaces"), int):
        errors.append(f"{repo_path} summary.total_surfaces must be an integer")
    for index, surface in enumerate(surfaces, start=1):
        if not isinstance(surface, dict):
            errors.append(f"{repo_path} surfaces[{index}] must be an object")
            continue
        path = scalar(surface.get("path")).strip()
        if not path:
            errors.append(f"{repo_path} surfaces[{index}] missing path")
            continue
        try:
            repo_path_if_safe(path, repo_root, f"{repo_path} surfaces[{index}]")
        except ReviewAssistError as exc:
            errors.append(str(exc))
        for field in ("category", "source_type", "status", "inclusion_decision", "decision_reason"):
            if field not in surface:
                errors.append(f"{repo_path} surfaces[{index}] missing {field}")

def validate_rule_risk_report(repo_root: Path, report: dict[str, Any], repo_path: str, errors: list[str]) -> None:
    require_object(require_field(report, "summary", repo_path, errors), f"{repo_path} summary", errors)
    fixtures = require_list(require_field(report, "fixtures", repo_path, errors), f"{repo_path} fixtures", errors)
    findings = require_list(require_field(report, "findings", repo_path, errors), f"{repo_path} findings", errors)
    require_field(report, "environment_gap", repo_path, errors)
    require_field(report, "outputs", repo_path, errors)
    for index, fixture in enumerate(fixtures, start=1):
        if not isinstance(fixture, dict):
            errors.append(f"{repo_path} fixtures[{index}] must be an object")
            continue
        for field in ("id", "kind", "path", "expected_finding_count", "observed_finding_count"):
            if field not in fixture:
                errors.append(f"{repo_path} fixtures[{index}] missing {field}")
        if fixture.get("path"):
            try:
                repo_path_if_safe(scalar(fixture["path"]), repo_root, f"{repo_path} fixtures[{index}]")
            except ReviewAssistError as exc:
                errors.append(str(exc))
    for index, finding in enumerate(findings, start=1):
        if not isinstance(finding, dict):
            errors.append(f"{repo_path} findings[{index}] must be an object")
            continue
        for field in ("path", "line", "column", "rule_name", "severity", "observed_problem", "recommended_fix"):
            if field not in finding:
                errors.append(f"{repo_path} findings[{index}] missing {field}")
        for field in ("path", "target_path"):
            if finding.get(field):
                try:
                    repo_path_if_safe(scalar(finding[field]), repo_root, f"{repo_path} findings[{index}].{field}")
                except ReviewAssistError as exc:
                    errors.append(str(exc))

def validate_rule_risk_matrix(repo_root: Path, matrix: dict[str, Any], repo_path: str, errors: list[str]) -> None:
    checks = require_list(require_field(matrix, "checks", repo_path, errors), f"{repo_path} checks", errors)
    for index, check in enumerate(checks, start=1):
        if not isinstance(check, dict):
            errors.append(f"{repo_path} checks[{index}] must be an object")
            continue
        for field in (
            "id",
            "rule_name",
            "risk_classes",
            "target_surfaces",
            "failure_impact",
            "recommended_fix",
        ):
            if field not in check:
                errors.append(f"{repo_path} checks[{index}] missing {field}")
        if not isinstance(check.get("risk_classes"), list):
            errors.append(f"{repo_path} checks[{index}] risk_classes must be a list")
        if not isinstance(check.get("target_surfaces"), list):
            errors.append(f"{repo_path} checks[{index}] target_surfaces must be a list")
        check_source = scalar(check.get("check_source")).strip()
        if check_source:
            try:
                repo_path_if_safe(check_source, repo_root, f"{repo_path} checks[{index}].check_source")
            except ReviewAssistError as exc:
                errors.append(str(exc))

def validate_custom_report(repo_root: Path, report: dict[str, Any], repo_path: str, errors: list[str]) -> None:
    require_object(require_field(report, "summary", repo_path, errors), f"{repo_path} summary", errors)
    findings = require_list(require_field(report, "findings", repo_path, errors), f"{repo_path} findings", errors)
    fixtures = require_list(require_field(report, "fixtures", repo_path, errors), f"{repo_path} fixtures", errors)
    targets = require_list(require_field(report, "targets", repo_path, errors), f"{repo_path} targets", errors)
    require_field(report, "checks", repo_path, errors)
    require_field(report, "outputs", repo_path, errors)
    for index, target in enumerate(targets, start=1):
        try:
            repo_path_if_safe(scalar(target), repo_root, f"{repo_path} targets[{index}]")
        except ReviewAssistError as exc:
            errors.append(str(exc))
    for index, fixture in enumerate(fixtures, start=1):
        if not isinstance(fixture, dict):
            errors.append(f"{repo_path} fixtures[{index}] must be an object")
            continue
        for field in ("id", "kind", "check_id", "path", "expected_finding_count", "observed_finding_count"):
            if field not in fixture:
                errors.append(f"{repo_path} fixtures[{index}] missing {field}")
        if fixture.get("path"):
            try:
                repo_path_if_safe(scalar(fixture["path"]), repo_root, f"{repo_path} fixtures[{index}]")
            except ReviewAssistError as exc:
                errors.append(str(exc))
    for index, finding in enumerate(findings, start=1):
        if not isinstance(finding, dict):
            errors.append(f"{repo_path} findings[{index}] must be an object")
            continue
        for field in (
            "path",
            "line",
            "column",
            "check_id",
            "rule_name",
            "severity",
            "risk_classes",
            "observed_problem",
            "impact",
            "recommended_fix",
            "target_surfaces",
        ):
            if field not in finding:
                errors.append(f"{repo_path} findings[{index}] missing {field}")
        if finding.get("path"):
            try:
                repo_path_if_safe(scalar(finding["path"]), repo_root, f"{repo_path} findings[{index}].path")
            except ReviewAssistError as exc:
                errors.append(str(exc))

def validate_assembly_parity(repo_root: Path, report: dict[str, Any], repo_path: str, errors: list[str]) -> None:
    require_object(require_field(report, "summary", repo_path, errors), f"{repo_path} summary", errors)
    outputs = require_list(
        require_field(report, "generated_outputs", repo_path, errors),
        f"{repo_path} generated_outputs",
        errors,
    )
    require_field(report, "coverage_statement", repo_path, errors)
    require_field(report, "controlled_bad_cases", repo_path, errors)
    if "baseline_comparison" not in report:
        errors.append(f"{repo_path} missing baseline_comparison")
    require_field(report, "outputs", repo_path, errors)
    for index, output in enumerate(outputs, start=1):
        if not isinstance(output, dict):
            errors.append(f"{repo_path} generated_outputs[{index}] must be an object")
            continue
        for field in ("id", "path", "line_mapping_status", "parse", "parity"):
            if field not in output:
                errors.append(f"{repo_path} generated_outputs[{index}] missing {field}")
        if output.get("path"):
            try:
                repo_path_if_safe(scalar(output["path"]), repo_root, f"{repo_path} generated_outputs[{index}].path")
            except ReviewAssistError as exc:
                errors.append(str(exc))
        line_mapping = output.get("line_mapping", [])
        if isinstance(line_mapping, list):
            for map_index, mapping in enumerate(line_mapping, start=1):
                if isinstance(mapping, dict) and mapping.get("source_path"):
                    try:
                        repo_path_if_safe(
                            scalar(mapping["source_path"]),
                            repo_root,
                            f"{repo_path} generated_outputs[{index}].line_mapping[{map_index}]",
                        )
                    except ReviewAssistError as exc:
                        errors.append(str(exc))

def validate_governance_report(repo_root: Path, report: dict[str, Any], repo_path: str, errors: list[str]) -> None:
    require_object(require_field(report, "summary", repo_path, errors), f"{repo_path} summary", errors)
    require_list(require_field(report, "input_reports", repo_path, errors), f"{repo_path} input_reports", errors)
    classifications = require_list(
        require_field(report, "classifications", repo_path, errors),
        f"{repo_path} classifications",
        errors,
    )
    require_field(report, "baseline_delta", repo_path, errors)
    require_field(report, "controlled_fail_closed_proof", repo_path, errors)
    require_field(report, "assembly_parity_report", repo_path, errors)
    require_field(report, "governance", repo_path, errors)
    for index, item in enumerate(classifications, start=1):
        if not isinstance(item, dict):
            errors.append(f"{repo_path} classifications[{index}] must be an object")
            continue
        for field in ("source_report", "source_schema_version", "path", "rule_name", "severity", "governance"):
            if field not in item:
                errors.append(f"{repo_path} classifications[{index}] missing {field}")
        if item.get("path"):
            try:
                repo_path_if_safe(scalar(item["path"]), repo_root, f"{repo_path} classifications[{index}].path")
            except ReviewAssistError as exc:
                errors.append(str(exc))

def validate_engine_boundary(repo_root: Path, report: dict[str, Any], repo_path: str, errors: list[str]) -> None:
    require_object(require_field(report, "summary", repo_path, errors), f"{repo_path} summary", errors)
    require_list(require_field(report, "dependency_reports", repo_path, errors), f"{repo_path} dependency_reports", errors)
    declared = require_list(
        require_field(report, "declared_output_artifacts", repo_path, errors),
        f"{repo_path} declared_output_artifacts",
        errors,
    )
    require_list(require_field(report, "engine_matrix", repo_path, errors), f"{repo_path} engine_matrix", errors)
    require_field(report, "pester_boundary", repo_path, errors)
    require_field(report, "independent_analyzer_enforcement_proof", repo_path, errors)
    for index, artifact in enumerate(declared, start=1):
        if not isinstance(artifact, dict):
            errors.append(f"{repo_path} declared_output_artifacts[{index}] must be an object")
            continue
        for field in ("id", "path", "artifact_status", "blocking", "evidence_claimed_by_boundary"):
            if field not in artifact:
                errors.append(f"{repo_path} declared_output_artifacts[{index}] missing {field}")
        artifact_path = scalar(artifact.get("path")).strip()
        if artifact.get("repo_path") is True and artifact_path:
            try:
                repo_path_if_safe(artifact_path, repo_root, f"{repo_path} declared_output_artifacts[{index}].path")
            except ReviewAssistError as exc:
                errors.append(str(exc))

def validate_analyzer_report(repo_root: Path, report: dict[str, Any], repo_path: str, errors: list[str]) -> None:
    require_object(require_field(report, "summary", repo_path, errors), f"{repo_path} summary", errors)
    findings = require_list(require_field(report, "findings", repo_path, errors), f"{repo_path} findings", errors)
    require_field(report, "targets", repo_path, errors)
    require_field(report, "skipped_surfaces", repo_path, errors)
    require_field(report, "analyzer", repo_path, errors)
    require_field(report, "powershell", repo_path, errors)
    require_field(report, "settings", repo_path, errors)
    require_field(report, "inventory", repo_path, errors)
    require_field(report, "baseline", repo_path, errors)
    require_field(report, "outputs", repo_path, errors)
    for index, finding in enumerate(findings, start=1):
        if not isinstance(finding, dict):
            errors.append(f"{repo_path} findings[{index}] must be an object")
            continue
        if finding.get("path"):
            try:
                repo_path_if_safe(scalar(finding["path"]), repo_root, f"{repo_path} findings[{index}].path")
            except ReviewAssistError as exc:
                errors.append(str(exc))

def validate_loaded_sources(repo_root: Path, docs: dict[str, dict[str, Any]], source_reports: list[dict[str, Any]], errors: list[str]) -> None:
    repo_paths = {entry["source_key"]: entry["path"] for entry in source_reports}
    validators = {
        "surface_inventory": validate_inventory,
        "rule_risk_report": validate_rule_risk_report,
        "rule_risk_matrix": validate_rule_risk_matrix,
        "custom_report": validate_custom_report,
        "assembly_parity_report": validate_assembly_parity,
        "governance_report": validate_governance_report,
        "engine_boundary_report": validate_engine_boundary,
        "analyzer_report": validate_analyzer_report,
        "function_reachability_report": validate_function_reachability_report,
    }
    for key, validator in validators.items():
        doc = docs.get(key)
        if doc is None:
            continue
        validator(repo_root, doc, repo_paths.get(key, SOURCE_CONTRACTS[key].path.as_posix()), errors)
