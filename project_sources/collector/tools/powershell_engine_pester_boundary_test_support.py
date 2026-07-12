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


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def matrix_row(check_category: str, **overrides: object) -> dict[str, object]:
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


def good_boundary_doc() -> dict[str, object]:
    rows = [matrix_row(category) for category in sorted(boundary.REQUIRED_CHECK_CATEGORIES)]
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


def write_reports(root: Path, *, custom_findings: int = 1, rule_findings: int = 1, unclassified: int = 0) -> None:
    write(
        root / boundary.DEFAULT_RULE_RISK_REPORT,
        json.dumps(
            {
                "schema_version": "dcoir_powershell_rule_risk_fixture_report_v1",
                "validation": {"success": True, "errors": [], "warnings": []},
                "summary": {"observed_finding_count": rule_findings, "finding_count": rule_findings},
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
                "summary": {"finding_count": custom_findings},
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
                    "classified_finding_count": custom_findings + rule_findings,
                    "unclassified_finding_count": unclassified,
                    "finding_count": custom_findings + rule_findings,
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


class EngineBoundaryTestBase(unittest.TestCase):
    def make_repo(self, doc: dict[str, object] | None = None, **report_overrides: int) -> tempfile.TemporaryDirectory[str]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        write(root / boundary.DEFAULT_BOUNDARY, json.dumps(doc or good_boundary_doc(), indent=2) + "\n")
        write_reports(root, **report_overrides)
        return temp

    def args(self, root: Path, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "repo_root": str(root),
            "boundary": boundary.DEFAULT_BOUNDARY.as_posix(),
            "json_output": boundary.DEFAULT_JSON_OUTPUT.as_posix(),
            "markdown_output": boundary.DEFAULT_MARKDOWN_OUTPUT.as_posix(),
            "extra_report": [boundary.DEFAULT_ASSEMBLY_REPORT.as_posix()],
            "no_write": True,
        }
        values.update(overrides)
        return argparse.Namespace(**values)
