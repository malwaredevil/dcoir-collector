#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import textwrap
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_powershell_analyzer as analyzer


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def update_inventory_sha256(root: Path, rel: str, text: str) -> None:
    inventory_path = root / analyzer.DEFAULT_INVENTORY
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    for surface_record in inventory["surfaces"]:
        if surface_record["path"] == rel:
            surface_record["sha256"] = analyzer.sha256_text(text)
            break
    else:
        raise AssertionError(f"inventory test surface not found: {rel}")
    write(inventory_path, json.dumps(inventory, indent=2) + "\n")


def surface(
    path: str,
    category: str,
    source_type: str,
    decision: str = "include",
    sha256: str = "",
) -> dict[str, object]:
    return {
        "path": path,
        "category": category,
        "source_type": source_type,
        "status": "source" if decision == "include" else "workflow_embedded",
        "inclusion_decision": decision,
        "decision_reason": "test target" if decision == "include" else "reference surface",
        "exists": True,
        "marker_lines": [],
        "embedded_snippets": [],
        "size_bytes": 20,
        "line_count": 1,
        "sha256": sha256,
    }


class PowerShellAnalyzerTestCase(unittest.TestCase):
    def make_repo(self) -> tempfile.TemporaryDirectory[str]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        source_text = "Write-Output 'collector ok'\n"
        harness_text = "Write-Output 'harness ok'\n"
        workflow_text = (
            "jobs:\n"
            "  validate:\n"
            "    steps:\n"
            "      - shell: pwsh\n"
            "        run: Write-Host ok\n"
        )
        write(root / "project_sources/collector/source/DCOIR_Collector.ps1", source_text)
        write(root / "project_sources/collector/harness/run_DCOIR_Tests.ps1", harness_text)
        write(root / ".github/workflows/validate-on-pr.yml", workflow_text)
        write(
            root / "project_sources/collector/PSScriptAnalyzerSettings.psd1",
            textwrap.dedent(
                """\
                # DCOIR_POLICY_ID: dcoir-powershell-analyzer-policy-v1
                # DCOIR_EXCLUSIONS: none
                @{
                    Severity = @('Error', 'Warning')
                    IncludeRules = @(
                        'PSAvoidUsingPlainTextForPassword'
                        'PSAvoidUsingConvertToSecureStringWithPlainText'
                        'PSAvoidUsingInvokeExpression'
                        'PSAvoidUsingWriteHost'
                        'PSUseDeclaredVarsMoreThanAssignments'
                        'PSUseShouldProcessForStateChangingFunctions'
                    )
                    Rules = @{
                        PSAvoidUsingPlainTextForPassword = @{}
                        PSAvoidUsingConvertToSecureStringWithPlainText = @{}
                        PSAvoidUsingInvokeExpression = @{}
                        PSAvoidUsingWriteHost = @{}
                        PSUseDeclaredVarsMoreThanAssignments = @{}
                        PSUseShouldProcessForStateChangingFunctions = @{}
                    }
                }
                """
            ),
        )
        inventory = {
            "schema_version": analyzer.INVENTORY_SCHEMA_VERSION,
            "issue": 261,
            "summary": {"total_surfaces": 3},
            "validation": {"success": True, "errors": [], "warnings": []},
            "surfaces": [
                surface(
                    "project_sources/collector/source/DCOIR_Collector.ps1",
                    "collector_runtime_wrapper",
                    ".ps1",
                    sha256=analyzer.sha256_text(source_text),
                ),
                surface(
                    "project_sources/collector/harness/run_DCOIR_Tests.ps1",
                    "collector_harness_script",
                    ".ps1",
                    sha256=analyzer.sha256_text(harness_text),
                ),
                surface(
                    ".github/workflows/validate-on-pr.yml",
                    "workflow_embedded_powershell",
                    "workflow_yaml",
                    "reference",
                    sha256=analyzer.sha256_text(workflow_text),
                ),
            ],
        }
        write(root / "project_sources/collector/powershell_surface_inventory.json", json.dumps(inventory, indent=2) + "\n")
        write(
            root / "fake_analyzer.py",
            textwrap.dedent(
                """\
                import json
                import sys
                import time
                from pathlib import Path

                mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
                request = json.loads(sys.stdin.read())
                target = request["target"]
                if mode == "crash":
                    print("simulated crash", file=sys.stderr)
                    raise SystemExit(23)
                if mode == "invalid_json":
                    print("{not-json")
                    raise SystemExit(0)
                if mode == "timeout":
                    time.sleep(3)
                if mode == "skip":
                    print(json.dumps({
                        "analyzer_name": "FakePSScriptAnalyzer",
                        "analyzer_version": "1.0.0",
                        "powershell_engine": "Core",
                        "powershell_version": "7.4.1",
                        "target_path": target["path"],
                        "analyzed": False,
                        "skipped_reason": "simulated skip",
                        "findings": [],
                    }))
                    raise SystemExit(0)
                version = "2.0" if mode == "old_version" else "7.4.1"
                text = Path(target["analysis_path"]).read_text(encoding="utf-8")
                findings = []
                if mode != "no_findings" and "Write-Host" in text:
                    findings.append({
                        "path": target["analysis_path"],
                        "line": 1,
                        "column": 1,
                        "symbol": "",
                        "rule_name": "PSAvoidUsingWriteHost",
                        "severity": "Warning",
                        "observed_problem": "Write-Host makes analyzer output noisy and reviewer-hostile.",
                        "recommended_fix": "Use Write-Output or structured logging.",
                    })
                response = {
                    "analyzer_name": "FakePSScriptAnalyzer",
                    "analyzer_version": "1.0.0",
                    "powershell_engine": "Core",
                    "powershell_version": version,
                    "target_path": target["path"],
                    "analyzed": True,
                    "findings": findings,
                }
                if mode == "missing_analyzed":
                    response.pop("analyzed")
                if mode == "null_analyzed":
                    response["analyzed"] = None
                if mode == "string_analyzed":
                    response["analyzed"] = "true"
                if mode == "missing_target_path":
                    response.pop("target_path")
                print(json.dumps(response))
                """
            ),
        )
        return temp

    def make_args(self, root: Path, mode: str = "auto", **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "repo_root": str(root),
            "inventory": analyzer.DEFAULT_INVENTORY.as_posix(),
            "settings": analyzer.DEFAULT_SETTINGS.as_posix(),
            "json_output": analyzer.DEFAULT_JSON_OUTPUT.as_posix(),
            "markdown_output": analyzer.DEFAULT_MARKDOWN_OUTPUT.as_posix(),
            "analyzer_command": [sys.executable, str(root / "fake_analyzer.py"), mode],
            "target_path": [],
            "baseline_json": None,
            "timeout_seconds": 10,
            "minimum_powershell_version": "5.1",
            "fail_on_severity": "Warning",
            "allow_findings": False,
            "expect_finding_rule": None,
            "expect_finding_path": None,
            "expect_no_findings": False,
            "no_write": False,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def required_include_rules_block(self, indent: str = "        ") -> str:
        return "\n".join(f"{indent}'{rule}'" for rule in sorted(analyzer.REQUIRED_POLICY_RULES))

    def required_rule_keys_block(self, indent: str = "        ") -> str:
        return "\n".join(f"{indent}{rule} = @{{}}" for rule in sorted(analyzer.REQUIRED_POLICY_RULES))



__all__ = [
    "PowerShellAnalyzerTestCase",
    "analyzer",
    "surface",
    "update_inventory_sha256",
    "write",
]
