#!/usr/bin/env python3
"""Finding classification and summary helpers for finding governance."""
from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from powershell_finding_governance_common import Finding, scalar, severity_rank, slash_path


def finding_matches_baseline(finding: Finding, record: dict[str, Any]) -> bool:
    if scalar(record.get("fingerprint")).strip() != finding.fingerprint:
        return False
    if scalar(record.get("path")).strip() != finding.path:
        return False
    record_rule = scalar(record.get("rule_name")).strip()
    record_check = scalar(record.get("check_id")).strip()
    return (record_rule and record_rule == finding.rule_name) or (record_check and record_check == finding.check_id)


def finding_matches_suppression(finding: Finding, suppression: dict[str, Any]) -> bool:
    if scalar(suppression.get("fingerprint")).strip() != finding.fingerprint:
        return False
    if scalar(suppression.get("path")).strip() != finding.path:
        return False
    suppression_rule = scalar(suppression.get("rule_name")).strip()
    suppression_check = scalar(suppression.get("check_id")).strip()
    return (suppression_rule and suppression_rule == finding.rule_name) or (
        suppression_check and suppression_check == finding.check_id
    )


def path_prefix_matches(path: str, prefix: str) -> bool:
    normalized_path = slash_path(path)
    normalized_prefix = slash_path(prefix).rstrip("/")
    if not normalized_prefix:
        return False
    return normalized_path == normalized_prefix or normalized_path.startswith(f"{normalized_prefix}/")


def finding_matches_rule(finding: Finding, rule: dict[str, Any]) -> bool:
    prefixes = [scalar(prefix).strip() for prefix in rule.get("path_prefixes", []) if scalar(prefix).strip()]
    paths = [scalar(path).strip() for path in rule.get("paths", []) if scalar(path).strip()]
    rule_names = [scalar(name).strip() for name in rule.get("rule_names", []) if scalar(name).strip()]
    check_ids = [scalar(check_id).strip() for check_id in rule.get("check_ids", []) if scalar(check_id).strip()]
    source_schemas = [scalar(schema).strip() for schema in rule.get("source_schema_versions", []) if scalar(schema).strip()]
    severities = [scalar(severity).strip().casefold() for severity in rule.get("severities", []) if scalar(severity).strip()]
    if prefixes and not any(path_prefix_matches(finding.path, prefix) for prefix in prefixes):
        return False
    if paths and finding.path not in paths:
        return False
    if rule_names and finding.rule_name not in rule_names:
        return False
    if check_ids and finding.check_id not in check_ids:
        return False
    if source_schemas and finding.source_schema_version not in source_schemas:
        return False
    if severities and finding.severity.casefold() not in severities:
        return False
    return bool(prefixes or paths or rule_names or check_ids or source_schemas or severities)


def exception_approves_missing(record: dict[str, Any], exceptions: list[dict[str, Any]]) -> bool:
    record_id = scalar(record.get("id")).strip()
    fingerprint = scalar(record.get("fingerprint")).strip()
    for exception in exceptions:
        if not isinstance(exception, dict):
            continue
        if scalar(exception.get("kind")).strip() != "unexpected_disappearance":
            continue
        if scalar(exception.get("baseline_record_id")).strip() == record_id:
            return True
        if scalar(exception.get("fingerprint")).strip() == fingerprint:
            return True
    return False


def classify_findings(governance: dict[str, Any], findings: list[Finding], today: date) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    errors: list[str] = []
    baseline_records = [record for record in governance.get("baseline_records", []) if isinstance(record, dict)]
    suppressions = [suppression for suppression in governance.get("suppressions", []) if isinstance(suppression, dict)]
    classification_rules = [rule for rule in governance.get("classification_rules", []) if isinstance(rule, dict)]
    approved_exceptions = [item for item in governance.get("approved_delta_exceptions", []) if isinstance(item, dict)]
    classifications: list[dict[str, Any]] = []
    matched_baseline_ids: Counter[str] = Counter()
    matched_suppression_ids: Counter[str] = Counter()
    decision_counts: Counter[str] = Counter()
    for finding in findings:
        item = finding.as_report_item()
        matched_record = next((record for record in baseline_records if finding_matches_baseline(finding, record)), None)
        if matched_record:
            baseline_id = scalar(matched_record.get("id")).strip()
            matched_baseline_ids[baseline_id] += 1
            baseline_severity = scalar(matched_record.get("severity")).strip()
            if severity_rank(finding.severity) > severity_rank(baseline_severity):
                errors.append(
                    "severity increase for baseline "
                    f"{baseline_id}: current {finding.severity} exceeds baseline {baseline_severity}"
                )
            decision = scalar(matched_record.get("decision")).strip()
            item["governance"] = {
                "decision": decision,
                "matched_by": "baseline_record",
                "record_id": baseline_id,
                "rationale": scalar(matched_record.get("rationale")).strip(),
                "owner": scalar(matched_record.get("owner")).strip(),
                "reviewer": scalar(matched_record.get("reviewer")).strip(),
                "review_date": scalar(matched_record.get("review_date")).strip(),
            }
            decision_counts[decision] += 1
            classifications.append(item)
            continue
        matched_suppression = next(
            (suppression for suppression in suppressions if finding_matches_suppression(finding, suppression)),
            None,
        )
        if matched_suppression:
            suppression_id = scalar(matched_suppression.get("id")).strip()
            matched_suppression_ids[suppression_id] += 1
            decision = scalar(matched_suppression.get("decision") or "accepted risk").strip()
            item["governance"] = {
                "decision": decision,
                "matched_by": "suppression",
                "record_id": suppression_id,
                "rationale": scalar(matched_suppression.get("rationale")).strip(),
                "owner": scalar(matched_suppression.get("owner")).strip(),
                "reviewer": scalar(matched_suppression.get("reviewer")).strip(),
                "review_date": scalar(matched_suppression.get("review_date")).strip(),
            }
            decision_counts[decision] += 1
            classifications.append(item)
            continue
        matched_rule = next((rule for rule in classification_rules if finding_matches_rule(finding, rule)), None)
        if matched_rule:
            decision = scalar(matched_rule.get("decision")).strip()
            item["governance"] = {
                "decision": decision,
                "matched_by": "classification_rule",
                "record_id": scalar(matched_rule.get("id")).strip(),
                "rationale": scalar(matched_rule.get("rationale")).strip(),
                "owner": scalar(matched_rule.get("owner")).strip(),
                "reviewer": scalar(matched_rule.get("reviewer")).strip(),
                "review_date": scalar(matched_rule.get("review_date")).strip(),
            }
            decision_counts[decision] += 1
            classifications.append(item)
            continue
        item["governance"] = {
            "decision": "unclassified",
            "matched_by": "none",
            "record_id": None,
        }
        decision_counts["unclassified"] += 1
        errors.append(
            "new unclassified PowerShell finding: "
            f"{finding.path} {finding.rule_name or finding.check_id} {finding.fingerprint}"
        )
        classifications.append(item)
    for record in baseline_records:
        record_id = scalar(record.get("id")).strip()
        expected = record.get("expected_match_count", 1)
        actual = matched_baseline_ids.get(record_id, 0)
        if actual == 0 and exception_approves_missing(record, approved_exceptions):
            continue
        if actual != expected:
            errors.append(
                f"baseline record {record_id} matched {actual} findings, expected {expected}; "
                "unexpected disappearance or count regression"
            )
    for suppression in suppressions:
        suppression_id = scalar(suppression.get("id")).strip()
        expected = suppression.get("expected_match_count", 1)
        actual = matched_suppression_ids.get(suppression_id, 0)
        if actual != expected:
            errors.append(f"suppression {suppression_id} matched {actual} findings, expected {expected}")
    delta = {
        "baseline_record_count": len(baseline_records),
        "matched_baseline_record_count": sum(matched_baseline_ids.values()),
        "suppression_count": len(suppressions),
        "matched_suppression_count": sum(matched_suppression_ids.values()),
        "unclassified_finding_count": decision_counts.get("unclassified", 0),
        "decision_counts": dict(sorted(decision_counts.items())),
        "baseline_match_counts": dict(sorted(matched_baseline_ids.items())),
        "suppression_match_counts": dict(sorted(matched_suppression_ids.items())),
        "as_of": today.isoformat(),
    }
    return classifications, delta, errors


def governance_summary(findings: list[Finding], classifications: list[dict[str, Any]], delta: dict[str, Any]) -> dict[str, Any]:
    severity_counts = Counter(finding.severity for finding in findings)
    source_counts = Counter(finding.source_schema_version or finding.source_report for finding in findings)
    return {
        "finding_count": len(findings),
        "classified_finding_count": len([item for item in classifications if item["governance"]["decision"] != "unclassified"]),
        "unclassified_finding_count": delta["unclassified_finding_count"],
        "baseline_record_count": delta["baseline_record_count"],
        "matched_baseline_record_count": delta["matched_baseline_record_count"],
        "suppression_count": delta["suppression_count"],
        "matched_suppression_count": delta["matched_suppression_count"],
        "decision_counts": delta["decision_counts"],
        "severity_counts": dict(sorted(severity_counts.items())),
        "source_schema_counts": dict(sorted(source_counts.items())),
    }
