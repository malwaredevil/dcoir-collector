#!/usr/bin/env python3
"""Run real NTFS reparse-point containment checks in the existing Windows PR job.

The GitHub Actions Ready-stage Windows job discovers tests in this directory.
These cases deliberately test the shipped required-surface checker, not a mock.
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
CHECKER = REPO_ROOT / ".github/github_actions/tools/check_required_surfaces.py"
PROFILES = Path(".github/github_actions/workflow_required_surface_profiles.json")
MANIFEST = Path(".github/github_actions/workflow_required_surface_profile_supplements.json")
SUPPLEMENT_DIR = Path(".github/github_actions/workflow_required_surface_profile_supplements")
SUPPLEMENT = SUPPLEMENT_DIR / "sample.json"


@unittest.skipUnless(sys.platform == "win32", "Real NTFS junction validation requires a Windows runner")
class RequiredSurfaceWindowsJunctionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="dcoir-ntfs-boundary-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "checkout"
        self.root.mkdir()
        self.outside = Path(self.temp.name) / "outside-checkout"
        self.outside.mkdir()
        (self.root / PROFILES).parent.mkdir(parents=True)
        (self.root / SUPPLEMENT).parent.mkdir(parents=True)
        self.write_json(self.root / PROFILES, {"sample": ["base.txt"]})
        self.write_json(self.root / MANIFEST, {"supplements": [SUPPLEMENT.as_posix()]})
        self.write_json(self.root / SUPPLEMENT, {"sample": ["extra.txt"]})
        (self.root / "base.txt").write_text("base", encoding="utf-8")
        (self.root / "extra.txt").write_text("extra", encoding="utf-8")

    @staticmethod
    def write_json(path: Path, value: object) -> None:
        path.write_text(json.dumps(value), encoding="utf-8")

    def junction(self, link: Path, target: Path) -> None:
        self.assertFalse(link.exists(), f"Unexpected junction fixture conflict: {link}")
        self.assertTrue(target.is_dir(), f"Invalid junction target: {target}")
        # mklink /J creates an actual NTFS junction and needs no Developer Mode.
        command = subprocess.list2cmdline(["mklink", "/J", str(link), str(target)])
        process = subprocess.run(
            ["cmd.exe", "/D", "/C", command],
            capture_output=True, text=True, check=False, timeout=15,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.addCleanup(self.remove_junction, link)

    @staticmethod
    def remove_junction(link: Path) -> None:
        # On modern Windows, rmdir removes the junction, not target contents.
        if link.exists() or link.is_symlink():
            link.rmdir()

    def checker(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CHECKER), "--profile", "sample", "--repo-root", str(self.root)],
            text=True, capture_output=True, check=False, timeout=20,
        )

    def assert_rejected(self, expected: str) -> None:
        p = self.checker()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn(expected, p.stderr)
        self.assertNotIn("Traceback", p.stderr)

    def test_normal_file_paths_pass_on_windows(self) -> None:
        p = self.checker()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("validated: 2 paths present", p.stdout)

    def test_ntfs_junction_to_outside_required_file_fails_closed(self) -> None:
        (self.outside / "outside.txt").write_text("external", encoding="utf-8")
        self.junction(self.root / "escape", self.outside)
        self.write_json(self.root / PROFILES, {"sample": ["escape/outside.txt"]})
        self.assert_rejected("resolve outside repository")

    def test_ntfs_junction_to_inside_required_file_is_allowed(self) -> None:
        inside = self.root / "safe-directory"
        inside.mkdir()
        (inside / "safe.txt").write_text("safe", encoding="utf-8")
        self.junction(self.root / "inside", inside)
        self.write_json(self.root / PROFILES, {"sample": ["inside/safe.txt"]})
        p = self.checker()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("validated: 2 paths present", p.stdout)

    def test_ntfs_junction_to_external_supplement_json_fails_closed(self) -> None:
        self.write_json(self.outside / "supplement.json", {"sample": ["extra.txt"]})
        junction = self.root / SUPPLEMENT_DIR / "external-link"
        self.junction(junction, self.outside)
        self.write_json(
            self.root / MANIFEST,
            {"supplements": [(SUPPLEMENT_DIR / "external-link/supplement.json").as_posix()]},
        )
        self.assert_rejected("supplement file resolves outside repository")

    def test_ntfs_junction_to_internal_supplement_json_is_allowed(self) -> None:
        inside = self.root / SUPPLEMENT_DIR / "safe-json"
        inside.mkdir()
        self.write_json(inside / "supplement.json", {"sample": ["extra.txt"]})
        self.junction(self.root / SUPPLEMENT_DIR / "internal-link", inside)
        self.write_json(
            self.root / MANIFEST,
            {"supplements": [(SUPPLEMENT_DIR / "internal-link/supplement.json").as_posix()]},
        )
        p = self.checker()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("validated: 2 paths present", p.stdout)

    def test_ntfs_junction_to_external_profile_source_fails_closed(self) -> None:
        # Move a copy of the JSON sources outside the checkout, then replace
        # their common parent with a real junction to the external directory.
        original = self.root / ".github/github_actions"
        target = self.outside / "github_actions"
        shutil.copytree(original, target)
        shutil.rmtree(original)
        self.junction(original, target)
        self.assert_rejected("Required surface profile file resolves outside repository")

    def test_file_symlink_to_external_required_file_fails_when_supported(self) -> None:
        target = self.outside / "external.txt"
        target.write_text("external", encoding="utf-8")
        link = self.root / "external-file-link.txt"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Windows runner denies file symlink creation: {exc}")
        self.write_json(self.root / PROFILES, {"sample": ["external-file-link.txt"]})
        self.assert_rejected("resolve outside repository")


if __name__ == "__main__":
    unittest.main()
