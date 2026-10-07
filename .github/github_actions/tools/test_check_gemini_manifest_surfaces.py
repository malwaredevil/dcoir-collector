#!/usr/bin/env python3
"""Regression tests for the CI Gemini manifest surface helper.

The helper must reject exactly what the canonical bundle validator rejects.
It used to keep its own rules: an unlisted Sub_Agent_*.txt file passed it
(it only globbed *.md.txt), so with skip_validation the file shipped in the
delivery zip.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HELPER = REPO_ROOT / ".github" / "github_actions" / "tools" / "check_gemini_manifest_surfaces.py"
SOURCE_REL = Path("project_sources") / "gemini" / "bundle_source"
MANIFEST_NAME = "Gemini_Bundle_Source_Manifest.json"


class GeminiManifestSurfaceHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.source_root = root / SOURCE_REL
        shutil.copytree(REPO_ROOT / SOURCE_REL, self.source_root)
        shutil.copytree(REPO_ROOT / "knowledge", root / "knowledge")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_helper(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HELPER), "--source-root", str(self.source_root)],
            capture_output=True,
            text=True,
            check=False,
        )

    def edit_manifest(self, edit) -> None:
        path = self.source_root / MANIFEST_NAME
        manifest = json.loads(path.read_text(encoding="utf-8"))
        edit(manifest)
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def assert_rejected(self, message: str) -> None:
        result = self.run_helper()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(message, result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_clean_source_passes(self) -> None:
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Gemini manifest surfaces validated:", result.stdout)

    def test_unlisted_txt_sub_agent_is_rejected(self) -> None:
        (self.source_root / "01_GEMINI_AGENT_BUILD" / "Sub_Agent_99_Unlisted.txt").write_text("x\n", encoding="utf-8")
        self.assert_rejected("discovered sub-agent files do not exactly match manifest topology")

    def test_non_manifest_topology_source_is_rejected(self) -> None:
        self.edit_manifest(lambda m: m["topology"].update(topology_source_of_truth="directory_scan"))
        self.assert_rejected("topology.topology_source_of_truth must be manifest")

    def test_empty_required_files_is_rejected(self) -> None:
        self.edit_manifest(lambda m: m.update(required_files=[]))
        self.assert_rejected("required_files must list at least one file")

    def test_unreadable_manifest_is_rejected(self) -> None:
        (self.source_root / MANIFEST_NAME).write_text("{not json", encoding="utf-8")
        self.assert_rejected("Gemini bundle manifest could not be read: JSONDecodeError")

    def test_unsafe_manifest_path_is_rejected_before_file_checks(self) -> None:
        self.edit_manifest(lambda m: m["required_files"].append("../../outside.txt"))
        result = self.run_helper()
        self.assertEqual(result.returncode, 1)
        self.assertIn("required_files", result.stderr)
        self.assertNotIn("missing required source-root files", result.stderr)

    def test_runtime_governance_leak_is_rejected(self) -> None:
        manifest = json.loads(
            (self.source_root / MANIFEST_NAME).read_text(encoding="utf-8")
        )
        runtime_path = self.source_root / manifest["topology"]["sub_agent_files"][0]
        runtime_path.write_text(
            runtime_path.read_text(encoding="utf-8")
            + "\nselect ircore.get_gemini_research_consultation(...)\n",
            encoding="utf-8",
        )
        self.assert_rejected("runtime-facing Gemini files contain builder/governance source references")


if __name__ == "__main__":
    unittest.main()
