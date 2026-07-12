#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_powershell_engine_pester_boundary as boundary
import run_powershell_finding_governance as governance


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def boundary_matrix_row(check_category: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": check_category,
        "check_category": check_category,
        "required_engine": "python-3.12",
        "runner_os": "any",
        "module_or_tool_dependency": "standard-library",
        "evidence_type": "json-report",
        "output_artifact": f"artifact/{check_category}.json",
        "blocking": True,
        "owner": "#267-test",
        "boundary": "test boundary",
    }
    row.update(overrides)
    return row


def boundary_doc() -> dict[str, object]:
    rows = [boundary_matrix_row(category) for category in sorted(boundary.REQUIRED_CHECK_CATEGORIES)]
    for row in rows:
        if row["check_category"] == "windows_powershell_51_parser_runtime_compatibility":
            row["required_engine"] = "Windows PowerShell 5.1 Desktop"
            row["runner_os"] = "windows-latest"
        if row["check_category"] == "powershell_7_static_analyzer":
            row["required_engine"] = "PowerShell 7 Core"
            row["module_or_tool_dependency"] = "PSScriptAnalyzer"
        if row["check_category"] == "pester_supporting_tests":
            row["required_engine"] = "PowerShell 7 Core or Windows PowerShell 5.1 Desktop as declared by the owning test"
            row["runner_os"] = "windows-latest when Windows PowerShell 5.1 behavior is asserted; otherwise any runner with declared engine"
            row["module_or_tool_dependency"] = "Pester"
            row["blocking"] = False
    return {
        "schema_version": boundary.BOUNDARY_SCHEMA_VERSION,
        "issue": boundary.ISSUE_NUMBER,
        "parent_issue": boundary.PARENT_ISSUE_NUMBER,
        "policy": {
            "workflow_readiness_claimed": False,
            "pester_may_replace_analyzer_or_custom_checks": False,
            "engine_evidence_must_be_separate": True,
            "independent_analyzer_enforcement_required": True,
        },
        "engine_matrix": rows,
        "pester_boundary": {
            "scope_decision": "supporting-in-scope-not-analyzer-substitute",
            "blocking_for_static_security_validation": False,
            "must_not_replace": [
                "#262 analyzer wrapper enforcement",
                "#264 DCOIR custom checks",
            ],
            "required_evidence_when_used": sorted(boundary.PESTER_EVIDENCE_FIELDS),
            "owned_responsibilities": [
                {
                    "surface": "wrapper tests",
                    "owner": "future gate",
                    "blocking": False,
                    "notes": "test responsibility",
                }
            ],
        },
        "independent_analyzer_enforcement_proof": {
            "requires_pester": False,
            "source_reports": [
                boundary.DEFAULT_RULE_RISK_REPORT.as_posix(),
                boundary.DEFAULT_CUSTOM_REPORT.as_posix(),
                boundary.DEFAULT_GOVERNANCE_REPORT.as_posix(),
            ],
            "required_conditions": ["proof exists"],
        },
    }


def write_boundary_reports(root: Path) -> None:
    write(
        root / boundary.DEFAULT_RULE_RISK_REPORT,
        json.dumps(
            {
                "schema_version": "dcoir_powershell_rule_risk_fixture_report_v1",
                "validation": {"success": True, "errors": [], "warnings": []},
                "summary": {"observed_finding_count": 1, "finding_count": 1},
            },
            indent=2,
        )
        + "\n",
    )
    write(
        root / boundary.DEFAULT_CUSTOM_REPORT,
        json.dumps(
            {
                "schema_version": "dcoir_powershell_custom_check_report_v1",
                "validation": {"success": True, "errors": [], "warnings": []},
                "summary": {"finding_count": 1},
            },
            indent=2,
        )
        + "\n",
    )
    write(
        root / boundary.DEFAULT_GOVERNANCE_REPORT,
        json.dumps(
            {
                "schema_version": "dcoir_powershell_finding_governance_report_v1",
                "validation": {"success": True, "errors": [], "warnings": []},
                "summary": {
                    "classified_finding_count": 2,
                    "unclassified_finding_count": 0,
                    "finding_count": 2,
                },
            },
            indent=2,
        )
        + "\n",
    )
    write(
        root / boundary.DEFAULT_ASSEMBLY_REPORT,
        json.dumps(
            {
                "schema_version": "dcoir_powershell_assembly_parity_report_v1",
                "validation": {"success": True, "errors": [], "warnings": []},
                "summary": {"finding_count": 0},
            },
            indent=2,
        )
        + "\n",
    )


def boundary_args(root: Path, extra_report: list[str] | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        repo_root=str(root),
        boundary=boundary.DEFAULT_BOUNDARY.as_posix(),
        json_output=boundary.DEFAULT_JSON_OUTPUT.as_posix(),
        markdown_output=boundary.DEFAULT_MARKDOWN_OUTPUT.as_posix(),
        extra_report=extra_report or [boundary.DEFAULT_ASSEMBLY_REPORT.as_posix()],
        no_write=True,
    )


def finding(path: str = "project_sources/collector/fixtures/powershell_analysis/bad/example.ps1") -> dict[str, object]:
    return {
        "path": path,
        "line": 1,
        "column": 1,
        "rule_name": "DCOIR.Example",
        "check_id": "dcoir-example",
        "severity": "Error",
        "observed_problem": "Example problem.",
        "recommended_fix": "Fix the example problem.",
        "fingerprint": "finding-fingerprint-1",
    }


def baseline_record(path: str) -> dict[str, object]:
    return {
        "id": "unsafe-baseline",
        "decision": "baseline-temporary",
        "path": path,
        "line": 1,
        "rule_name": "DCOIR.Example",
        "severity": "Error",
        "fingerprint": "finding-fingerprint-1",
        "rationale": "Regression test baseline.",
        "owner": "DCOIR Collector maintainers",
        "reviewer": "DCOIR operator",
        "review_date": "2026-06-10",
        "revisit_condition": "Before workflow gating.",
        "expected_match_count": 1,
    }


def suppression_record(path: str) -> dict[str, object]:
    return {
        "id": "unsafe-suppression",
        "decision": "accepted risk",
        "path": path,
        "rule_name": "DCOIR.Example",
        "scope": "file",
        "fingerprint": "finding-fingerprint-1",
        "rationale": "Regression test suppression.",
        "owner": "DCOIR Collector maintainers",
        "reviewer": "DCOIR operator",
        "review_date": "2026-06-10",
        "revisit_condition": "Before workflow gating.",
        "expected_match_count": 1,
    }


def write_governance_repo(
    root: Path,
    *,
    assembly_success: bool = True,
    assembly_generated_path: str = "compiled_runtime/DCOIR_Collector.ps1",
    finding_path: str = "project_sources/collector/fixtures/powershell_analysis/bad/example.ps1",
    classification_path_prefixes: list[str] | None = None,
    classification_paths: list[str] | None = None,
    baseline_path: str | None = None,
    suppression_path: str | None = None,
) -> None:
    finding_report = {
        "schema_version": "dcoir_powershell_custom_check_report_v1",
        "findings": [finding(finding_path)],
        "validation": {"success": True, "errors": [], "warnings": []},
        "summary": {"finding_count": 1},
    }
    rule_risk_report = {
        "schema_version": "dcoir_powershell_rule_risk_fixture_report_v1",
        "findings": [],
        "validation": {"success": True, "errors": [], "warnings": []},
        "summary": {"finding_count": 0},
    }
    analyzer_report = {
        "schema_version": "dcoir_powershell_analyzer_report_v1",
        "findings": [],
        "validation": {"success": True, "errors": [], "warnings": []},
        "summary": {"finding_count": 0},
    }
    assembly_report = {
        "schema_version": "dcoir_powershell_assembly_parity_report_v1",
        "validation": {"success": assembly_success, "errors": [] if assembly_success else ["failed upstream"], "warnings": []},
        "generated_outputs": [
            {"id": "collector_compiled_runtime", "path": assembly_generated_path}
        ],
    }
    classification_rule: dict[str, object] = {
        "id": "fixture-findings",
        "decision": "advisory",
        "rationale": "Fixtures are advisory control evidence.",
        "owner": "DCOIR Collector maintainers",
        "reviewer": "DCOIR operator",
        "review_date": "2026-06-10",
        "revisit_condition": "Before workflow gating.",
    }
    if classification_path_prefixes is None:
        classification_rule["path_prefixes"] = ["project_sources/collector/fixtures/powershell_analysis/"]
    else:
        classification_rule["path_prefixes"] = classification_path_prefixes
    if classification_paths is not None:
        classification_rule["paths"] = classification_paths
    governance_doc = {
        "schema_version": governance.GOVERNANCE_SCHEMA_VERSION,
        "issue": governance.ISSUE_NUMBER,
        "policy": {
            "allowed_decisions": sorted(governance.ALLOWED_DECISIONS),
            "max_baseline_records": 10,
        },
        "classification_rules": [classification_rule],
        "baseline_records": [baseline_record(baseline_path)] if baseline_path is not None else [],
        "suppressions": [suppression_record(suppression_path)] if suppression_path is not None else [],
        "approved_delta_exceptions": [],
        "control_proofs": [],
    }
    write(root / governance.DEFAULT_CUSTOM_REPORT, json.dumps(finding_report, indent=2) + "\n")
    write(root / governance.DEFAULT_RULE_RISK_REPORT, json.dumps(rule_risk_report, indent=2) + "\n")
    write(root / governance.DEFAULT_ANALYZER_REPORT, json.dumps(analyzer_report, indent=2) + "\n")
    write(root / governance.DEFAULT_ASSEMBLY_PARITY_REPORT, json.dumps(assembly_report, indent=2) + "\n")
    write(root / governance.DEFAULT_GOVERNANCE, json.dumps(governance_doc, indent=2) + "\n")


def governance_args(root: Path, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "repo_root": str(root),
        "governance": governance.DEFAULT_GOVERNANCE.as_posix(),
        "finding_report": [],
        "optional_finding_report": [],
        "assembly_parity_report": governance.DEFAULT_ASSEMBLY_PARITY_REPORT.as_posix(),
        "json_output": governance.DEFAULT_JSON_OUTPUT.as_posix(),
        "markdown_output": governance.DEFAULT_MARKDOWN_OUTPUT.as_posix(),
        "as_of_date": "2026-06-10",
        "allow_missing_analyzer_report": False,
        "no_write": True,
    }
    values.update(overrides)
    return argparse.Namespace(**values)
