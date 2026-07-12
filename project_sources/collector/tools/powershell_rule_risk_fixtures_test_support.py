#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_powershell_rule_risk_fixtures as harness


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class RuleRiskFixtureTestCase(unittest.TestCase):
    def make_repo(
        self,
        *,
        bad_text: str = 'Write-Host "bad output"\n',
        control_text: str = 'Write-Output "good output"\n',
        expected_line: int = 1,
        matrix_fixtures: list[str] | None = None,
        duplicate_check: bool = False,
    ) -> tempfile.TemporaryDirectory[str]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        write(root / "project_sources/collector/fixtures/powershell_analysis/bad/write_host.ps1", bad_text)
        write(root / "project_sources/collector/fixtures/powershell_analysis/good/control.ps1", control_text)
        self.write_settings(root)
        fixtures = ["bad-write-host"] if matrix_fixtures is None else matrix_fixtures
        checks = [
            {
                "id": "pssa-avoid-write-host",
                "rule_name": "PSAvoidUsingWriteHost",
                "tool": "PSScriptAnalyzer",
                "check_source": "project_sources/collector/PSScriptAnalyzerSettings.psd1",
                "blocking": True,
                "expected_severity": "Warning",
                "risk_classes": ["review_assist_output_quality"],
                "target_surfaces": ["validation tooling"],
                "failure_impact": "Host-only output can disappear from durable reports.",
                "recommended_fix": "Use Write-Output or structured reporting.",
                "fixtures": fixtures,
                "promotion_criteria": "Already blocking in this test matrix.",
            }
        ]
        if duplicate_check:
            checks.append(dict(checks[0]))
        matrix = {
            "schema_version": harness.MATRIX_SCHEMA_VERSION,
            "issue": harness.ISSUE_NUMBER,
            "minimum_risk_classes": [],
            "checks": checks,
        }
        manifest = {
            "schema_version": harness.MANIFEST_SCHEMA_VERSION,
            "issue": harness.ISSUE_NUMBER,
            "matrix": harness.DEFAULT_MATRIX.as_posix(),
            "fixtures_root": harness.FIXTURE_ROOT.as_posix(),
            "fixtures": [
                {
                    "id": "bad-write-host",
                    "kind": "negative",
                    "path": "project_sources/collector/fixtures/powershell_analysis/bad/write_host.ps1",
                    "description": "Write-Host negative fixture.",
                    "expected_findings": [
                        {
                            "check_id": "pssa-avoid-write-host",
                            "rule_name": "PSAvoidUsingWriteHost",
                            "severity": "Warning",
                            "line": expected_line,
                            "risk_class": "review_assist_output_quality",
                        }
                    ],
                },
                {
                    "id": "good-control",
                    "kind": "control",
                    "path": "project_sources/collector/fixtures/powershell_analysis/good/control.ps1",
                    "description": "Clean control fixture.",
                    "expected_findings": [],
                },
            ],
        }
        write(root / harness.DEFAULT_MATRIX, json.dumps(matrix, indent=2) + "\n")
        write(root / harness.DEFAULT_MANIFEST, json.dumps(manifest, indent=2) + "\n")
        return temp

    def write_settings(self, root: Path) -> None:
        include_rules = "\n".join(f"        '{rule}'" for rule in sorted(harness.analyzer.REQUIRED_POLICY_RULES))
        rules = "\n".join(f"        {rule} = @{{}}" for rule in sorted(harness.analyzer.REQUIRED_POLICY_RULES))
        write(
            root / "project_sources/collector/PSScriptAnalyzerSettings.psd1",
            textwrap.dedent(
                f"""\
                # DCOIR_POLICY_ID: dcoir-powershell-analyzer-policy-v1
                # DCOIR_EXCLUSIONS: none
                @{{
                    Severity = @('Error', 'Warning')
                    IncludeRules = @(
{include_rules}
                    )
                    Rules = @{{
{rules}
                    }}
                }}
                """
            ),
        )

    def args(self, root: Path) -> argparse.Namespace:
        return argparse.Namespace(
            repo_root=str(root),
            matrix=harness.DEFAULT_MATRIX.as_posix(),
            manifest=harness.DEFAULT_MANIFEST.as_posix(),
            json_output=harness.DEFAULT_JSON_OUTPUT.as_posix(),
            markdown_output=harness.DEFAULT_MARKDOWN_OUTPUT.as_posix(),
            matrix_markdown_output=harness.DEFAULT_MATRIX_MARKDOWN_OUTPUT.as_posix(),
            timeout_seconds=10,
            no_write=True,
            skip_minimum_risk_class_check=True,
        )
