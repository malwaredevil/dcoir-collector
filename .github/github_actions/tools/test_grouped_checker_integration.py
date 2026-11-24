#!/usr/bin/env python3
"""End-to-end checker regression tests for grouped required-surface profiles."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CHECKER = ROOT / ".github/github_actions/tools/check_required_surfaces.py"
PROFILES = Path(".github/github_actions/workflow_required_surface_profiles.json")
GROUPED = Path(".github/github_actions/workflow_required_surface_profile_groups.json")
MANIFEST = Path(".github/github_actions/workflow_required_surface_profile_supplements.json")
SUPPLEMENT = Path(".github/github_actions/workflow_required_surface_profile_supplements/example.json")
PROFILE_NAMES = (
    "validate_on_push", "validate_on_pr", "manual_full_validation",
    "scheduled_health_check", "manual_gemini_bundle_build",
    "manual_gemini_model_comparison", "manual_collector_runtime_package_build",
    "manual_openai_gpt_deployment_package_build",
)


class GroupCheckerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.paths(["base.txt"])
        self.write(MANIFEST, {"supplements": [SUPPLEMENT.as_posix()]})
        self.write(SUPPLEMENT, {"validate_on_pr": ["extra.txt"]})
        (self.repo / "base.txt").write_text("x", encoding="utf-8")
        (self.repo / "extra.txt").write_text("x", encoding="utf-8")

    def write(self, rel, obj):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")

    def paths(self, paths):
        self.write(PROFILES, {name: list(paths) for name in PROFILE_NAMES})
        self.write(GROUPED, {
            "schema_version": "dcoir_required_surface_profile_groups_v1",
            "groups": {"base": list(paths)},
            "profiles": {name: [{"group": "base"}] for name in PROFILE_NAMES},
        })

    def check(self):
        return subprocess.run(
            [sys.executable, str(CHECKER), "--profile", "validate_on_pr", "--repo-root", str(self.repo)],
            capture_output=True, text=True, check=False, timeout=15,
        )

    def test_normal_composed_profile_succeeds(self):
        done = self.check()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("2 paths present", done.stdout)

    def test_group_change_cannot_use_stale_flat_artifact(self):
        grouped = json.loads((self.repo / GROUPED).read_text())
        grouped["groups"]["base"] = ["different.txt"]
        self.write(GROUPED, grouped)
        done = self.check()
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("Stale required-surface flat profile artifact", done.stderr)

    def test_missing_group_file_fails_closed(self):
        (self.repo / GROUPED).unlink()
        done = self.check()
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("grouped profile source", done.stderr)

    def test_missing_manifest_still_fails_closed(self):
        (self.repo / MANIFEST).unlink()
        done = self.check()
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("supplement manifest missing", done.stderr)

    def test_unsafe_path_fails_its_original_guard(self):
        self.paths(["../escape.txt"])
        done = self.check()
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("normalized repo-relative path", done.stderr)


if __name__ == "__main__":
    unittest.main()
