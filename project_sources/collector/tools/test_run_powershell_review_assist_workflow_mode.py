#!/usr/bin/env python3
"""Slice 6: compare complete native workflow report bytes against the exact legacy wrapper."""
from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
REPO_ROOT = TOOLS.parents[2]
sys.path.insert(0, str(TOOLS))
import run_powershell_review_assist_report as review
import powershell_review_assist_builder as builder

FIXED_TIME = datetime(2026, 11, 24, 8, 0, 0, tzinfo=timezone.utc)
TARGET_JSON = "project_sources/collector/.slice6_workflow.json"
TARGET_MARKDOWN = "project_sources/collector/.slice6_workflow.md"
SOURCE_JSON = "project_sources/collector/.slice6_legacy_source.json"
SOURCE_MARKDOWN = "project_sources/collector/.slice6_legacy_source.md"
LEGACY_WRAPPER = (
    REPO_ROOT / "project_sources/collector/fixtures/powershell_review_assist/"
    "issue608_slice6_legacy_wrapper.py"
)
INPUT_PATHS = (
    review.DEFAULT_SCHEMA_PATH,
    review.DEFAULT_SURFACE_INVENTORY,
    review.DEFAULT_RULE_RISK_REPORT,
    review.DEFAULT_RULE_RISK_MATRIX,
    review.DEFAULT_CUSTOM_REPORT,
    review.DEFAULT_ASSEMBLY_PARITY_REPORT,
    review.DEFAULT_GOVERNANCE_REPORT,
    review.DEFAULT_ENGINE_BOUNDARY_REPORT,
    review.DEFAULT_FUNCTION_REACHABILITY_REPORT,
)


class FrozenDatetime:
    @staticmethod
    def now(tz=None):
        return FIXED_TIME.astimezone(tz or timezone.utc)


@contextlib.contextmanager
def changed_directory(directory: Path):
    previous = Path.cwd()
    try:
        os.chdir(directory)
        yield
    finally:
        os.chdir(previous)


class NativeWorkflowModeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for item in INPUT_PATHS:
            src = REPO_ROOT / item
            dest = self.root / item
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        # Legacy wrapper imports the CLI by repo-relative CWD. The tool modules
        # are resolved from the already imported canonical tools package.
        legacy_cli = self.root / "project_sources/collector/tools/run_powershell_review_assist_report.py"
        legacy_cli.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(TOOLS / "run_powershell_review_assist_report.py", legacy_cli)

    def run_generator(self, json_name, markdown_name, *flags):
        with patch.object(builder, "datetime", FrozenDatetime):
            return review.main([
                "--repo-root", str(self.root),
                "--json-output", json_name,
                "--markdown-output", markdown_name,
                *flags,
            ])

    def read_report_pair(self, json_name, markdown_name):
        return ((self.root / json_name).read_bytes(),
                (self.root / markdown_name).read_bytes())

    def legacy_wrapper_pair(self):
        """Run the actual original wrapper source archived from main SHA c8c76c59."""
        original = LEGACY_WRAPPER.read_bytes()
        blob = b"blob " + str(len(original)).encode() + b"\x00" + original
        self.assertEqual(hashlib.sha1(blob).hexdigest(),
                         "85ab09dfefc8a2dfa18313cedd8f96d03f3c4f44")
        self.assertEqual(self.run_generator(SOURCE_JSON, SOURCE_MARKDOWN), 0)

        spec = importlib.util.spec_from_file_location("issue608_legacy_wrapper", LEGACY_WRAPPER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        env = {
            "REVIEW_ASSIST_GENERATED_JSON": SOURCE_JSON,
            "REVIEW_ASSIST_TARGET_JSON": TARGET_JSON,
            "REVIEW_ASSIST_TARGET_MARKDOWN": TARGET_MARKDOWN,
        }
        with patch.dict(os.environ, env), changed_directory(self.root):
            self.assertEqual(module.main(), 0)
        return self.read_report_pair(TARGET_JSON, TARGET_MARKDOWN)

    def test_original_legacy_wrapper_is_fixed_and_generates_real_bytes(self):
        json_bytes, markdown_bytes = self.legacy_wrapper_pair()
        self.assertGreater(len(json_bytes), 100000)
        self.assertGreater(len(markdown_bytes), 10000)
        report = json.loads(json_bytes)
        self.assertEqual(report["generated_from"]["generated_at_utc"],
                         "2026-11-24T08:00:00+00:00")
        self.assertEqual(report["artifact_contract"]["workflow_behavior"],
                         "caller_uploaded_artifact")
        self.assertIn(b"Workflow behavior: ", markdown_bytes)
        self.assertIn(b"Retention scope: ", markdown_bytes)
        print("SLICE6_FROZEN_LEGACY_SHA256_JSON", hashlib.sha256(json_bytes).hexdigest())
        print("SLICE6_FROZEN_LEGACY_SHA256_MD", hashlib.sha256(markdown_bytes).hexdigest())

    def test_native_mode_equals_all_legacy_json_and_markdown_bytes(self):
        expected_json, expected_md = self.legacy_wrapper_pair()
        self.assertEqual(
            self.run_generator(TARGET_JSON, TARGET_MARKDOWN,
                               "--artifact-behavior", "caller_uploaded_artifact"),
            0,
        )
        native_json, native_md = self.read_report_pair(TARGET_JSON, TARGET_MARKDOWN)
        self.assertEqual(native_json, expected_json)
        self.assertEqual(native_md, expected_md)

    def test_default_local_contract_remains_unchanged(self):
        self.assertEqual(self.run_generator(TARGET_JSON, TARGET_MARKDOWN), 0)
        json_bytes, markdown_bytes = self.read_report_pair(TARGET_JSON, TARGET_MARKDOWN)
        report = json.loads(json_bytes)
        self.assertEqual(report["artifact_contract"]["workflow_behavior"], "none")
        self.assertIn(b"Retention scope:", markdown_bytes)
        self.assertNotIn(b"Workflow behavior:", markdown_bytes)
        self.assertEqual(report["artifact_contract"]["local_artifacts"]["json"],
                         review.DEFAULT_JSON_OUTPUT.as_posix())
        print("SLICE6_FROZEN_LOCAL_SHA256_JSON", hashlib.sha256(json_bytes).hexdigest())
        print("SLICE6_FROZEN_LOCAL_SHA256_MD", hashlib.sha256(markdown_bytes).hexdigest())

    def test_cli_accepts_native_behavior_and_retention_override(self):
        args = review.parse_args([
            "--artifact-behavior", "caller_uploaded_artifact",
            "--retention-scope", "operator-controlled test retention",
        ])
        self.assertEqual(args.artifact_behavior, "caller_uploaded_artifact")
        self.assertEqual(args.retention_scope, "operator-controlled test retention")


    def test_cli_rejects_invalid_behavior_and_retention(self):
        for args in (
            ["--artifact-behavior", "invalid"],
            ["--retention-scope", "not legal in local mode"],
            ["--artifact-behavior", "caller_uploaded_artifact", "--retention-scope", ""],
            ["--artifact-behavior", "caller_uploaded_artifact", "--retention-scope", "  "],
            ["--artifact-behavior", "caller_uploaded_artifact", "--retention-scope", "bad\nline"],
            ["--artifact-behavior", "caller_uploaded_artifact", "--retention-scope", "bad\rline"],
            ["--artifact-behavior", "caller_uploaded_artifact", "--retention-scope", "bad\x01line"],
            ["--artifact-behavior", "caller_uploaded_artifact", "--retention-scope", "bad\x7fline"],
        ):
            with self.subTest(args=args):
                with self.assertRaises(SystemExit) as ctx:
                    review.parse_args(args)
                self.assertEqual(ctx.exception.code, 2)

    def test_workflow_retention_override_matches_both_outputs(self):
        retention = "operator-controlled upload window for Slice 6"
        self.assertEqual(self.run_generator(
            TARGET_JSON, TARGET_MARKDOWN,
            "--artifact-behavior", "caller_uploaded_artifact",
            "--retention-scope", retention,
        ), 0)
        json_bytes, md_bytes = self.read_report_pair(TARGET_JSON, TARGET_MARKDOWN)
        report = json.loads(json_bytes)
        self.assertEqual(report["artifact_contract"]["retention_scope"], retention)
        self.assertEqual(report["artifact_contract"]["workflow_behavior"], "caller_uploaded_artifact")
        text = md_bytes.decode("utf-8")
        self.assertEqual(text.count("- Workflow behavior: "), 1)
        self.assertIn("- Retention scope: " + retention, text)

    def test_no_write_leaves_existing_artifacts_untouched(self):
        j_path = self.root / TARGET_JSON
        m_path = self.root / TARGET_MARKDOWN
        j_path.write_bytes(b"safe-json-marker")
        m_path.write_bytes(b"safe-markdown-marker")
        for mode in ("none", "caller_uploaded_artifact"):
            with self.subTest(mode=mode):
                self.assertEqual(
                    self.run_generator(TARGET_JSON, TARGET_MARKDOWN,
                                       "--artifact-behavior", mode, "--no-write"), 0)
                self.assertEqual(j_path.read_bytes(), b"safe-json-marker")
                self.assertEqual(m_path.read_bytes(), b"safe-markdown-marker")

    def test_workflow_mode_rejects_unsafe_output_locations(self):
        cases = (
            ("../outside.json", TARGET_MARKDOWN),
            ("/outside.json", TARGET_MARKDOWN),
            ("project_sources/collector/fault.txt", TARGET_MARKDOWN),
            (".github/workflows/escape.json", TARGET_MARKDOWN),
            (TARGET_JSON, ".github/workflows/escape.md"),
        )
        for json_name, markdown_name in cases:
            with self.subTest(json_name=json_name, markdown_name=markdown_name):
                self.assertEqual(self.run_generator(
                    json_name, markdown_name,
                    "--artifact-behavior", "caller_uploaded_artifact"), 1)
                self.assertFalse((self.root.parent / "outside.json").exists())
                self.assertFalse((self.root / ".github/workflows/escape.json").exists())
                self.assertFalse((self.root / ".github/workflows/escape.md").exists())

    def test_shipped_action_requires_single_native_invocation_no_wrapper(self):
        action = REPO_ROOT / ".github/actions/run-powershell-review-assist"
        reports = (action / "DcoirPowerShellReviewAssist.Reports.ps1").read_text(encoding="utf-8")
        entry = (action / "Invoke-DcoirPowerShellReviewAssist.ps1").read_text(encoding="utf-8")
        self.assertIn("--artifact-behavior caller_uploaded_artifact", reports)
        self.assertEqual(reports.count("run_powershell_review_assist_report.py"), 1)
        self.assertNotIn("MetadataWrapperScript", reports + entry)
        self.assertNotIn("REVIEW_ASSIST_GENERATED_JSON", reports)
        self.assertNotIn("REVIEW_ASSIST_TARGET_JSON", reports)
        self.assertNotIn("REVIEW_ASSIST_TARGET_MARKDOWN", reports)
        self.assertFalse((action / "wrap_review_assist_workflow_report.py").exists())
        self.assertIn("review-assist-validation-success:", reports)
        self.assertIn("review-assist-workflow-behavior:", reports)
        self.assertLess(entry.index("Invoke-FunctionReachabilityReviewAssistGate"),
                        entry.index("Invoke-PowerShellReviewAssistReportGate"))


if __name__ == "__main__":
    unittest.main()
