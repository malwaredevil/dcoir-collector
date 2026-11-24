#!/usr/bin/env python3
"""Function-reachability source validator for PowerShell review-assist reports."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from powershell_review_assist_common import (
    ReviewAssistError,
    require_field,
    require_list,
    require_object,
    repo_path_if_safe,
    scalar,
)

def validate_function_reachability_report(repo_root: Path, report: dict[str, Any], repo_path: str, errors: list[str]) -> None:
    summary = require_object(require_field(report, "summary", repo_path, errors), f"{repo_path} summary", errors)
    analysis_scope = require_object(
        require_field(report, "analysis_scope", repo_path, errors),
        f"{repo_path} analysis_scope",
        errors,
    )
    functions = require_list(require_field(report, "functions", repo_path, errors), f"{repo_path} functions", errors)
    dynamic_sites = require_list(
        require_field(report, "dynamic_invocation_sites", repo_path, errors),
        f"{repo_path} dynamic_invocation_sites",
        errors,
    )
    runtime_coverage = require_object(
        require_field(report, "runtime_lane_coverage", repo_path, errors),
        f"{repo_path} runtime_lane_coverage",
        errors,
    )
    non_claims = require_list(require_field(report, "non_claims", repo_path, errors), f"{repo_path} non_claims", errors)
    outputs = require_object(require_field(report, "outputs", repo_path, errors), f"{repo_path} outputs", errors)
    source_files = require_list(
        require_field(analysis_scope, "source_files", f"{repo_path} analysis_scope", errors),
        f"{repo_path} analysis_scope.source_files",
        errors,
    )
    classification_counts = require_object(
        require_field(summary, "classification_counts", f"{repo_path} summary", errors),
        f"{repo_path} summary.classification_counts",
        errors,
    )
    allowed_classifications = {
        "entrypoint",
        "literal_referenced",
        "dynamic_invocation_uncertain",
        "static_unreferenced",
    }
    if summary.get("function_count") != len(functions):
        errors.append(f"{repo_path} summary.function_count must match functions length")
    if sum(value for value in classification_counts.values() if isinstance(value, int)) != len(functions):
        errors.append(f"{repo_path} summary.classification_counts must sum to functions length")
    if summary.get("coverage_state") != "not_collected":
        errors.append(f"{repo_path} summary.coverage_state must remain not_collected")
    if runtime_coverage.get("state") != "not_collected":
        errors.append(f"{repo_path} runtime_lane_coverage.state must remain not_collected")
    non_claim_text = "\n".join(scalar(item) for item in non_claims)
    if "safe to delete" not in non_claim_text:
        errors.append(f"{repo_path} non_claims must explicitly reject function deletion readiness")
    for field in ("json", "markdown"):
        output_path = scalar(outputs.get(field)).strip()
        if output_path:
            try:
                repo_path_if_safe(output_path, repo_root, f"{repo_path} outputs.{field}")
            except ReviewAssistError as exc:
                errors.append(str(exc))
    for index, source in enumerate(source_files, start=1):
        if isinstance(source, dict) and source.get("path"):
            try:
                repo_path_if_safe(scalar(source["path"]), repo_root, f"{repo_path} analysis_scope.source_files[{index}].path")
            except ReviewAssistError as exc:
                errors.append(str(exc))
    for index, item in enumerate(functions, start=1):
        if not isinstance(item, dict):
            errors.append(f"{repo_path} functions[{index}] must be an object")
            continue
        for field in (
            "name",
            "classification",
            "source_path",
            "line",
            "static_reference_status",
            "dynamic_uncertainty_status",
            "reference_count",
            "coverage_status",
            "claim",
        ):
            if field not in item:
                errors.append(f"{repo_path} functions[{index}] missing {field}")
        classification = scalar(item.get("classification"))
        if classification not in allowed_classifications:
            errors.append(f"{repo_path} functions[{index}] unknown classification: {classification}")
        if item.get("coverage_status") != "not_observed_in_suite":
            errors.append(f"{repo_path} functions[{index}] coverage_status must remain not_observed_in_suite")
        if item.get("source_path"):
            try:
                repo_path_if_safe(scalar(item["source_path"]), repo_root, f"{repo_path} functions[{index}].source_path")
            except ReviewAssistError as exc:
                errors.append(str(exc))
        references = item.get("references", [])
        if isinstance(references, list):
            for reference_index, reference in enumerate(references, start=1):
                if isinstance(reference, dict) and reference.get("source_path"):
                    try:
                        repo_path_if_safe(
                            scalar(reference["source_path"]),
                            repo_root,
                            f"{repo_path} functions[{index}].references[{reference_index}].source_path",
                        )
                    except ReviewAssistError as exc:
                        errors.append(str(exc))
    for index, site in enumerate(dynamic_sites, start=1):
        if isinstance(site, dict) and site.get("source_path"):
            try:
                repo_path_if_safe(scalar(site["source_path"]), repo_root, f"{repo_path} dynamic_invocation_sites[{index}].source_path")
            except ReviewAssistError as exc:
                errors.append(str(exc))
