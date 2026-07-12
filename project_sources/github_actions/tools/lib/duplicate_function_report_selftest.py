"""Self-tests for the duplicate-function report validator."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from lib.duplicate_function_report_contract import (
    DEFAULT_JSON,
    DEFAULT_MARKDOWN,
    SCHEMA_VERSION,
    ValidationError,
    resolve_report_path,
    scoped_report_path,
    validate_reports,
)


def run_self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        json_path = scoped_report_path(root, DEFAULT_JSON, DEFAULT_JSON, "JSON report")
        markdown_path = scoped_report_path(root, DEFAULT_MARKDOWN, DEFAULT_MARKDOWN, "Markdown report")
        json_path.parent.mkdir(parents=True)
        report = {
            "schema_version": SCHEMA_VERSION,
            "validation": {"success": True, "errors": [], "warnings": []},
            "summary": {
                "file_count": 1,
                "function_name_count": 2,
                "duplicate_function_count": 0,
                "parse_failure_count": 0,
            },
            "duplicates": [],
            "parse_failures": [],
            "targets": ["project_sources/collector/source/DCOIR_Collector.ps1"],
            "artifact_contract": {
                "local_artifacts": {"json": DEFAULT_JSON.as_posix(), "markdown": DEFAULT_MARKDOWN.as_posix()},
                "workflow_behavior": "caller_uploaded_artifact",
                "retention_scope": "workflow-generated report artifacts uploaded by the caller workflow",
            },
        }
        json_path.write_text(json.dumps(report), encoding="utf-8")
        markdown_path.write_text(
            "\n".join(
                [
                    "# PowerShell Duplicate Function Report",
                    "",
                    "## Summary",
                    "",
                    "- Files scanned: 1",
                    "- Unique function names: 2",
                    "- Duplicate function names: 0",
                    "- Parse failures: 0",
                    "- Workflow behavior: `caller_uploaded_artifact`",
                    f"- JSON: `{DEFAULT_JSON.as_posix()}`",
                    f"- Markdown: `{DEFAULT_MARKDOWN.as_posix()}`",
                    "",
                    "## Duplicate Function Definitions",
                    "",
                    "No duplicate function definitions found.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        previous_cwd = Path.cwd()
        os.chdir(root)
        try:
            validate_reports(DEFAULT_JSON, DEFAULT_MARKDOWN)

            bad = dict(report)
            bad["schema_version"] = "wrong"
            json_path.write_text(json.dumps(bad), encoding="utf-8")
            try:
                validate_reports(DEFAULT_JSON, DEFAULT_MARKDOWN)
            except ValidationError:
                pass
            else:
                raise AssertionError("invalid schema self-test should fail")

            rejected_paths = (
                Path("../etc/passwd"),
                Path("../../../../tmp/evil.md"),
                Path("/tmp/evil.md"),
                Path("project_sources/collector/../validation/powershell_duplicate_function_report.json"),
                Path("project_sources/collector/not_the_report.json"),
                Path("project_sources/validation/powershell_duplicate_function_report.json"),
                Path("project_sources/collector/powershell_duplicate_function_report.json\nextra"),
            )
            for rejected_path in rejected_paths:
                try:
                    resolve_report_path(rejected_path, DEFAULT_JSON, "JSON report", root=root)
                except ValidationError:
                    pass
                else:
                    raise AssertionError(f"unsafe path self-test should fail: {rejected_path!s}")
        finally:
            os.chdir(previous_cwd)
