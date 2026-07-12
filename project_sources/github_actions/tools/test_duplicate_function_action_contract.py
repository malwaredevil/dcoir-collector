#!/usr/bin/env python3
"""Validate the duplicate-function composite action's report/path contract."""
from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
ACTION_PATH = REPO_ROOT / ".github/actions/run-duplicate-function-check/action.yml"
SCRIPT_PATH = REPO_ROOT / ".github/actions/run-duplicate-function-check/Invoke-DcoirDuplicateFunctionCheck.ps1"
VALIDATE_ON_PR = REPO_ROOT / ".github/workflows/reusable-validate-on-pr.yml"
VALIDATE_ON_PUSH = REPO_ROOT / ".github/workflows/reusable-validate-on-push.yml"
TEST_PATH = "project_sources/github_actions/tools/test_duplicate_function_action_contract.py"


def normalize_report_path(path_value: str, expected_suffix: str) -> str:
    if not path_value or not path_value.strip():
        raise ValueError("output path is required")
    raw_normalized = path_value.replace("\\", "/")
    if re.search(r"[\x00-\x1f\x7f]", raw_normalized):
        raise ValueError("control character")
    normalized = raw_normalized.strip()
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise ValueError("repo-relative")
    if re.search(r"(^|/)\.\.($|/)", normalized):
        raise ValueError("traversal")
    if not normalized.startswith("project_sources/collector/"):
        raise ValueError("collector subtree")
    if not normalized.lower().endswith(expected_suffix.lower()):
        raise ValueError("suffix")
    return normalized


def markdown_table_cell(value: object | None) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"\r?\n", " ", text)
    text = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("|", "&#124;")
        .replace("`", "&#96;")
    )
    return text


def function_block(text: str, function_name: str) -> str:
    match = re.search(rf"function {re.escape(function_name)}\b", text)
    if not match:
        raise AssertionError(f"{function_name} function not found")
    start = match.start()
    open_brace = text.find("{", start)
    if open_brace < 0:
        raise AssertionError(f"{function_name} opening brace not found")
    depth = 0
    for index in range(open_brace, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"{function_name} function did not close")


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

    def test_path_guard_contract_accepts_only_collector_reports(self) -> None:
        self.assertEqual(
            normalize_report_path(
                "project_sources/collector/powershell_duplicate_function_report.json",
                ".json",
            ),
            "project_sources/collector/powershell_duplicate_function_report.json",
        )
        self.assertEqual(
            normalize_report_path(
                r"project_sources\collector\powershell_duplicate_function_report.md",
                ".md",
            ),
            "project_sources/collector/powershell_duplicate_function_report.md",
        )

        rejected = [
            ("", ".json"),
            ("/tmp/powershell_duplicate_function_report.json", ".json"),
            ("C:/tmp/powershell_duplicate_function_report.json", ".json"),
            ("project_sources/collector/../collector/powershell_duplicate_function_report.json", ".json"),
            ("project_sources/validation/powershell_duplicate_function_report.json", ".json"),
            ("project_sources/collector/powershell_duplicate_function_report.txt", ".json"),
            ("project_sources/collector/powershell_duplicate_function_report.json\nextra", ".json"),
            ("project_sources/collector/powershell_duplicate_function_report.json\x7f", ".json"),
        ]
        for path_value, suffix in rejected:
            with self.subTest(path_value=path_value):
                with self.assertRaises(ValueError):
                    normalize_report_path(path_value, suffix)

    def test_action_contains_required_path_guard_checks(self) -> None:
        block = function_block(self.script_text, "Resolve-CollectorReportPath")
        self.assertIn("$rawNormalized = $pathValue.Replace('\\', '/')", block)
        self.assertIn("$rawNormalized -match '[\\x00-\\x1F\\x7F]'", block)
        self.assertLess(
            block.index("$rawNormalized -match '[\\x00-\\x1F\\x7F]'"),
            block.index("$normalized = $rawNormalized.Trim()"),
        )
        self.assertIn("$normalized.StartsWith('/')", block)
        self.assertIn("$normalized -match '^[A-Za-z]:'", block)
        self.assertIn("$normalized -match '(^|/)\\.\\.($|/)'", block)
        self.assertIn("$normalized.StartsWith('project_sources/collector/'", block)
        self.assertIn("$normalized.EndsWith($expectedSuffix", block)
        self.assertIn("$resolved.StartsWith($repoRoot", block)
        self.assertIn("$jsonOutput.RelativePath -eq $markdownOutput.RelativePath", self.script_text)

    def test_markdown_cell_escaping_contract(self) -> None:
        escaped = markdown_table_cell("name`with|table\n<&>")
        self.assertEqual(escaped, "name&#96;with&#124;table &lt;&amp;&gt;")
        self.assertNotIn("`", escaped)
        self.assertNotIn("|", escaped)
        self.assertNotIn("\n", escaped)

        block = function_block(self.script_text, "ConvertTo-MarkdownTableCell")
        for expected in [
            "Replace('&', '&amp;')",
            "Replace('<', '&lt;')",
            "Replace('>', '&gt;')",
            "Replace('|', '&#124;')",
            "Replace('`', '&#96;')",
        ]:
            self.assertIn(expected, block)

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

    def test_validation_workflows_run_contract_test_before_action(self) -> None:
        for workflow in [VALIDATE_ON_PR, VALIDATE_ON_PUSH]:
            with self.subTest(workflow=workflow.name):
                text = workflow.read_text(encoding="utf-8")
                self.assertIn(TEST_PATH, text)
                self.assertLess(
                    text.index(TEST_PATH),
                    text.index("uses: ./.github/actions/run-duplicate-function-check"),
                )


if __name__ == "__main__":
    unittest.main()
