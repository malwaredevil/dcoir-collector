#!/usr/bin/env python3
"""Matrix and manifest validation for rule-risk fixture reporting."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from powershell_rule_risk_fixtures_common import (
    FIXTURE_ROOT,
    MANIFEST_SCHEMA_VERSION,
    MATRIX_SCHEMA_VERSION,
    MINIMUM_RISK_CLASSES,
    is_relative_to,
    require_string,
    require_string_list,
    safe_fixture_path,
    scalar,
    validate_fixture_root,
)

def fixture_sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def validate_matrix(matrix: dict[str, Any], enforce_minimum_risks: bool) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if matrix.get("schema_version") != MATRIX_SCHEMA_VERSION:
        errors.append(
            "rule-to-risk matrix schema mismatch: "
            f"expected {MATRIX_SCHEMA_VERSION}, got {matrix.get('schema_version')!r}"
        )
    checks = matrix.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("rule-to-risk matrix must contain checks[]")
        return {}, errors, warnings

    seen_ids: set[str] = set()
    check_map: dict[str, dict[str, Any]] = {}
    covered_risks: set[str] = set()
    advisory_count = 0
    blocking_count = 0
    for index, raw_check in enumerate(checks, start=1):
        label = f"matrix check #{index}"
        if not isinstance(raw_check, dict):
            errors.append(f"{label} is not an object")
            continue
        check_id = require_string(raw_check, "id", label, errors)
        if check_id in seen_ids:
            errors.append(f"{label}: duplicate check id {check_id}")
        seen_ids.add(check_id)
        require_string(raw_check, "rule_name", label, errors)
        require_string(raw_check, "tool", label, errors)
        require_string(raw_check, "check_source", label, errors)
        expected_severity = require_string(raw_check, "expected_severity", label, errors)
        if expected_severity and expected_severity not in {"Information", "Warning", "Error"}:
            errors.append(f"{label}: expected_severity must be Information, Warning, or Error")
        risks = require_string_list(raw_check, "risk_classes", label, errors)
        covered_risks.update(risks)
        require_string_list(raw_check, "target_surfaces", label, errors)
        require_string(raw_check, "failure_impact", label, errors)
        require_string(raw_check, "recommended_fix", label, errors)
        fixtures = raw_check.get("fixtures")
        if not isinstance(fixtures, list) or not all(isinstance(item, str) and item.strip() for item in fixtures):
            errors.append(f"{label}: fixtures must be a list of strings")
            fixtures = []
        if raw_check.get("blocking") is True:
            blocking_count += 1
            if not fixtures:
                errors.append(f"{label}: blocking checks must name at least one fixture")
        elif raw_check.get("blocking") is False:
            advisory_count += 1
            if not scalar(raw_check.get("promotion_criteria")).strip():
                errors.append(f"{label}: advisory checks must state promotion_criteria")
        else:
            errors.append(f"{label}: blocking must be true or false")
        if check_id:
            check_map[check_id] = raw_check

    if blocking_count == 0:
        errors.append("matrix must contain at least one blocking check")
    if advisory_count == 0:
        warnings.append("matrix has no advisory checks; #263 expects advisory/blocking separation")
    if enforce_minimum_risks:
        missing = sorted(MINIMUM_RISK_CLASSES - covered_risks)
        if missing:
            errors.append("matrix is missing minimum #263 risk classes: " + ", ".join(missing))
    return check_map, errors, warnings

def validate_manifest(
    manifest: dict[str, Any],
    repo_root: Path,
    check_map: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        errors.append(
            "fixture manifest schema mismatch: "
            f"expected {MANIFEST_SCHEMA_VERSION}, got {manifest.get('schema_version')!r}"
        )
    fixtures = manifest.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        errors.append("fixture manifest must contain fixtures[]")
        return {}, errors, warnings

    fixture_root_valid = validate_fixture_root(repo_root, errors)
    fixture_map: dict[str, dict[str, Any]] = {}
    seen_ids: set[str] = set()
    control_count = 0
    negative_count = 0
    for index, raw_fixture in enumerate(fixtures, start=1):
        label = f"fixture #{index}"
        if not isinstance(raw_fixture, dict):
            errors.append(f"{label} is not an object")
            continue
        fixture_id = require_string(raw_fixture, "id", label, errors)
        if fixture_id in seen_ids:
            errors.append(f"{label}: duplicate fixture id {fixture_id}")
        seen_ids.add(fixture_id)
        kind = require_string(raw_fixture, "kind", label, errors)
        if kind not in {"negative", "control"}:
            errors.append(f"{label}: kind must be negative or control")
        path = safe_fixture_path(require_string(raw_fixture, "path", label, errors), label, errors)
        require_string(raw_fixture, "description", label, errors)
        expected_findings = raw_fixture.get("expected_findings")
        if not isinstance(expected_findings, list):
            errors.append(f"{label}: expected_findings must be a list")
            expected_findings = []
        if kind == "negative":
            negative_count += 1
            if not expected_findings:
                errors.append(f"{label}: negative fixtures must declare expected_findings")
        elif kind == "control":
            control_count += 1
            if expected_findings:
                errors.append(f"{label}: control fixtures must not declare expected findings")
        absolute: Path | None = None
        usable_path = path is not None and fixture_root_valid
        if path is not None:
            absolute = repo_root / path
            if not fixture_root_valid:
                absolute = None
            elif not is_relative_to(absolute, repo_root / FIXTURE_ROOT):
                errors.append(f"{label}: fixture path resolves outside {FIXTURE_ROOT.as_posix()}")
                absolute = None
                usable_path = False
            elif not absolute.exists():
                errors.append(f"{label}: fixture file is missing: {path}")
                usable_path = False
            elif not absolute.is_file():
                errors.append(f"{label}: fixture path must be a file: {path}")
                absolute = None
                usable_path = False
            elif absolute.stat().st_size == 0:
                errors.append(f"{label}: fixture file is empty: {path}")
                usable_path = False

        for expected_index, raw_expected in enumerate(expected_findings, start=1):
            expected_label = f"{label} expected finding #{expected_index}"
            if not isinstance(raw_expected, dict):
                errors.append(f"{expected_label} is not an object")
                continue
            check_id = require_string(raw_expected, "check_id", expected_label, errors)
            if check_id and check_id not in check_map:
                errors.append(f"{expected_label}: unknown check_id {check_id}")
            rule_name = require_string(raw_expected, "rule_name", expected_label, errors)
            severity = require_string(raw_expected, "severity", expected_label, errors)
            risk_class = require_string(raw_expected, "risk_class", expected_label, errors)
            if severity and severity not in {"Information", "Warning", "Error"}:
                errors.append(f"{expected_label}: severity must be Information, Warning, or Error")
            line = raw_expected.get("line")
            if not isinstance(line, int) or line < 1:
                errors.append(f"{expected_label}: line must be a positive integer")
            if check_id in check_map:
                check = check_map[check_id]
                if rule_name and rule_name != check.get("rule_name"):
                    errors.append(f"{expected_label}: rule_name does not match matrix check {check_id}")
                if severity and severity != check.get("expected_severity"):
                    errors.append(f"{expected_label}: severity does not match matrix check {check_id}")
                if risk_class and risk_class not in check.get("risk_classes", []):
                    errors.append(f"{expected_label}: risk_class is not declared on matrix check {check_id}")
        if fixture_id and path is not None and usable_path:
            enriched = dict(raw_fixture)
            enriched["path"] = path
            enriched["sha256"] = fixture_sha256_file(absolute) if absolute is not None and absolute.exists() and absolute.is_file() else None
            fixture_map[fixture_id] = enriched

    if control_count == 0:
        errors.append("fixture manifest must contain at least one control fixture")
    if negative_count == 0:
        errors.append("fixture manifest must contain at least one negative fixture")
    matrix_fixture_ids = {
        fixture_id
        for check in check_map.values()
        if check.get("blocking") is True
        for fixture_id in check.get("fixtures", [])
    }
    missing_fixtures = sorted(fixture_id for fixture_id in matrix_fixture_ids if fixture_id not in fixture_map)
    if missing_fixtures:
        errors.append("matrix references missing fixture ids: " + ", ".join(missing_fixtures))
    unreferenced_negatives = sorted(
        fixture_id
        for fixture_id, fixture in fixture_map.items()
        if fixture.get("kind") == "negative" and fixture_id not in matrix_fixture_ids
    )
    if unreferenced_negatives:
        warnings.append("negative fixtures not referenced by a blocking check: " + ", ".join(unreferenced_negatives))
    return fixture_map, errors, warnings
