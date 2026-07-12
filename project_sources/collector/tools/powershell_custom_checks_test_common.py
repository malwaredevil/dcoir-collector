#!/usr/bin/env python3
"""Shared fixtures for PowerShell custom-check runner tests."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_powershell_custom_checks as custom

def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def surface(path: str) -> dict[str, object]:
    return {
        "path": path,
        "category": "fixture_or_example",
        "source_type": ".ps1",
        "status": "fixture",
        "inclusion_decision": "include",
        "decision_reason": "test fixture",
        "exists": True,
        "marker_lines": [],
        "embedded_snippets": [],
        "size_bytes": 20,
        "line_count": 1,
        "sha256": "",
    }


def check_def(check_id: str, rule_name: str, risk_class: str) -> dict[str, object]:
    return {
        "id": check_id,
        "rule_name": rule_name,
        "matrix_check_id": check_id,
        "expected_severity": "Error",
        "risk_classes": [risk_class],
        "target_surfaces": ["validation tooling"],
        "intent": "Local fail-closed evidence must be tied to the risky row.",
        "failure_impact": "Unrelated failure handling can hide unsafe validation output.",
        "recommended_fix": "Fail the same local path that emits unsafe validation evidence.",
    }


class PowerShellCustomCheckCase(unittest.TestCase):
    def make_repo(
        self,
        *,
        bad_text: str = '$Rows += [pscustomobject]@{ Check = "Fixture"; Status = "FAIL" }\n',
        good_text: str = '$Rows += [pscustomobject]@{ Check = "Fixture"; Status = "FAIL" }\nthrow "failed"\n',
        expected_line: int = 1,
        matrix_rule_name: str = "DCOIR.FailOutputMustFailValidation",
        omit_good_from_inventory: bool = False,
    ) -> tempfile.TemporaryDirectory[str]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        bad_path = "project_sources/collector/fixtures/powershell_analysis/bad/fail_row_green_exit.ps1"
        good_path = "project_sources/collector/fixtures/powershell_analysis/good/custom_fail_row_fails_command.ps1"
        write(root / bad_path, bad_text)
        write(root / good_path, good_text)
        matrix = {
            "schema_version": custom.MATRIX_SCHEMA_VERSION,
            "issue": 263,
            "checks": [
                {
                    "id": "dcoir-fail-output-must-fail",
                    "rule_name": matrix_rule_name,
                    "blocking": True,
                    "expected_severity": "Error",
                    "risk_classes": ["fail_rows_reports_or_fixture_outputs_not_causing_failure"],
                }
            ],
        }
        checks = {
            "schema_version": custom.CHECKS_SCHEMA_VERSION,
            "issue": custom.ISSUE_NUMBER,
            "checks": [
                {
                    "id": "dcoir-fail-output-must-fail",
                    "rule_name": "DCOIR.FailOutputMustFailValidation",
                    "matrix_check_id": "dcoir-fail-output-must-fail",
                    "expected_severity": "Error",
                    "risk_classes": ["fail_rows_reports_or_fixture_outputs_not_causing_failure"],
                    "target_surfaces": ["validation tooling"],
                    "intent": "FAIL rows must fail the command.",
                    "target": "Validation report scripts.",
                    "detection": "Find FAIL rows without a fail-closed path.",
                    "limitations": "Fixture-level static detection only.",
                    "false_positive_controls": ["Allows throw or nonzero exit."],
                    "failure_impact": "A FAIL report can exit green.",
                    "recommended_fix": "Throw or exit nonzero when FAIL rows are emitted.",
                }
            ],
        }
        manifest = {
            "schema_version": custom.FIXTURE_MANIFEST_SCHEMA_VERSION,
            "issue": custom.ISSUE_NUMBER,
            "fixtures": [
                {
                    "id": "bad-fail-row-green-exit",
                    "kind": "negative",
                    "check_id": "dcoir-fail-output-must-fail",
                    "path": bad_path,
                    "description": "Bad fixture.",
                    "expected_findings": [
                        {
                            "check_id": "dcoir-fail-output-must-fail",
                            "rule_name": "DCOIR.FailOutputMustFailValidation",
                            "severity": "Error",
                            "line": expected_line,
                            "risk_class": "fail_rows_reports_or_fixture_outputs_not_causing_failure",
                        }
                    ],
                },
                {
                    "id": "good-fail-row-fails-command",
                    "kind": "control",
                    "check_id": "dcoir-fail-output-must-fail",
                    "path": good_path,
                    "description": "Good fixture.",
                    "expected_findings": [],
                },
            ],
        }
        surfaces = [surface(bad_path)]
        if not omit_good_from_inventory:
            surfaces.append(surface(good_path))
        inventory = {
            "schema_version": custom.INVENTORY_SCHEMA_VERSION,
            "issue": 261,
            "summary": {"total_surfaces": len(surfaces)},
            "validation": {"success": True, "errors": [], "warnings": []},
            "surfaces": surfaces,
        }
        write(root / custom.DEFAULT_MATRIX, json.dumps(matrix, indent=2) + "\n")
        write(root / custom.DEFAULT_CHECKS, json.dumps(checks, indent=2) + "\n")
        write(root / custom.DEFAULT_FIXTURE_MANIFEST, json.dumps(manifest, indent=2) + "\n")
        write(root / custom.DEFAULT_INVENTORY, json.dumps(inventory, indent=2) + "\n")
        return temp

    def args(self, root: Path, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "repo_root": str(root),
            "checks": custom.DEFAULT_CHECKS.as_posix(),
            "matrix": custom.DEFAULT_MATRIX.as_posix(),
            "inventory": custom.DEFAULT_INVENTORY.as_posix(),
            "fixture_manifest": custom.DEFAULT_FIXTURE_MANIFEST.as_posix(),
            "json_output": custom.DEFAULT_JSON_OUTPUT.as_posix(),
            "markdown_output": custom.DEFAULT_MARKDOWN_OUTPUT.as_posix(),
            "target_scope": "fixtures",
            "target_path": [],
            "fail_on_severity": "Warning",
            "allow_findings": False,
            "no_write": True,
        }
        values.update(overrides)
        return argparse.Namespace(**values)
