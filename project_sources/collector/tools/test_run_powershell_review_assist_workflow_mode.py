#!/usr/bin/env python3
"""Slice 6: compare complete native workflow report bytes against the exact legacy wrapper."""
from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
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
LEGACY_FIXTURES = REPO_ROOT / "project_sources/collector/fixtures/powershell_review_assist"
LEGACY_WRAPPER = LEGACY_FIXTURES / "issue608_slice6_legacy_wrapper.py"
# Complete pre-Slice-6 implementation archived from c8c76c59; the manifest pins
# each Git blob so the oracle cannot share code with the modules under review.
LEGACY_IMPLEMENTATION = LEGACY_FIXTURES / "issue608_slice6_legacy_c8c76c59"
LEGACY_MANIFEST = json.loads(
    (LEGACY_FIXTURES / "issue608_slice6_legacy_artifact_manifest.json").read_text(encoding="utf-8"))
LEGACY_IMPLEMENTATION_BLOBS = LEGACY_MANIFEST["legacy_implementation"]["git_blob_sha1"]
LEGACY_TOOLS = "project_sources/collector/tools"
# Isolated (-I) interpreter importing only the archived tools; runs generator then wrapper like the old action.
LEGACY_DRIVER = r"""
import importlib.util, os, sys
from datetime import datetime, timezone
from pathlib import Path
tools = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(tools))
import powershell_review_assist_builder as legacy_builder
import run_powershell_review_assist_report as legacy_cli
fixed = datetime.fromisoformat(sys.argv[3])
class FrozenDatetime:
    @staticmethod
    def now(tz=None):
        return fixed.astimezone(tz or timezone.utc)
legacy_builder.datetime = FrozenDatetime
rc = legacy_cli.main(["--repo-root", ".", "--json-output", os.environ["REVIEW_ASSIST_GENERATED_JSON"],
                      "--markdown-output", sys.argv[4]])
if rc != 0:
    raise SystemExit(10 + rc)
spec = importlib.util.spec_from_file_location("issue608_legacy_wrapper", sys.argv[2])
wrapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrapper)
rc = wrapper.main()
for name, module in list(sys.modules.items()):
    if "powershell_review_assist" in name:
        origin = Path(getattr(module, "__file__", "") or "").resolve()
        if origin.parent != tools:
            raise SystemExit(f"non-legacy module loaded: {name} from {origin}")
raise SystemExit(rc)
"""
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
        # The legacy wrapper imports the CLI by repo-relative CWD, so the
        # complete archived c8c76c59 implementation is materialized there.
        legacy_tools = self.root / LEGACY_TOOLS
        legacy_tools.mkdir(parents=True, exist_ok=True)
        for name in LEGACY_IMPLEMENTATION_BLOBS:
            shutil.copy2(LEGACY_IMPLEMENTATION / name, legacy_tools / name)

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

    def assert_git_blob(self, path: Path, expected: str):
        # Undo a Windows autocrlf checkout so the hash equals the Git blob.
        original = path.read_bytes().replace(b"\r\n", b"\n")
        blob = b"blob " + str(len(original)).encode() + b"\x00" + original
        self.assertEqual(hashlib.sha1(blob).hexdigest(), expected, path.name)

    def legacy_wrapper_pair(self):
        """Run the complete archived c8c76c59 generator and wrapper in isolation."""
        self.assert_git_blob(LEGACY_WRAPPER, LEGACY_MANIFEST["legacy_wrapper_git_blob_sha1"])
        self.assertEqual(
            sorted(p.name for p in LEGACY_IMPLEMENTATION.glob("*.py")),
            sorted(LEGACY_IMPLEMENTATION_BLOBS),
        )
        for name, blob_sha in LEGACY_IMPLEMENTATION_BLOBS.items():
            self.assert_git_blob(LEGACY_IMPLEMENTATION / name, blob_sha)
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.update({
            "PYTHONDONTWRITEBYTECODE": "1",
            "REVIEW_ASSIST_GENERATED_JSON": SOURCE_JSON,
            "REVIEW_ASSIST_TARGET_JSON": TARGET_JSON,
            "REVIEW_ASSIST_TARGET_MARKDOWN": TARGET_MARKDOWN,
        })
        result = subprocess.run(
            [sys.executable, "-I", "-c", LEGACY_DRIVER, LEGACY_TOOLS,
             str(LEGACY_WRAPPER), FIXED_TIME.isoformat(), SOURCE_MARKDOWN],
            cwd=self.root, env=env, capture_output=True, text=True, timeout=300, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
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


    def test_missing_required_source_fails_workflow_mode(self):
        (self.root / review.DEFAULT_RULE_RISK_REPORT).unlink()
        self.assertEqual(self.run_generator(
            TARGET_JSON, TARGET_MARKDOWN,
            "--artifact-behavior", "caller_uploaded_artifact",
        ), 1)
        report = json.loads((self.root / TARGET_JSON).read_text(encoding="utf-8"))
        self.assertFalse(report["validation"]["success"])
        self.assertFalse(report["summary"]["validation_success"])

    def test_workflow_markdown_write_error_persists_failed_json(self):
        original_write = Path.write_text

        def reject_markdown(path, text, *args, **kwargs):
            if path.name == Path(TARGET_MARKDOWN).name:
                raise OSError("seeded workflow Markdown write failure")
            return original_write(path, text, *args, **kwargs)

        with patch.object(Path, "write_text", reject_markdown):
            rc = self.run_generator(
                TARGET_JSON, TARGET_MARKDOWN,
                "--artifact-behavior", "caller_uploaded_artifact",
            )
        self.assertEqual(rc, 1)
        failed_report = json.loads((self.root / TARGET_JSON).read_text(encoding="utf-8"))
        self.assertFalse(failed_report["validation"]["success"])
        self.assertFalse(failed_report["summary"]["validation_success"])
        self.assertTrue(any("write failure" in str(item) for item in failed_report["validation"]["errors"]))


if __name__ == "__main__":
    unittest.main()
