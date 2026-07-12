#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_powershell_finding_governance as governance


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def finding(
    *,
    path: str = "project_sources/collector/fixtures/powershell_analysis/bad/example.ps1",
    rule_name: str = "DCOIR.Example",
    check_id: str = "dcoir-example",
    severity: str = "Error",
    fingerprint: str = "finding-fingerprint-1",
) -> dict[str, object]:
    return {
        "path": path,
        "line": 1,
        "column": 1,
        "rule_name": rule_name,
        "check_id": check_id,
        "severity": severity,
        "observed_problem": "Example problem.",
        "recommended_fix": "Fix the example problem.",
        "fingerprint": fingerprint,
    }


def baseline_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "id": "baseline-example-1",
        "decision": "baseline-temporary",
        "path": "project_sources/collector/source/parts/DCOIR_Collector.01_Core.ps1",
        "line": 10,
        "rule_name": "DCOIR.Example",
        "severity": "Error",
        "fingerprint": "finding-fingerprint-1",
        "rationale": "Temporary baseline pending remediation.",
        "owner": "DCOIR Collector maintainers",
        "reviewer": "DCOIR operator",
        "review_date": "2026-06-10",
        "expires_on": "2026-12-31",
        "expected_match_count": 1,
    }
    record.update(overrides)
    return record


def suppression_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "id": "suppression-example-1",
        "decision": "accepted risk",
        "path": "project_sources/collector/source/parts/DCOIR_Collector.01_Core.ps1",
        "line": 10,
        "scope": "line",
        "rule_name": "DCOIR.Example",
        "severity": "Error",
        "fingerprint": "finding-fingerprint-1",
        "rationale": "Reviewed local suppression.",
        "owner": "DCOIR Collector maintainers",
        "reviewer": "DCOIR operator",
        "review_date": "2026-06-10",
        "expires_on": "2026-12-31",
        "expected_match_count": 1,
    }
    record.update(overrides)
    return record


class FindingGovernanceTestBase(unittest.TestCase):
    def make_repo(
        self,
        *,
        report_findings: list[dict[str, object]] | None = None,
        governance_overrides: dict[str, object] | None = None,
        write_analyzer_report: bool = True,
    ) -> tempfile.TemporaryDirectory[str]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        finding_report = {
            "schema_version": "dcoir_powershell_custom_check_report_v1",
            "findings": report_findings if report_findings is not None else [finding()],
            "validation": {"success": True, "errors": [], "warnings": []},
            "summary": {"finding_count": len(report_findings if report_findings is not None else [finding()])},
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
            "validation": {"success": True, "errors": [], "warnings": []},
            "generated_outputs": [
                {"id": "collector_compiled_runtime", "path": "compiled_runtime/DCOIR_Collector.ps1"}
            ],
        }
        governance_doc: dict[str, object] = {
            "schema_version": governance.GOVERNANCE_SCHEMA_VERSION,
            "issue": governance.ISSUE_NUMBER,
            "policy": {
                "allowed_decisions": sorted(governance.ALLOWED_DECISIONS),
                "max_baseline_records": 10,
            },
            "classification_rules": [
                {
                    "id": "fixture-findings",
                    "decision": "advisory",
                    "path_prefixes": ["project_sources/collector/fixtures/powershell_analysis/"],
                    "rationale": "Fixtures are advisory control evidence.",
                    "owner": "DCOIR Collector maintainers",
                    "reviewer": "DCOIR operator",
                    "review_date": "2026-06-10",
                    "revisit_condition": "Before workflow gating.",
                }
            ],
            "baseline_records": [],
            "suppressions": [],
            "approved_delta_exceptions": [],
            "control_proofs": [],
        }
        if governance_overrides:
            governance_doc.update(governance_overrides)
        write(root / governance.DEFAULT_CUSTOM_REPORT, json.dumps(finding_report, indent=2) + "\n")
        write(root / governance.DEFAULT_RULE_RISK_REPORT, json.dumps(rule_risk_report, indent=2) + "\n")
        if write_analyzer_report:
            write(root / governance.DEFAULT_ANALYZER_REPORT, json.dumps(analyzer_report, indent=2) + "\n")
        write(root / governance.DEFAULT_ASSEMBLY_PARITY_REPORT, json.dumps(assembly_report, indent=2) + "\n")
        write(root / governance.DEFAULT_GOVERNANCE, json.dumps(governance_doc, indent=2) + "\n")
        return temp

    def args(self, root: Path, **overrides: object) -> argparse.Namespace:
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
