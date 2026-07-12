#!/usr/bin/env python3
"""Evidence-channel rendering for PowerShell review-assist reports."""
from collections import Counter
from typing import Any

from powershell_review_assist_findings import fixture_outcomes

def evidence_channels(
    docs: dict[str, dict[str, Any]],
    source_entries: dict[str, dict[str, Any]],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    kind_counts = Counter(item["evidence_kind"] for item in findings)
    boundary = docs.get("engine_boundary_report", {})
    governance = docs.get("governance_report", {})
    assembly = docs.get("assembly_parity_report", {})
    rule_risk = docs.get("rule_risk_report", {})
    custom = docs.get("custom_report", {})
    function_reachability = docs.get("function_reachability_report", {})
    function_summary = function_reachability.get("summary", {}) if isinstance(function_reachability.get("summary"), dict) else {}
    analyzer_entry = source_entries["analyzer_report"]
    analyzer_status = analyzer_entry["validation_status"]
    if not analyzer_entry["present"]:
        analyzer_state = "optional_missing"
    elif analyzer_status == "success":
        analyzer_state = "present_validated"
    else:
        analyzer_state = "present_failed"
    return {
        "analyzer": {
            "source_issue": 262,
            "state": analyzer_state,
            "path": analyzer_entry["path"],
            "finding_count": kind_counts.get("psscriptanalyzer", 0),
            "claim": "live PSScriptAnalyzer evidence is not claimed unless this report is present and valid",
        },
        "deterministic_fixture_analyzer": {
            "source_issue": 263,
            "state": source_entries["rule_risk_report"]["validation_status"],
            "finding_count": kind_counts.get("deterministic_fixture_analyzer", 0),
            "environment_gap": rule_risk.get("environment_gap"),
            "fixture_outcomes": fixture_outcomes(rule_risk),
        },
        "custom_checks": {
            "source_issue": 264,
            "state": source_entries["custom_report"]["validation_status"],
            "finding_count": kind_counts.get("dcoir_custom_static_check", 0),
            "fixture_outcomes": fixture_outcomes(custom),
        },
        "assembly_parity": {
            "source_issue": 265,
            "state": source_entries["assembly_parity_report"]["validation_status"],
            "summary": assembly.get("summary", {}),
            "generated_outputs": [
                {
                    "id": item.get("id"),
                    "path": item.get("path"),
                    "line_mapping_status": item.get("line_mapping_status"),
                    "parse": item.get("parse"),
                    "parity": item.get("parity"),
                }
                for item in assembly.get("generated_outputs", [])
                if isinstance(item, dict)
            ],
            "baseline_comparison": assembly.get("baseline_comparison"),
        },
        "finding_governance": {
            "source_issue": 266,
            "state": source_entries["governance_report"]["validation_status"],
            "summary": governance.get("summary", {}),
            "baseline_delta": governance.get("baseline_delta", {}),
            "governance": governance.get("governance", {}),
        },
        "engine_boundary": {
            "source_issue": 267,
            "state": source_entries["engine_boundary_report"]["validation_status"],
            "summary": boundary.get("summary", {}),
            "declared_output_artifacts": boundary.get("declared_output_artifacts", []),
            "independent_analyzer_enforcement_proof": boundary.get("independent_analyzer_enforcement_proof", {}),
        },
        "function_reachability": {
            "source_issue": 306,
            "state": source_entries["function_reachability_report"]["validation_status"],
            "path": source_entries["function_reachability_report"]["path"],
            "parser_mode": function_summary.get("parser_mode"),
            "function_count": function_summary.get("function_count", 0),
            "classification_counts": function_summary.get("classification_counts", {}),
            "dynamic_invocation_site_count": function_summary.get("dynamic_invocation_site_count", 0),
            "coverage_state": function_summary.get("coverage_state"),
            "claim": "report-only reachability evidence; no function deletion readiness or runtime absence is claimed",
        },
        "pester_boundary": {
            "source_issue": 267,
            "state": "supporting_non_blocking",
            "pester_boundary": boundary.get("pester_boundary", {}),
            "claim": "Pester may support later runtime or wrapper evidence but is not blocking static-validation evidence in #268.",
        },
    }
