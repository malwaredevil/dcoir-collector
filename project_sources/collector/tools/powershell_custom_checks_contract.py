#!/usr/bin/env python3
"""Contract validation for custom PowerShell checks."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from powershell_custom_checks_common import (
    ANALYZABLE_SOURCE_TYPES,
    CHECKS_SCHEMA_VERSION,
    FIXTURE_MANIFEST_SCHEMA_VERSION,
    INVENTORY_SCHEMA_VERSION,
    MATRIX_SCHEMA_VERSION,
    REQUIRED_CHECK_FIELDS,
    normalize_repo_path,
    require_string,
    require_string_list,
    safe_fixture_path,
    safe_inventory_path,
    scalar,
)

def validate_matrix(matrix: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    if matrix.get("schema_version") != MATRIX_SCHEMA_VERSION:
        errors.append(
            f"rule-to-risk matrix schema mismatch: expected {MATRIX_SCHEMA_VERSION}, got {matrix.get('schema_version')!r}"
        )
    checks = matrix.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("rule-to-risk matrix must contain checks[]")
        return {}, errors
    check_map: dict[str, dict[str, Any]] = {}
    for index, raw_check in enumerate(checks, start=1):
        if not isinstance(raw_check, dict):
            errors.append(f"matrix check #{index}: entry is not an object")
            continue
        check_id = scalar(raw_check.get("id")).strip()
        if not check_id:
            errors.append(f"matrix check #{index}: id must be a non-empty string")
            continue
        if check_id in check_map:
            errors.append(f"matrix check #{index}: duplicate check id {check_id}")
        check_map[check_id] = raw_check
    return check_map, errors


def validate_check_definitions(
    checks_doc: dict[str, Any],
    matrix_checks: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if checks_doc.get("schema_version") != CHECKS_SCHEMA_VERSION:
        errors.append(
            f"custom check schema mismatch: expected {CHECKS_SCHEMA_VERSION}, got {checks_doc.get('schema_version')!r}"
        )
    raw_checks = checks_doc.get("checks")
    if not isinstance(raw_checks, list) or not raw_checks:
        errors.append("custom checks document must contain checks[]")
        return {}, errors, warnings

    check_map: dict[str, dict[str, Any]] = {}
    for index, raw_check in enumerate(raw_checks, start=1):
        label = f"custom check #{index}"
        if not isinstance(raw_check, dict):
            errors.append(f"{label}: entry is not an object")
            continue
        for field in REQUIRED_CHECK_FIELDS:
            if field in {"risk_classes", "target_surfaces", "false_positive_controls"}:
                require_string_list(raw_check, field, label, errors)
            else:
                require_string(raw_check, field, label, errors)
        check_id = scalar(raw_check.get("id")).strip()
        if not check_id:
            continue
        if check_id in check_map:
            errors.append(f"{label}: duplicate check id {check_id}")
        if raw_check.get("expected_severity") not in {"Information", "Warning", "Error"}:
            errors.append(f"{label}: expected_severity must be Information, Warning, or Error")
        matrix_check_id = scalar(raw_check.get("matrix_check_id")).strip()
        matrix_check = matrix_checks.get(matrix_check_id)
        if not matrix_check:
            errors.append(f"{label}: matrix_check_id {matrix_check_id!r} is not present in #263 matrix")
        else:
            if raw_check.get("rule_name") != matrix_check.get("rule_name"):
                errors.append(f"{label}: rule_name does not match #263 matrix check {matrix_check_id}")
            if raw_check.get("expected_severity") != matrix_check.get("expected_severity"):
                errors.append(f"{label}: expected_severity does not match #263 matrix check {matrix_check_id}")
            matrix_risks = set(matrix_check.get("risk_classes", []))
            custom_risks = set(raw_check.get("risk_classes", []))
            if not custom_risks:
                errors.append(f"{label}: risk_classes cannot be empty")
            elif not custom_risks.issubset(matrix_risks):
                errors.append(f"{label}: risk_classes are not all mapped by #263 matrix check {matrix_check_id}")
            if matrix_check.get("blocking") is not True:
                warnings.append(f"{label}: mapped #263 matrix check is not blocking")
        check_map[check_id] = raw_check
    return check_map, errors, warnings


def validate_inventory(inventory: dict[str, Any], repo_root: Path) -> tuple[set[str], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if inventory.get("schema_version") != INVENTORY_SCHEMA_VERSION:
        errors.append(
            f"PowerShell inventory schema mismatch: expected {INVENTORY_SCHEMA_VERSION}, got {inventory.get('schema_version')!r}"
        )
    validation = inventory.get("validation", {})
    if validation.get("errors"):
        errors.extend(f"inventory validation error: {error}" for error in validation.get("errors", []))
    warnings.extend(f"inventory warning: {warning}" for warning in validation.get("warnings", []))
    surfaces = inventory.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        errors.append("PowerShell inventory must contain surfaces[]")
        return set(), errors, warnings
    surface_paths: set[str] = set()
    for index, surface in enumerate(surfaces, start=1):
        if not isinstance(surface, dict):
            continue
        raw_path = scalar(surface.get("path")).strip()
        if raw_path:
            path = safe_inventory_path(raw_path, f"inventory surface #{index}", repo_root, errors)
            if path:
                surface_paths.add(path)
    return surface_paths, errors, warnings

def inventory_targets(inventory: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    for surface in inventory.get("surfaces", []):
        if not isinstance(surface, dict):
            continue
        if surface.get("inclusion_decision") != "include":
            continue
        if surface.get("source_type") not in ANALYZABLE_SOURCE_TYPES:
            continue
        path = scalar(surface.get("path")).strip()
        if path:
            targets.append(normalize_repo_path(path))
    return sorted(dict.fromkeys(targets))

def validate_fixture_manifest(
    manifest: dict[str, Any],
    check_map: dict[str, dict[str, Any]],
    surface_paths: set[str],
    repo_root: Path,
) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if manifest.get("schema_version") != FIXTURE_MANIFEST_SCHEMA_VERSION:
        errors.append(
            "custom fixture manifest schema mismatch: "
            f"expected {FIXTURE_MANIFEST_SCHEMA_VERSION}, got {manifest.get('schema_version')!r}"
        )
    raw_fixtures = manifest.get("fixtures")
    if not isinstance(raw_fixtures, list) or not raw_fixtures:
        errors.append("custom fixture manifest must contain fixtures[]")
        return {}, errors, warnings

    fixture_map: dict[str, dict[str, Any]] = {}
    fixture_kinds_by_check: dict[str, set[str]] = {check_id: set() for check_id in check_map}
    for index, raw_fixture in enumerate(raw_fixtures, start=1):
        label = f"custom fixture #{index}"
        if not isinstance(raw_fixture, dict):
            errors.append(f"{label}: entry is not an object")
            continue
        fixture_id = require_string(raw_fixture, "id", label, errors)
        kind = require_string(raw_fixture, "kind", label, errors)
        check_id = require_string(raw_fixture, "check_id", label, errors)
        path = safe_fixture_path(require_string(raw_fixture, "path", label, errors), label, errors)
        if fixture_id in fixture_map:
            errors.append(f"{label}: duplicate fixture id {fixture_id}")
        if kind not in {"negative", "control"}:
            errors.append(f"{label}: kind must be negative or control")
        if check_id not in check_map:
            errors.append(f"{label}: check_id {check_id!r} is not defined")
        else:
            fixture_kinds_by_check[check_id].add(kind)
        if path and path not in surface_paths:
            errors.append(f"{label}: fixture path {path} is missing from PowerShell surface inventory")
        if path and not (repo_root / path).is_file():
            errors.append(f"{label}: fixture source is missing: {path}")

        expected_findings = raw_fixture.get("expected_findings")
        if not isinstance(expected_findings, list):
            errors.append(f"{label}: expected_findings must be a list")
            expected_findings = []
        if kind == "negative" and not expected_findings:
            errors.append(f"{label}: negative fixtures must declare expected_findings")
        if kind == "control" and expected_findings:
            errors.append(f"{label}: control fixtures must not declare expected_findings")
        for expected_index, raw_expected in enumerate(expected_findings, start=1):
            expected_label = f"{label} expected finding #{expected_index}"
            if not isinstance(raw_expected, dict):
                errors.append(f"{expected_label}: entry is not an object")
                continue
            expected_check_id = require_string(raw_expected, "check_id", expected_label, errors)
            rule_name = require_string(raw_expected, "rule_name", expected_label, errors)
            severity = require_string(raw_expected, "severity", expected_label, errors)
            risk_class = require_string(raw_expected, "risk_class", expected_label, errors)
            line = raw_expected.get("line")
            if not isinstance(line, int) or line <= 0:
                errors.append(f"{expected_label}: line must be a positive integer")
            if expected_check_id != check_id:
                errors.append(f"{expected_label}: check_id must match fixture check_id {check_id}")
            check = check_map.get(expected_check_id)
            if check:
                if rule_name != check.get("rule_name"):
                    errors.append(f"{expected_label}: rule_name does not match custom check {expected_check_id}")
                if severity != check.get("expected_severity"):
                    errors.append(f"{expected_label}: severity does not match custom check {expected_check_id}")
                if risk_class not in check.get("risk_classes", []):
                    errors.append(f"{expected_label}: risk_class is not declared on custom check {expected_check_id}")
        if fixture_id:
            fixture_map[fixture_id] = {
                **raw_fixture,
                "path": path,
                "expected_findings": expected_findings,
            }

    for check_id, kinds in fixture_kinds_by_check.items():
        if "negative" not in kinds:
            errors.append(f"{check_id}: custom check has no negative fixture")
        if "control" not in kinds:
            errors.append(f"{check_id}: custom check has no corrected/control fixture")
    return fixture_map, errors, warnings
