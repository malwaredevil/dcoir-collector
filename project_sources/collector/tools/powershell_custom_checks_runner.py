#!/usr/bin/env python3
"""Report assembly for custom PowerShell checks."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from powershell_custom_checks_common import (
    ISSUE_NUMBER,
    PARENT_ISSUE_NUMBER,
    SCHEMA_VERSION,
    CustomCheckError,
    read_json,
    repo_input_metadata,
    repo_relative_cli_path,
    safe_inventory_path,
)
from powershell_custom_checks_contract import (
    validate_check_definitions,
    validate_fixture_manifest,
    validate_inventory,
    validate_matrix,
)
from powershell_custom_checks_reporting import (
    select_targets,
    severity_at_or_above,
    validate_fixture_results,
    write_outputs,
)
from powershell_custom_checks_rules import run_checks_for_text

def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], list[str], list[str]]:
    repo_root = Path(args.repo_root).resolve()
    json_output = Path(args.json_output)
    markdown_output = Path(args.markdown_output)
    errors: list[str] = []
    warnings: list[str] = []
    checks_path = repo_relative_cli_path(repo_root, args.checks, "custom checks path", errors)
    matrix_path = repo_relative_cli_path(repo_root, args.matrix, "rule-to-risk matrix path", errors)
    inventory_path = repo_relative_cli_path(repo_root, args.inventory, "PowerShell surface inventory path", errors)
    fixture_manifest_path = repo_relative_cli_path(repo_root, args.fixture_manifest, "custom fixture manifest path", errors)
    checks_doc: dict[str, Any] = {}
    matrix: dict[str, Any] = {}
    inventory: dict[str, Any] = {}
    manifest: dict[str, Any] = {}
    check_map: dict[str, dict[str, Any]] = {}
    fixture_map: dict[str, dict[str, Any]] = {}
    surface_paths: set[str] = set()

    try:
        if checks_path is None or matrix_path is None or inventory_path is None or fixture_manifest_path is None:
            raise CustomCheckError("custom check input path validation failed")
        checks_doc = read_json(checks_path, "custom checks")
        matrix = read_json(matrix_path, "rule-to-risk matrix")
        inventory = read_json(inventory_path, "PowerShell surface inventory")
        manifest = read_json(fixture_manifest_path, "custom fixture manifest")
    except CustomCheckError as exc:
        errors.append(str(exc))

    if not errors:
        matrix_checks, matrix_errors = validate_matrix(matrix)
        errors.extend(matrix_errors)
        check_map, check_errors, check_warnings = validate_check_definitions(checks_doc, matrix_checks)
        errors.extend(check_errors)
        warnings.extend(check_warnings)
        surface_paths, inventory_errors, inventory_warnings = validate_inventory(inventory, repo_root)
        errors.extend(inventory_errors)
        warnings.extend(inventory_warnings)
        fixture_map, fixture_errors, fixture_warnings = validate_fixture_manifest(manifest, check_map, surface_paths, repo_root)
        errors.extend(fixture_errors)
        warnings.extend(fixture_warnings)

    targets = select_targets(args, inventory, fixture_map) if not errors else []
    if not errors and not targets:
        errors.append("no PowerShell targets selected for custom checks")

    findings: list[dict[str, Any]] = []
    if not errors:
        for target in targets:
            safe_target = safe_inventory_path(target, f"selected target {target}", repo_root, errors)
            if not safe_target:
                continue
            target_path = repo_root / safe_target
            if not target_path.is_file():
                errors.append(f"selected PowerShell source missing: {safe_target}")
                continue
            text = target_path.read_text(encoding="utf-8", errors="ignore")
            findings.extend(run_checks_for_text(text, safe_target, check_map))

    fixture_paths = {fixture["path"] for fixture in fixture_map.values()}
    scanned_fixture_paths = fixture_paths.intersection(targets)
    fixture_results: list[dict[str, Any]] = []
    fixture_errors: list[str] = []
    fixture_warnings: list[str] = []
    evaluated_fixture_map = fixture_map
    if fixture_map and scanned_fixture_paths:
        scanned_fixture_map = {
            fixture_id: fixture
            for fixture_id, fixture in fixture_map.items()
            if fixture["path"] in scanned_fixture_paths
        }
        evaluated_fixture_map = scanned_fixture_map
        fixture_results, fixture_errors, fixture_warnings = validate_fixture_results(scanned_fixture_map, findings)
        errors.extend(fixture_errors)
        warnings.extend(fixture_warnings)
    elif fixture_map:
        warnings.append("fixture expectations were not evaluated because no fixture targets were selected")
        fixture_results = [
            {
                "id": fixture_id,
                "kind": fixture.get("kind"),
                "check_id": fixture.get("check_id"),
                "path": fixture.get("path"),
                "expected_finding_count": len(fixture.get("expected_findings", [])),
                "observed_finding_count": 0,
                "observed_rules": [],
            }
            for fixture_id, fixture in sorted(fixture_map.items())
        ]

    unexpected_non_fixture_findings = [
        finding
        for finding in findings
        if finding["path"] not in fixture_paths and severity_at_or_above(finding["severity"], args.fail_on_severity)
    ]
    if unexpected_non_fixture_findings and not args.allow_findings:
        errors.append(
            f"unsuppressed custom findings at or above {args.fail_on_severity}: {len(unexpected_non_fixture_findings)}"
        )

    evaluated_fixture_paths = {fixture["path"] for fixture in evaluated_fixture_map.values()}
    negative_count = len([fixture for fixture in evaluated_fixture_map.values() if fixture.get("kind") == "negative"])
    control_count = len([fixture for fixture in evaluated_fixture_map.values() if fixture.get("kind") == "control"])
    expected_count = sum(len(fixture.get("expected_findings", [])) for fixture in evaluated_fixture_map.values())
    observed_fixture_count = len([finding for finding in findings if finding["path"] in evaluated_fixture_paths])
    report = {
        "schema_version": SCHEMA_VERSION,
        "issue": ISSUE_NUMBER,
        "parent_issue": PARENT_ISSUE_NUMBER,
        "depends_on": [261, 262, 263],
        "source_of_truth": "#264 custom DCOIR check contract mapped to #263 rule-to-risk matrix",
        "target_scope": args.target_scope,
        "checks": repo_input_metadata(checks_path, args.checks, repo_root, checks_doc),
        "matrix": repo_input_metadata(matrix_path, args.matrix, repo_root, matrix),
        "inventory": {
            **repo_input_metadata(inventory_path, args.inventory, repo_root, inventory),
            "inventory_total_surfaces": inventory.get("summary", {}).get("total_surfaces") if isinstance(inventory, dict) else None,
        },
        "fixture_manifest": repo_input_metadata(fixture_manifest_path, args.fixture_manifest, repo_root, manifest),
        "summary": {
            "custom_check_count": len(check_map),
            "target_count": len(targets),
            "finding_count": len(findings),
            "negative_fixture_count": negative_count,
            "control_fixture_count": control_count,
            "expected_fixture_finding_count": expected_count,
            "observed_fixture_finding_count": observed_fixture_count,
        },
        "targets": targets,
        "fixtures": fixture_results,
        "findings": findings,
        "validation": {
            "success": not errors,
            "errors": errors,
            "warnings": warnings,
        },
        "outputs": {
            "json": json_output.as_posix(),
            "markdown": markdown_output.as_posix(),
        },
    }
    if not args.no_write:
        output_errors = write_outputs(repo_root, report, json_output, markdown_output)
        if output_errors:
            errors.extend(output_errors)
            report["validation"]["success"] = False
            report["validation"]["errors"] = errors
            write_outputs(repo_root, report, json_output, markdown_output)
    return report, errors, warnings
