#!/usr/bin/env python3
"""Validate the duplicate-function composite action's report/path contract."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
ACTION_PATH = REPO_ROOT / ".github/actions/run-duplicate-function-check/action.yml"
SCRIPT_PATH = REPO_ROOT / ".github/actions/run-duplicate-function-check/Invoke-DcoirDuplicateFunctionCheck.ps1"
VALIDATE_ON_PR = REPO_ROOT / ".github/workflows/reusable-validate-on-pr.yml"
VALIDATE_ON_PUSH = REPO_ROOT / ".github/workflows/reusable-validate-on-push.yml"
TEST_PATH = ".github/github_actions/tools/test_duplicate_function_action_contract.py"
NATIVE_TEST = REPO_ROOT / ".github/scripts/Test-DuplicateFunctionCheckPaths.ps1"
HELPER_PATH = SCRIPT_PATH.with_name("DuplicateFunctionCheck.Paths.ps1")
PASS_RECORD = "DCOIR_DUPLICATE_PATH_TEST_PASS positive=12 rejected=54 markdown=9"


def run_native_contract() -> str:
    for path in (HELPER_PATH, NATIVE_TEST):
        if not path.is_file():
            raise AssertionError(f"Missing native contract surface: {path}")
    exe = shutil.which("pwsh")
    if not exe:
        raise AssertionError("pwsh is required for Windows native contract tests")
    result = subprocess.run(
        [exe, "-NoProfile", "-NonInteractive", "-File", str(NATIVE_TEST)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120, check=False,
    )
    if result.returncode:
        raise AssertionError(f"Native contract failed ({result.returncode}): {result.stdout}\n{result.stderr}")
    records = [line for line in result.stdout.splitlines()
               if line.lstrip().startswith("DCOIR_DUPLICATE_PATH_TEST_PASS")]
    if records != [PASS_RECORD]:
        raise AssertionError(f"Missing or invalid native evidence: {result.stdout}\n{result.stderr}")
    return result.stdout


class DuplicateFunctionActionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.action_text = ACTION_PATH.read_text(encoding="utf-8")
        cls.script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    def test_action_dispatches_to_repo_local_script(self) -> None:
        self.assertIn("DCOIR_ACTION_SCRIPT: ${{ github.action_path }}/Invoke-DcoirDuplicateFunctionCheck.ps1", self.action_text)
        self.assertIn("& $env:DCOIR_ACTION_SCRIPT", self.action_text)

    def test_action_defaults_use_collector_report_paths(self) -> None:
        self.assertIn(
            "default: project_sources/collector/powershell_duplicate_function_report.json",
            self.action_text,
        )
        self.assertIn(
            "default: project_sources/collector/powershell_duplicate_function_report.md",
            self.action_text,
        )


    def test_report_schema_markers_are_present(self) -> None:
        for marker in [
            "dcoir_powershell_duplicate_function_report_v1",
            "validation        = [ordered]@{",
            "summary           = [ordered]@{",
            "duplicate_function_count",
            "parse_failure_count",
            "duplicates        = @($duplicateRecords)",
            "parse_failures    = @($parseFailureRecords)",
            "artifact_contract = [ordered]@{",
            "workflow_behavior = 'caller_uploaded_artifact'",
            "$markdownLines.Add('- Workflow behavior: `caller_uploaded_artifact`')",
            "$markdownLines.Add('- JSON: `' + $jsonOutput.RelativePath + '`')",
            "$markdownLines.Add('- Markdown: `' + $markdownOutput.RelativePath + '`')",
        ]:
            self.assertIn(marker, self.script_text)

    def test_duplicate_function_discovery_is_shared_with_syntax(self) -> None:
        # Both shipped consumers must use the AST-backed scan set, not independent globs.
        helper = REPO_ROOT / ".github/scripts/Get-CollectorSourcePartFiles.ps1"
        self.assertTrue(helper.is_file(), "Shared helper is missing")
        self.assertIn("function Get-CollectorSourcePartFiles", helper.read_text(encoding="utf-8"))
        self.assertIn(".github/scripts/Get-CollectorSourcePartFiles.ps1", self.script_text)
        self.assertIn("-ForValidation", self.script_text)
        self.assertNotIn("Get-ChildItem -LiteralPath $partsDir", self.script_text)

    def test_syntax_discovery_uses_the_same_shared_scan_set(self) -> None:
        syntax_text = (REPO_ROOT / ".github/actions/validate-powershell-syntax/action.yml").read_text(encoding="utf-8")
        self.assertIn(".github/scripts/Get-CollectorSourcePartFiles.ps1", syntax_text)
        self.assertIn("-ForValidation", syntax_text)
        self.assertNotIn(
            "$psFiles += Get-ChildItem -LiteralPath 'project_sources/collector/source/parts'",
            syntax_text,
        )
        self.assertNotIn("INCLUDE_COLLECTOR_PARTS -eq 'true' -and (Test-Path", syntax_text)

    def test_validation_workflows_run_contract_test_before_action(self) -> None:
        for workflow in [VALIDATE_ON_PR, VALIDATE_ON_PUSH]:
            with self.subTest(workflow=workflow.name):
                text = workflow.read_text(encoding="utf-8")
                self.assertIn(TEST_PATH, text)
                self.assertLess(
                    text.index(TEST_PATH),
                    text.index("uses: ./.github/actions/run-duplicate-function-check"),
                )


    def test_public_path_functions_have_one_shipped_owner(self) -> None:
        helper_text = HELPER_PATH.read_text(encoding="utf-8")
        for name in ("Resolve-CollectorReportPath", "ConvertTo-MarkdownTableCell"):
            with self.subTest(name=name):
                pattern = rf"(?im)^\s*function\s+{re.escape(name)}\b"
                self.assertEqual(len(re.findall(pattern, helper_text)), 1)
                self.assertEqual(len(re.findall(pattern, self.script_text)), 0)

    def test_action_loads_helper_before_initial_validation(self) -> None:
        dispatch = ". (Join-Path -Path $PSScriptRoot -ChildPath 'DuplicateFunctionCheck.Paths.ps1')"
        self.assertEqual(self.script_text.count(dispatch), 1)
        self.assertLess(self.script_text.index("$repoRoot ="), self.script_text.index(dispatch))
        for name in ("json", "markdown"):
            self.assertLess(self.script_text.index(dispatch), self.script_text.index(f"${name}Output = Resolve-CollectorReportPath "))

    def test_action_validates_both_outputs_before_report_writes(self) -> None:
        scan = self.script_text.index("$sourceFiles =")
        first_write = self.script_text.index("Set-Content -LiteralPath")
        for name in ("json", "markdown"):
            self.assertLess(self.script_text.index(f"${name}Output = Resolve-CollectorReportPath "), scan)
        distinct = self.script_text.index("$jsonOutput.RelativePath -eq $markdownOutput.RelativePath")
        self.assertLess(distinct, scan)
        self.assertLess(scan, first_write)


class NativeDriverContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(callable(globals().get("run_native_contract")), "Missing native driver implementation")

    def test_missing_surface(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            absent = Path(directory) / "missing.ps1"
            for field in ("HELPER_PATH", "NATIVE_TEST"):
                with self.subTest(field=field), patch.object(sys.modules[__name__], field, absent), patch("subprocess.run") as child:
                    with self.assertRaisesRegex(AssertionError, "Missing native contract surface"):
                        run_native_contract()
                    child.assert_not_called()

    def test_missing_executable(self) -> None:
        with patch("shutil.which", return_value=None), patch("subprocess.run") as child:
            with self.assertRaisesRegex(AssertionError, "pwsh is required"):
                run_native_contract()
            child.assert_not_called()

    def test_native_result_contract(self) -> None:
        cases = (
            (1, PASS_RECORD),
            (0, ""),
            (0, PASS_RECORD.replace("positive=12", "positive=0")),
            (0, PASS_RECORD.replace("rejected=54", "rejected=53")),
            (0, PASS_RECORD.replace("markdown=9", "markdown=0")),
            (0, PASS_RECORD + " extra"),
            (0, " " + PASS_RECORD),
            (0, PASS_RECORD + "\n" + PASS_RECORD),
            (0, PASS_RECORD + "\n " + PASS_RECORD),
            (0, PASS_RECORD + "\nDCOIR_DUPLICATE_PATH_TEST_PASS malformed"),
        )
        for code, output in cases:
            with self.subTest(code=code, output=output):
                result = subprocess.CompletedProcess([], code, output, "")
                with patch("shutil.which", return_value="pwsh"), patch("subprocess.run", return_value=result):
                    with self.assertRaises(AssertionError):
                        run_native_contract()

    def test_native_timeout_is_failure(self) -> None:
        with patch("shutil.which", return_value="pwsh"), patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pwsh", 120)):
            with self.assertRaises(subprocess.TimeoutExpired):
                run_native_contract()

    def test_exact_child_invocation(self) -> None:
        output = "native fixture evidence\n" + PASS_RECORD + "\n"
        result = subprocess.CompletedProcess([], 0, output, "")
        with patch("shutil.which", return_value="pwsh"), patch("subprocess.run", return_value=result) as child:
            self.assertEqual(run_native_contract(), output)
            child.assert_called_once_with(
                ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(NATIVE_TEST)],
                cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=120, check=False,
            )


class NativeWindowsBehaviorTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows native behavior not executed on this platform")
    def test_shipped_powershell_behavior(self):
        print(run_native_contract(), end="", flush=True)


if __name__ == "__main__":
    unittest.main()
