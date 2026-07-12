#!/usr/bin/env python3
"""Governance policy validation for PowerShell finding governance."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from powershell_finding_governance_common import (
    ALLOWED_DECISIONS,
    EXPIRY_OR_REVISIT_FIELDS,
    GOVERNANCE_SCHEMA_VERSION,
    LINE_OR_LOCATOR_FIELDS,
    REVIEW_FIELDS,
    GovernanceError,
    has_any_text,
    is_blanket_selector,
    normalize_date,
    scalar,
    validate_governance_path,
    validate_governance_path_prefix,
)
from powershell_finding_governance_sources import generated_output_paths


def validate_review_fields(prefix: str, item: dict[str, Any], errors: list[str]) -> None:
    for key in REVIEW_FIELDS:
        if not scalar(item.get(key)).strip():
            errors.append(f"{prefix} missing {key}")
    if not has_any_text(item, EXPIRY_OR_REVISIT_FIELDS):
        errors.append(f"{prefix} missing expiry_or_revisit")


def validate_baseline_record(
    record: dict[str, Any],
    allowed_decisions: set[str],
    today: date,
    errors: list[str],
    repo_root: Path,
) -> None:
    record_id = scalar(record.get("id")).strip() or "<missing-id>"
    prefix = f"baseline record {record_id}"
    if not scalar(record.get("id")).strip():
        errors.append("baseline record missing id")
    decision = scalar(record.get("decision")).strip()
    if decision not in allowed_decisions:
        errors.append(f"{prefix} decision {decision!r} is not allowed")
    path = scalar(record.get("path")).strip()
    if not path:
        errors.append(f"{prefix} missing path")
    else:
        try:
            record["path"] = validate_governance_path(path, repo_root, prefix)
        except GovernanceError as exc:
            errors.append(str(exc))
    if not has_any_text(record, ("rule_name", "check_id")):
        errors.append(f"{prefix} missing rule_name_or_check_id")
    if not has_any_text(record, LINE_OR_LOCATOR_FIELDS):
        errors.append(f"{prefix} missing line_or_stable_locator")
    for key in ("severity", "fingerprint"):
        if not scalar(record.get(key)).strip():
            errors.append(f"{prefix} missing {key}")
    validate_review_fields(prefix, record, errors)
    expected = record.get("expected_match_count", 1)
    if not isinstance(expected, int) or expected < 1:
        errors.append(f"{prefix} expected_match_count must be a positive integer")
    expires_on = scalar(record.get("expires_on")).strip()
    if expires_on:
        parsed = normalize_date(expires_on)
        if parsed is None:
            errors.append(f"{prefix} expires_on is not ISO-8601 date")
        elif parsed < today:
            errors.append(f"{prefix} is stale: expires_on {expires_on} is before {today.isoformat()}")


def validate_suppression(
    suppression: dict[str, Any],
    allowed_decisions: set[str],
    generated_paths: set[str],
    today: date,
    errors: list[str],
    repo_root: Path,
) -> None:
    suppression_id = scalar(suppression.get("id")).strip() or "<missing-id>"
    prefix = f"suppression {suppression_id}"
    if not scalar(suppression.get("id")).strip():
        errors.append("suppression missing id")
    decision = scalar(suppression.get("decision") or "accepted risk").strip()
    if decision not in allowed_decisions:
        errors.append(f"{prefix} decision {decision!r} is not allowed")
    path = scalar(suppression.get("path")).strip()
    if not path:
        errors.append(f"{prefix} missing path")
    else:
        try:
            path = validate_governance_path(path, repo_root, prefix)
            suppression["path"] = path
        except GovernanceError as exc:
            errors.append(str(exc))
    rule_name = scalar(suppression.get("rule_name") or suppression.get("check_id")).strip()
    if is_blanket_selector(rule_name):
        errors.append(f"{prefix} uses a blanket or wildcard rule")
    if not scalar(suppression.get("fingerprint")).strip():
        errors.append(f"{prefix} missing fingerprint")
    if scalar(suppression.get("scope")).strip() not in {"line", "fingerprint", "file"}:
        errors.append(f"{prefix} scope must be line, fingerprint, or file")
    validate_review_fields(prefix, suppression, errors)
    expected = suppression.get("expected_match_count", 1)
    if not isinstance(expected, int) or expected < 1:
        errors.append(f"{prefix} expected_match_count must be a positive integer")
    expires_on = scalar(suppression.get("expires_on")).strip()
    if expires_on:
        parsed = normalize_date(expires_on)
        if parsed is None:
            errors.append(f"{prefix} expires_on is not ISO-8601 date")
        elif parsed < today:
            errors.append(f"{prefix} is stale: expires_on {expires_on} is before {today.isoformat()}")
    target_kind = scalar(suppression.get("target_kind")).strip()
    if path in generated_paths or target_kind == "generated_output":
        coverage = scalar(suppression.get("assembly_source_coverage_report")).strip()
        reason = scalar(suppression.get("reviewed_generated_reason")).strip()
        if coverage != "#265" or not reason:
            errors.append(
                f"{prefix} targets generated output without #265 assembly coverage and reviewed generated reason"
            )


def validate_rule_path_selectors(rule: dict[str, Any], rule_id: str, repo_root: Path, errors: list[str]) -> None:
    paths = rule.get("paths")
    if paths is not None:
        if not isinstance(paths, list):
            errors.append(f"classification rule {rule_id} paths must be a list")
        else:
            normalized_paths: list[str] = []
            for index, path in enumerate(paths, start=1):
                try:
                    normalized_paths.append(
                        validate_governance_path(path, repo_root, f"classification rule {rule_id} paths[{index}]")
                    )
                except GovernanceError as exc:
                    errors.append(str(exc))
            rule["paths"] = normalized_paths
    prefixes = rule.get("path_prefixes")
    if prefixes is not None:
        if not isinstance(prefixes, list):
            errors.append(f"classification rule {rule_id} path_prefixes must be a list")
        else:
            normalized_prefixes: list[str] = []
            for index, prefix in enumerate(prefixes, start=1):
                try:
                    normalized_prefixes.append(
                        validate_governance_path_prefix(
                            prefix,
                            repo_root,
                            f"classification rule {rule_id} path_prefixes[{index}]",
                        )
                    )
                except GovernanceError as exc:
                    errors.append(str(exc))
            rule["path_prefixes"] = normalized_prefixes


def validate_governance_doc(
    repo_root: Path,
    governance: dict[str, Any],
    assembly_report: dict[str, Any] | None,
    today: date,
) -> list[str]:
    errors: list[str] = []
    if governance.get("schema_version") != GOVERNANCE_SCHEMA_VERSION:
        errors.append(
            "PowerShell finding governance schema mismatch: "
            f"expected {GOVERNANCE_SCHEMA_VERSION}, got {governance.get('schema_version')!r}"
        )
    policy = governance.get("policy")
    if not isinstance(policy, dict):
        errors.append("PowerShell finding governance policy must be an object")
        policy = {}
    allowed_decisions = set(policy.get("allowed_decisions") or [])
    missing_decisions = sorted(ALLOWED_DECISIONS - allowed_decisions)
    if missing_decisions:
        errors.append(f"PowerShell finding governance policy missing decisions: {', '.join(missing_decisions)}")
    baseline_records = governance.get("baseline_records", [])
    suppressions = governance.get("suppressions", [])
    classification_rules = governance.get("classification_rules", [])
    approved_exceptions = governance.get("approved_delta_exceptions", [])
    if not isinstance(baseline_records, list):
        errors.append("PowerShell finding governance baseline_records must be a list")
        baseline_records = []
    if not isinstance(suppressions, list):
        errors.append("PowerShell finding governance suppressions must be a list")
        suppressions = []
    if not isinstance(classification_rules, list):
        errors.append("PowerShell finding governance classification_rules must be a list")
        classification_rules = []
    if not isinstance(approved_exceptions, list):
        errors.append("PowerShell finding governance approved_delta_exceptions must be a list")
    max_baseline_records = policy.get("max_baseline_records")
    if isinstance(max_baseline_records, int) and len(baseline_records) > max_baseline_records:
        errors.append(
            "PowerShell finding governance stale baseline growth: "
            f"{len(baseline_records)} baseline records exceeds max_baseline_records {max_baseline_records}"
        )
    generated_paths = generated_output_paths(assembly_report)
    seen_baseline_keys: set[tuple[str, str, str]] = set()
    for record in baseline_records:
        if not isinstance(record, dict):
            errors.append("baseline record must be an object")
            continue
        validate_baseline_record(record, allowed_decisions, today, errors, repo_root)
        key = (
            scalar(record.get("path")).strip(),
            scalar(record.get("rule_name") or record.get("check_id")).strip(),
            scalar(record.get("fingerprint")).strip(),
        )
        if key in seen_baseline_keys:
            errors.append(f"duplicate baseline record for {key[0]} {key[1]} {key[2]}")
        seen_baseline_keys.add(key)
    seen_suppression_keys: set[tuple[str, str, str]] = set()
    for suppression in suppressions:
        if not isinstance(suppression, dict):
            errors.append("suppression must be an object")
            continue
        validate_suppression(suppression, allowed_decisions, generated_paths, today, errors, repo_root)
        key = (
            scalar(suppression.get("path")).strip(),
            scalar(suppression.get("rule_name") or suppression.get("check_id")).strip(),
            scalar(suppression.get("fingerprint")).strip(),
        )
        if key in seen_suppression_keys:
            errors.append(f"duplicate suppression for {key[0]} {key[1]} {key[2]}")
        seen_suppression_keys.add(key)
    for rule in classification_rules:
        if not isinstance(rule, dict):
            errors.append("classification rule must be an object")
            continue
        rule_id = scalar(rule.get("id")).strip() or "<missing-id>"
        decision = scalar(rule.get("decision")).strip()
        if decision not in allowed_decisions:
            errors.append(f"classification rule {rule_id} decision {decision!r} is not allowed")
        if not scalar(rule.get("id")).strip():
            errors.append("classification rule missing id")
        validate_rule_path_selectors(rule, rule_id, repo_root, errors)
        if not any(isinstance(rule.get(key), list) and rule.get(key) for key in ("path_prefixes", "paths", "rule_names", "check_ids")):
            errors.append(f"classification rule {rule_id} has no bounded selector")
        validate_review_fields(f"classification rule {rule_id}", rule, errors)
    return errors
