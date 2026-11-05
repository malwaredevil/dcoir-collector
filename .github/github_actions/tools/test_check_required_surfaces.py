#!/usr/bin/env python3
"""Regression tests for required-surface supplement manifest fail-closed handling."""
from __future__ import annotations

import importlib.util
import json
import os
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


    def write_base_profiles(self, profiles: dict[str, list[str]]) -> None:
        (self.root / PROFILE_PATH).write_text(json.dumps(profiles), encoding="utf-8")

    def test_unsafe_required_surface_path_variants_fail_closed(self) -> None:
        unsafe = (
            "", ".", "./base.txt", "../outside.txt", "nested/../../outside.txt",
            "/tmp/outside.txt", r"C:\Temp\outside.txt", r"C:relative.txt",
            r"\\server\share\file.txt", r"folder\file.txt", "folder//file.txt",
            " base.txt", "base.txt ", "name" + chr(0) + ".txt",
        )
        for value in unsafe:
            with self.subTest(path=repr(value)):
                self.write_base_profiles({"sample": [value]})
                self.assert_rejected("must be a normalized repo-relative path")

    def test_bad_unselected_profile_fails_closed(self) -> None:
        self.write_base_profiles({"sample": ["base.txt"], "unused": ["../escape.txt"]})
        self.assert_rejected("must be a normalized repo-relative path")

    def test_supplement_required_path_traversal_fails_closed(self) -> None:
        (self.root / SUPPLEMENT_REL).write_text(
            json.dumps({"sample": ["../outside.txt"]}), encoding="utf-8"
        )
        self.assert_rejected("must be a normalized repo-relative path")

    def test_supplement_windows_path_fails_closed(self) -> None:
        (self.root / SUPPLEMENT_REL).write_text(
            json.dumps({"sample": [r"C:\Temp\outside.txt"]}), encoding="utf-8"
        )
        self.assert_rejected("must be a normalized repo-relative path")

    def test_valid_nested_required_path_preserves_success(self) -> None:
        nested = self.root / "nested"
        nested.mkdir()
        (nested / "valid.txt").write_text("valid", encoding="utf-8")
        self.write_base_profiles({"sample": ["nested/valid.txt"]})
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("validated: 2 paths present", result.stdout)

    def test_required_path_symlink_inside_repo_passes(self) -> None:
        try:
            (self.root / "inside-link.txt").symlink_to(self.root / "base.txt")
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Symlinks not supported: {exc}")
        self.write_base_profiles({"sample": ["inside-link.txt"]})
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("validated: 2 paths present", result.stdout)

    def test_required_path_symlink_outside_repo_fails_closed(self) -> None:
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        target = Path(outside.name) / "external.txt"
        target.write_text("outside", encoding="utf-8")
        try:
            (self.root / "external-link.txt").symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Symlinks not supported: {exc}")
        self.write_base_profiles({"sample": ["external-link.txt"]})
        self.assert_rejected("resolve outside repository")

    def test_required_path_symlink_loop_fails_without_traceback(self) -> None:
        try:
            (self.root / "loop-link.txt").symlink_to("loop-link.txt")
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Symlinks not supported: {exc}")
        self.write_base_profiles({"sample": ["loop-link.txt"]})
        self.assert_rejected("Unable to resolve required governed surface")


    def external_json(self, data: object) -> Path:
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        target = Path(outside.name) / "outside.json"
        target.write_text(json.dumps(data), encoding="utf-8")
        return target

    def symlink_to(self, link: Path, target: Path | str) -> None:
        link.unlink()
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Symlinks not supported: {exc}")

    def test_base_profile_json_symlink_escape_fails_closed(self) -> None:
        target = self.external_json({"sample": ["base.txt"]})
        self.symlink_to(self.root / PROFILE_PATH, target)
        self.assert_rejected("Required surface profile file resolves outside repository")

    def test_supplement_manifest_json_symlink_escape_fails_closed(self) -> None:
        target = self.external_json({"supplements": [SUPPLEMENT_REL.as_posix()]})
        self.symlink_to(self.root / MANIFEST_PATH, target)
        self.assert_rejected("Required surface profile supplement manifest resolves outside repository")

    def test_supplement_json_symlink_escape_fails_closed(self) -> None:
        target = self.external_json({"sample": ["extra.txt"]})
        self.symlink_to(self.root / SUPPLEMENT_REL, target)
        self.assert_rejected("Required surface profile supplement file resolves outside repository")

    def test_supplement_json_symlink_loop_fails_without_traceback(self) -> None:
        supplement_file = self.root / SUPPLEMENT_REL
        self.symlink_to(supplement_file, supplement_file)
        self.assert_rejected("Unable to resolve Required surface profile supplement file")

    def test_supplement_json_symlink_within_repo_still_passes(self) -> None:
        supplement_file = self.root / SUPPLEMENT_REL
        alternative = supplement_file.with_name("alternate.json")
        alternative.write_text(json.dumps({"sample": ["extra.txt"]}), encoding="utf-8")
        self.symlink_to(supplement_file, alternative)
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("validated: 2 paths present", result.stdout)

    def test_noncanonical_supplement_manifest_references_fail_closed(self) -> None:
        unsafe_refs = (
            "", ".", "./base.txt", "nested/../base.txt", "folder//part.json",
            "folder/part.json/", r"C:\Temp\outside.json", r"C:outside.json",
            r"folder\file.json", "/tmp/outside.json", "wrong" + chr(0) + ".json",
        )
        for ref in unsafe_refs:
            with self.subTest(ref=repr(ref)):
                self.manifest_file.write_text(
                    json.dumps({"supplements": [ref]}), encoding="utf-8"
                )
                self.assert_rejected("Required surface profile supplement path must be repo-relative")

    def test_base_profile_json_symlink_loop_fails_without_traceback(self) -> None:
        path = self.root / PROFILE_PATH
        self.symlink_to(path, path)
        self.assert_rejected("Unable to resolve Required surface profile file")


    def test_direct_loaders_accept_relative_repository_root(self) -> None:
        spec = importlib.util.spec_from_file_location("required_surfaces_under_test", HELPER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        original_cwd = Path.cwd()
        try:
            os.chdir(self.root)
            self.assertEqual(
                module.load_profiles(Path("."))["sample"],
                ["base.txt", "extra.txt"],
            )
            self.assertEqual(
                module.load_profile_supplements(Path("."))["sample"],
                ["extra.txt"],
            )
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
