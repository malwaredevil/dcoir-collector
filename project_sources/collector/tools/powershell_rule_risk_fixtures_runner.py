#!/usr/bin/env python3
"""Analyzer-wrapper execution and report assembly for rule-risk fixtures."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import powershell_rule_risk_fixtures_common as fixture_common
from powershell_rule_risk_fixtures_contract import validate_manifest, validate_matrix

def inventory_surface(repo_root: Path, fixture: dict[str, Any]) -> dict[str, Any]:
    path = fixture["path"]
    absolute = repo_root / path
    text = absolute.read_text(encoding="utf-8", errors="ignore")
    return {
        "path": path,
        "category": "collector_harness_script",
        "source_type": ".ps1",
        "status": "fixture",
        "inclusion_decision": "include",
        "decision_reason": "#263 fixture harness temporary analyzer target.",
        "exists": True,
        "marker_lines": [],
        "embedded_snippets": [],
        "size_bytes": len(absolute.read_bytes()),
        "line_count": text.count("\n") + (1 if text and not text.endswith("\n") else 0),
        "sha256": fixture_common.analyzer.sha256_text(text),
    }

def write_temp_inventory(repo_root: Path, fixtures: list[dict[str, Any]], temp_root: Path) -> Path:
    inventory = {
        "schema_version": fixture_common.analyzer.INVENTORY_SCHEMA_VERSION,
        "issue": fixture_common.ISSUE_NUMBER,
        "summary": {"total_surfaces": len(fixtures)},
        "validation": {"success": True, "errors": [], "warnings": []},
        "surfaces": [inventory_surface(repo_root, fixture) for fixture in fixtures],
    }
    inventory_path = temp_root / "powershell_rule_risk_fixture_inventory.json"
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    return inventory_path

def wrapper_args(repo_root: Path, inventory_path: Path, fixture_paths: list[str], timeout_seconds: int) -> argparse.Namespace:
    return argparse.Namespace(
        repo_root=str(repo_root),
        inventory=fixture_common.safe_relpath(inventory_path, repo_root),
        settings=fixture_common.analyzer.DEFAULT_SETTINGS.as_posix(),
        json_output=(Path("project_sources/collector") / "_fixture_wrapper_report.json").as_posix(),
        markdown_output=(Path("project_sources/collector") / "_fixture_wrapper_report.md").as_posix(),
        analyzer_command=[sys.executable, fixture_common.FACADE_PATH.as_posix(), "--fixture-analyzer"],
        target_path=fixture_paths,
        baseline_json=None,
        timeout_seconds=timeout_seconds,
        minimum_powershell_version="5.1",
        fail_on_severity="Warning",
        allow_findings=True,
        expect_finding_rule=None,
        expect_finding_path=None,
        expect_no_findings=False,
        no_write=True,
    )

def expected_match(expected: dict[str, Any], finding_row: dict[str, Any], path: str) -> bool:
    return (
        finding_row.get("path") == path
        and finding_row.get("rule_name") == expected.get("rule_name")
        and finding_row.get("severity") == expected.get("severity")
        and finding_row.get("line") == expected.get("line")
    )

def validate_fixture_results(
    check_map: dict[str, dict[str, Any]],
    fixture_map: dict[str, dict[str, Any]],
    findings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    by_path: dict[str, list[dict[str, Any]]] = {}
    for finding_row in findings:
        by_path.setdefault(str(finding_row.get("path")), []).append(finding_row)

    expected_by_check: dict[str, int] = {}
    observed_by_check: dict[str, int] = {}
    fixture_results: list[dict[str, Any]] = []
    for fixture_id, fixture in sorted(fixture_map.items()):
        fixture_findings_for_path = by_path.get(fixture["path"], [])
        expected_findings = fixture.get("expected_findings", [])
        fixture_errors: list[str] = []
        if fixture.get("kind") == "control" and fixture_findings_for_path:
            fixture_errors.append(
                f"{fixture_id}: control fixture produced unexpected findings: "
                + ", ".join(finding["rule_name"] for finding in fixture_findings_for_path)
            )
        for expected in expected_findings:
            check_id = expected.get("check_id")
            expected_by_check[check_id] = expected_by_check.get(check_id, 0) + 1
            matches = [
                finding_row
                for finding_row in fixture_findings_for_path
                if expected_match(expected, finding_row, fixture["path"])
            ]
            if not matches:
                fixture_errors.append(
                    f"{fixture_id}: expected {expected.get('rule_name')} at "
                    f"{fixture['path']}:{expected.get('line')} was not produced"
                )
            else:
                observed_by_check[check_id] = observed_by_check.get(check_id, 0) + len(matches)
        unexpected = [
            finding_row
            for finding_row in fixture_findings_for_path
            if not any(expected_match(expected, finding_row, fixture["path"]) for expected in expected_findings)
        ]
        if unexpected and fixture.get("kind") == "negative":
            warnings.append(
                f"{fixture_id}: produced additional unmapped findings: "
                + ", ".join(finding["rule_name"] for finding in unexpected)
            )
        errors.extend(fixture_errors)
        fixture_results.append(
            {
                "id": fixture_id,
                "kind": fixture.get("kind"),
                "path": fixture["path"],
                "sha256": fixture.get("sha256"),
                "expected_finding_count": len(expected_findings),
                "observed_finding_count": len(fixture_findings_for_path),
                "observed_rules": sorted({finding["rule_name"] for finding in fixture_findings_for_path}),
                "validation": {
                    "success": not fixture_errors,
                    "errors": fixture_errors,
                },
            }
        )

    negative_fixture_ids = {
        fixture_id for fixture_id, fixture in fixture_map.items() if fixture.get("kind") == "negative"
    }
    for check_id, check in sorted(check_map.items()):
        if check.get("blocking") is not True:
            continue
        fixtures = [fixture_id for fixture_id in check.get("fixtures", []) if fixture_id in fixture_map]
        negative_fixtures = [fixture_id for fixture_id in fixtures if fixture_id in negative_fixture_ids]
        if not negative_fixtures:
            errors.append(f"{check_id}: blocking check has no negative fixture")
        if expected_by_check.get(check_id, 0) == 0:
            errors.append(f"{check_id}: blocking check has no manifest expected finding")
        if observed_by_check.get(check_id, 0) == 0:
            errors.append(f"{check_id}: blocking check has no observed fixture finding")
    return fixture_results, errors, warnings

def build_fixture_report(args: argparse.Namespace) -> tuple[dict[str, Any], list[str], list[str], dict[str, Any]]:
    repo_root = Path(args.repo_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    matrix_path = fixture_common.repo_relative_path_or_error(repo_root, args.matrix, "rule-to-risk matrix path", errors)
    manifest_path = fixture_common.repo_relative_path_or_error(repo_root, args.manifest, "fixture manifest path", errors)
    matrix: dict[str, Any] = {}
    manifest: dict[str, Any] = {}
    fixture_results: list[dict[str, Any]] = []
    wrapper_report: dict[str, Any] | None = None

    if matrix_path is not None:
        try:
            matrix = fixture_common.read_json(matrix_path, "rule-to-risk matrix")
            if not isinstance(matrix, dict):
                raise fixture_common.RuleRiskFixtureError("rule-to-risk matrix must be a JSON object")
        except fixture_common.RuleRiskFixtureError as exc:
            errors.append(str(exc))
    if manifest_path is not None:
        try:
            manifest = fixture_common.read_json(manifest_path, "fixture manifest")
            if not isinstance(manifest, dict):
                raise fixture_common.RuleRiskFixtureError("fixture manifest must be a JSON object")
        except fixture_common.RuleRiskFixtureError as exc:
            errors.append(str(exc))

    check_map: dict[str, dict[str, Any]] = {}
    fixture_map: dict[str, dict[str, Any]] = {}
    if not errors:
        check_map, matrix_errors, matrix_warnings = validate_matrix(matrix, not args.skip_minimum_risk_class_check)
        fixture_map, manifest_errors, manifest_warnings = validate_manifest(manifest, repo_root, check_map)
        errors.extend(matrix_errors)
        errors.extend(manifest_errors)
        warnings.extend(matrix_warnings)
        warnings.extend(manifest_warnings)

    findings: list[dict[str, Any]] = []
    if not errors:
        fixtures = [fixture_map[fixture_id] for fixture_id in sorted(fixture_map)]
        with tempfile.TemporaryDirectory(prefix=".dcoir-rule-risk-fixtures-", dir=repo_root) as temp:
            inventory_path = write_temp_inventory(repo_root, fixtures, Path(temp))
            args_for_wrapper = wrapper_args(
                repo_root=repo_root,
                inventory_path=inventory_path,
                fixture_paths=[fixture["path"] for fixture in fixtures],
                timeout_seconds=args.timeout_seconds,
            )
            wrapper_report, wrapper_errors, wrapper_warnings = fixture_common.analyzer.build_report(args_for_wrapper)
            warnings.extend(wrapper_warnings)
            if wrapper_errors:
                errors.extend(f"fixture wrapper: {error}" for error in wrapper_errors)
            if wrapper_report is None:
                errors.append("fixture wrapper did not return a report")
            else:
                findings = wrapper_report.get("findings", [])
    if not errors and wrapper_report is not None:
        fixture_results, result_errors, result_warnings = validate_fixture_results(check_map, fixture_map, findings)
        errors.extend(result_errors)
        warnings.extend(result_warnings)
    elif fixture_map:
        fixture_results = [
            {
                "id": fixture_id,
                "kind": fixture.get("kind"),
                "path": fixture.get("path"),
                "sha256": fixture.get("sha256"),
                "expected_finding_count": len(fixture.get("expected_findings", [])),
                "observed_finding_count": 0,
                "observed_rules": [],
                "validation": {"success": False, "errors": ["fixture analysis did not complete"]},
            }
            for fixture_id, fixture in sorted(fixture_map.items())
        ]

    blocking_count = len([check for check in check_map.values() if check.get("blocking") is True])
    advisory_count = len([check for check in check_map.values() if check.get("blocking") is False])
    negative_count = len([fixture for fixture in fixture_map.values() if fixture.get("kind") == "negative"])
    control_count = len([fixture for fixture in fixture_map.values() if fixture.get("kind") == "control"])
    expected_count = sum(len(fixture.get("expected_findings", [])) for fixture in fixture_map.values())

    report = {
        "schema_version": fixture_common.SCHEMA_VERSION,
        "issue": fixture_common.ISSUE_NUMBER,
        "source_of_truth": "#263 rule-to-risk matrix and fixture manifest",
        "scope": "Matrix and fixture harness only. No workflow YAML, SARIF, required-check, PR, or external-agent invocation.",
        "matrix": {
            "path": fixture_common.safe_relpath(matrix_path, repo_root) if matrix_path is not None else Path(args.matrix).as_posix(),
            "schema_version": matrix.get("schema_version"),
            "sha256": fixture_common.sha256_file(matrix_path) if matrix_path is not None and matrix_path.exists() and matrix_path.is_file() else None,
        },
        "manifest": {
            "path": fixture_common.safe_relpath(manifest_path, repo_root) if manifest_path is not None else Path(args.manifest).as_posix(),
            "schema_version": manifest.get("schema_version"),
            "sha256": fixture_common.sha256_file(manifest_path)
            if manifest_path is not None and manifest_path.exists() and manifest_path.is_file()
            else None,
        },
        "analyzer_wrapper": {
            "path": "project_sources/collector/tools/run_powershell_analyzer.py",
            "schema_version": fixture_common.analyzer.SCHEMA_VERSION,
            "wrapped_report_schema_version": wrapper_report.get("schema_version") if wrapper_report else None,
        },
        "fixture_analyzer": {
            "name": "DCOIRFixtureAnalyzer",
            "version": "1.0.0",
            "command_kind": "custom_json_command",
        },
        "summary": {
            "matrix_check_count": len(check_map),
            "blocking_check_count": blocking_count,
            "advisory_check_count": advisory_count,
            "negative_fixture_count": negative_count,
            "control_fixture_count": control_count,
            "expected_finding_count": expected_count,
            "observed_finding_count": len(findings),
        },
        "fixtures": fixture_results,
        "findings": findings,
        "validation": {
            "success": not errors,
            "errors": errors,
            "warnings": warnings,
        },
        "outputs": {
            "json": Path(args.json_output).as_posix(),
            "markdown": Path(args.markdown_output).as_posix(),
            "matrix_markdown": Path(args.matrix_markdown_output).as_posix(),
        },
        "environment_gap": (
            "This #263 harness uses a deterministic local fixture analyzer through the #262 wrapper. "
            "It intentionally does not execute PSScriptAnalyzer, so this fixture report does not claim whether "
            "pwsh or the PSScriptAnalyzer module is installed in the current environment."
        ),
    }
    return report, errors, warnings, matrix
