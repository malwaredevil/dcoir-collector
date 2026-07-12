#!/usr/bin/env python3
"""Finding normalization and evidence-channel helpers for PowerShell review-assist reports."""
from __future__ import annotations

from collections import Counter
from typing import Any

from powershell_review_assist_common import SCHEMA_VERSIONS, scalar, slash_path

def matrix_by_rule(matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for check in matrix.get("checks", []):
        if isinstance(check, dict):
            rule_name = scalar(check.get("rule_name")).strip()
            check_id = scalar(check.get("id")).strip()
            if rule_name:
                result[rule_name] = check
            if check_id:
                result[check_id] = check
    return result

def governance_index(governance_report: dict[str, Any]) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    index: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for item in governance_report.get("classifications", []):
        if not isinstance(item, dict):
            continue
        source_report = slash_path(scalar(item.get("source_report")))
        path = slash_path(scalar(item.get("path")))
        rule_name = scalar(item.get("rule_name")).strip()
        check_id = scalar(item.get("check_id")).strip()
        fingerprint = scalar(item.get("fingerprint")).strip()
        keys = [
            (source_report, path, rule_name, check_id),
            (source_report, path, rule_name, ""),
        ]
        if fingerprint:
            keys.append((source_report, path, rule_name, fingerprint))
        for key in keys:
            if key not in index:
                index[key] = item
    return index

def find_governance(
    index: dict[tuple[str, str, str, str], dict[str, Any]],
    source_report: str,
    path: str,
    rule_name: str,
    check_id: str,
    fingerprint: str,
) -> dict[str, Any] | None:
    keys = [
        (source_report, path, rule_name, check_id),
        (source_report, path, rule_name, ""),
        (source_report, path, rule_name, fingerprint),
    ]
    return next((index[key] for key in keys if key in index), None)

def target_kind(path: str, generated_paths: set[str]) -> str:
    if path in generated_paths:
        return "generated_output"
    if "/fixtures/" in path:
        return "fixture"
    if path.endswith(".ps1.txt"):
        return "source_part"
    if "/source/parts/" in path:
        return "source_part"
    if "/harness/source/parts/" in path:
        return "source_part"
    if path.startswith(".github/"):
        return "workflow_reference"
    return "source_or_tooling"

def normalize_line(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    text = scalar(value).strip()
    if text.isdigit():
        return int(text)
    return None

def governance_states(governance_item: dict[str, Any] | None) -> tuple[str, str, str, dict[str, Any]]:
    if not isinstance(governance_item, dict):
        return "unclassified", "not_baselined", "not_suppressed", {}
    governance = governance_item.get("governance")
    if not isinstance(governance, dict):
        return "unclassified", "not_baselined", "not_suppressed", {}
    decision = scalar(governance.get("decision")).strip() or "unclassified"
    matched_by = scalar(governance.get("matched_by")).strip()
    baseline_state = "baseline_record" if matched_by == "baseline_record" else "not_baselined"
    suppression_state = "suppression" if matched_by == "suppression" else "not_suppressed"
    return decision, baseline_state, suppression_state, governance

def normalized_finding(
    *,
    raw: dict[str, Any],
    source_report: str,
    source_schema: str,
    evidence_kind: str,
    matrix_context: dict[str, Any] | None,
    governance_item: dict[str, Any] | None,
    generated_paths: set[str],
) -> dict[str, Any]:
    path = slash_path(scalar(raw.get("path") or raw.get("target_path")))
    rule_name = scalar(raw.get("rule_name") or raw.get("rule")).strip()
    check_id = scalar(raw.get("check_id") or raw.get("matrix_check_id") or raw.get("id")).strip()
    fingerprint = scalar(raw.get("fingerprint")).strip()
    risk_classes = raw.get("risk_classes")
    if not isinstance(risk_classes, list):
        risk_classes = []
    if not risk_classes and matrix_context:
        risk_classes = matrix_context.get("risk_classes", [])
    target_surfaces = raw.get("target_surfaces")
    if not isinstance(target_surfaces, list):
        target_surfaces = []
    if not target_surfaces and matrix_context:
        target_surfaces = matrix_context.get("target_surfaces", [])
    impact = scalar(raw.get("impact") or raw.get("failure_impact")).strip()
    if not impact and matrix_context:
        impact = scalar(matrix_context.get("failure_impact")).strip()
    recommended = scalar(raw.get("recommended_fix") or raw.get("fix")).strip()
    if not recommended and matrix_context:
        recommended = scalar(matrix_context.get("recommended_fix")).strip()
    decision, baseline_state, suppression_state, governance = governance_states(governance_item)
    return {
        "source_report_path": source_report,
        "source_schema_version": source_schema,
        "evidence_kind": evidence_kind,
        "path": path,
        "line": normalize_line(raw.get("line")),
        "column": normalize_line(raw.get("column")),
        "severity": scalar(raw.get("severity") or "Warning").strip(),
        "rule_name": rule_name,
        "check_id": check_id,
        "risk_classes": list(risk_classes),
        "target_surfaces": list(target_surfaces),
        "fingerprint": fingerprint,
        "observed_behavior": scalar(raw.get("observed_problem") or raw.get("message")).strip(),
        "impact": impact,
        "recommended_fix_direction": recommended,
        "governance_classification": decision,
        "baseline_state": baseline_state,
        "suppression_state": suppression_state,
        "governance": governance,
        "source_generated_target_kind": target_kind(path, generated_paths),
    }

def collect_normalized_findings(docs: dict[str, dict[str, Any]], source_report_paths: dict[str, str]) -> list[dict[str, Any]]:
    matrix = matrix_by_rule(docs.get("rule_risk_matrix", {}))
    governance = governance_index(docs.get("governance_report", {}))
    assembly_outputs = docs.get("assembly_parity_report", {}).get("generated_outputs", [])
    generated_paths = {
        slash_path(scalar(output.get("path")))
        for output in assembly_outputs
        if isinstance(output, dict) and scalar(output.get("path")).strip()
    }
    findings: list[dict[str, Any]] = []
    for raw in docs.get("rule_risk_report", {}).get("findings", []):
        if not isinstance(raw, dict):
            continue
        path = slash_path(scalar(raw.get("path") or raw.get("target_path")))
        rule_name = scalar(raw.get("rule_name")).strip()
        check_id = scalar(raw.get("check_id") or raw.get("matrix_check_id")).strip()
        source_report = source_report_paths["rule_risk_report"]
        governance_item = find_governance(
            governance,
            source_report,
            path,
            rule_name,
            check_id,
            scalar(raw.get("fingerprint")).strip(),
        )
        findings.append(
            normalized_finding(
                raw=raw,
                source_report=source_report,
                source_schema=SCHEMA_VERSIONS["rule_risk_report"],
                evidence_kind="deterministic_fixture_analyzer",
                matrix_context=matrix.get(rule_name) or matrix.get(check_id),
                governance_item=governance_item,
                generated_paths=generated_paths,
            )
        )
    for raw in docs.get("custom_report", {}).get("findings", []):
        if not isinstance(raw, dict):
            continue
        path = slash_path(scalar(raw.get("path")))
        rule_name = scalar(raw.get("rule_name")).strip()
        check_id = scalar(raw.get("check_id") or raw.get("matrix_check_id")).strip()
        source_report = source_report_paths["custom_report"]
        governance_item = find_governance(
            governance,
            source_report,
            path,
            rule_name,
            check_id,
            scalar(raw.get("fingerprint")).strip(),
        )
        findings.append(
            normalized_finding(
                raw=raw,
                source_report=source_report,
                source_schema=SCHEMA_VERSIONS["custom_report"],
                evidence_kind="dcoir_custom_static_check",
                matrix_context=None,
                governance_item=governance_item,
                generated_paths=generated_paths,
            )
        )
    analyzer = docs.get("analyzer_report")
    if isinstance(analyzer, dict):
        for raw in analyzer.get("findings", []):
            if not isinstance(raw, dict):
                continue
            findings.append(
                normalized_finding(
                    raw=raw,
                    source_report=source_report_paths["analyzer_report"],
                    source_schema=SCHEMA_VERSIONS["analyzer_report"],
                    evidence_kind="psscriptanalyzer",
                    matrix_context=None,
                    governance_item=None,
                    generated_paths=generated_paths,
                )
            )
    return findings

def validate_normalized_findings(findings: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for index, finding in enumerate(findings, start=1):
        prefix = f"normalized finding {index} {finding.get('path')} {finding.get('rule_name') or finding.get('check_id')}"
        if finding.get("evidence_kind") == "deterministic_fixture_analyzer":
            if not finding.get("risk_classes"):
                errors.append(f"{prefix} missing #263 matrix risk_classes")
            if not scalar(finding.get("impact")).strip():
                errors.append(f"{prefix} missing #263 matrix impact")
            if not finding.get("target_surfaces"):
                errors.append(f"{prefix} missing #263 matrix target_surfaces")
            if not scalar(finding.get("recommended_fix_direction")).strip():
                errors.append(f"{prefix} missing #263 matrix recommended_fix_direction")
    return errors

def path_decision(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": scalar(item.get("path")).strip(),
        "category": scalar(item.get("category")).strip(),
        "source_type": scalar(item.get("source_type")).strip(),
        "status": scalar(item.get("status")).strip(),
        "reason": scalar(item.get("decision_reason")).strip(),
    }

def surface_inventory_section(report: dict[str, Any]) -> dict[str, Any]:
    surfaces = [item for item in report.get("surfaces", []) if isinstance(item, dict)]
    by_decision: dict[str, list[dict[str, Any]]] = {"include": [], "exclude": [], "reference": [], "skip": []}
    for surface in surfaces:
        decision = scalar(surface.get("inclusion_decision")).strip() or "unknown"
        by_decision.setdefault(decision, []).append(path_decision(surface))
    skipped_paths = report.get("skipped_paths")
    if isinstance(skipped_paths, list):
        by_decision["skip"].extend(
            {
                "path": slash_path(scalar(path)),
                "category": "",
                "source_type": "",
                "status": "skipped",
                "reason": "reported by source inventory skipped_paths",
            }
            for path in skipped_paths
        )
    return {
        "mode": report.get("mode"),
        "summary": report.get("summary", {}),
        "outputs": report.get("outputs", {}),
        "path_decision_counts": {key: len(value) for key, value in sorted(by_decision.items())},
        "included_paths": by_decision.get("include", []),
        "excluded_paths": by_decision.get("exclude", []),
        "reference_paths": by_decision.get("reference", []),
        "skipped_paths": by_decision.get("skip", []),
    }

def fixture_outcomes(report: dict[str, Any]) -> dict[str, Any]:
    fixtures = [item for item in report.get("fixtures", []) if isinstance(item, dict)]
    counter = Counter(scalar(item.get("kind")).strip() or "unknown" for item in fixtures)
    return {
        "counts": dict(sorted(counter.items())),
        "fixtures": [
            {
                "id": item.get("id"),
                "kind": item.get("kind"),
                "path": item.get("path"),
                "expected_finding_count": item.get("expected_finding_count"),
                "observed_finding_count": item.get("observed_finding_count"),
                "observed_rules": item.get("observed_rules", []),
            }
            for item in fixtures
        ],
    }

def collect_unclaimed_artifacts(engine_report: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for item in engine_report.get("declared_output_artifacts", []):
        if not isinstance(item, dict):
            continue
        claimed = item.get("evidence_claimed_by_boundary")
        status = scalar(item.get("artifact_status")).strip()
        exists = item.get("exists")
        if claimed is False or status in {"not_committed_in_267_boundary", "external_or_future"} or exists in {False, None}:
            artifacts.append(
                {
                    "source_issue": 267,
                    "id": item.get("id"),
                    "path": item.get("path"),
                    "artifact_status": status,
                    "blocking": item.get("blocking"),
                    "evidence_claimed_by_boundary": claimed,
                    "reason": "Declared by #267 boundary but not committed, not claimed, external, or future evidence.",
                }
            )
    return artifacts

from powershell_review_assist_evidence import evidence_channels
