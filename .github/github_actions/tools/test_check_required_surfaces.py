#!/usr/bin/env python3
"""Regression tests for required-surface supplement manifest fail-closed handling."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HELPER = REPO_ROOT / ".github/github_actions/tools/check_required_surfaces.py"
PROFILE_PATH = Path(".github/github_actions/workflow_required_surface_profiles.json")
MANIFEST_PATH = Path(".github/github_actions/workflow_required_surface_profile_supplements.json")
SUPPLEMENT_REL = Path(".github/github_actions/workflow_required_surface_profile_supplements/extra.json")


class RequiredSurfaceSupplementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        profile_file = self.root / PROFILE_PATH
        profile_file.parent.mkdir(parents=True, exist_ok=True)
        profile_file.write_text(json.dumps({"sample": ["base.txt"]}), encoding="utf-8")
        (self.root / "base.txt").write_text("base", encoding="utf-8")
        supplement_file = self.root / SUPPLEMENT_REL
        supplement_file.parent.mkdir(parents=True, exist_ok=True)
        supplement_file.write_text(json.dumps({"sample": ["extra.txt"]}), encoding="utf-8")
        (self.root / "extra.txt").write_text("extra", encoding="utf-8")
        self.manifest_file = self.root / MANIFEST_PATH
        self.manifest_file.write_text(
            json.dumps({"supplements": [SUPPLEMENT_REL.as_posix()]}),
            encoding="utf-8",
        )

    def run_helper(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(HELPER),
                "--profile", "sample",
                "--repo-root", str(self.root),
            ],
            text=True,
            capture_output=True,
            check=False,
            timeout=15,
        )

    def assert_rejected(self, expected: str) -> None:
        result = self.run_helper()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(expected, result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_valid_manifest_and_supplement_pass(self) -> None:
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("validated: 2 paths present", result.stdout)

    def test_missing_manifest_fails_closed(self) -> None:
        self.manifest_file.unlink()
        self.assert_rejected("Required surface profile supplement manifest missing:")

    def test_malformed_manifest_fails_closed(self) -> None:
        self.manifest_file.write_text("{bad", encoding="utf-8")
        self.assert_rejected("Invalid JSON")

    def test_manifest_missing_supplements_list_fails_closed(self) -> None:
        self.manifest_file.write_text(json.dumps({}), encoding="utf-8")
        self.assert_rejected("must define a list of supplement paths")

    def test_missing_listed_supplement_fails_closed(self) -> None:
        (self.root / SUPPLEMENT_REL).unlink()
        self.assert_rejected("Required surface profile supplement file missing:")

    def test_traversal_supplement_path_fails_closed(self) -> None:
        self.manifest_file.write_text(
            json.dumps({"supplements": ["../outside.json"]}), encoding="utf-8"
        )
        self.assert_rejected("must be repo-relative")

    def test_malformed_supplement_content_fails_closed(self) -> None:
        (self.root / SUPPLEMENT_REL).write_text(
            json.dumps({"sample": "not a list"}), encoding="utf-8"
        )
        self.assert_rejected("must map to a list of string paths")

    def test_missing_supplement_required_surface_fails_closed(self) -> None:
        (self.root / "extra.txt").unlink()
        self.assert_rejected("Missing required governed surfaces")


if __name__ == "__main__":
    unittest.main()
