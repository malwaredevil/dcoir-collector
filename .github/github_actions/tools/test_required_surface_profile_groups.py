#!/usr/bin/env python3
"""Behavior and fail-closed tests for required-surface grouped profiles."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
MODULE = TOOL_DIR / "required_surface_profile_groups.py"
GROUPS_PATH = Path(".github/github_actions/workflow_required_surface_profile_groups.json")
FLAT_PATH = Path(".github/github_actions/workflow_required_surface_profiles.json")
NAMES = (
    "validate_on_push", "validate_on_pr", "manual_full_validation",
    "scheduled_health_check", "manual_gemini_bundle_build",
    "manual_gemini_model_comparison", "manual_collector_runtime_package_build",
    "manual_openai_gpt_deployment_package_build",
)


def fixture(paths=None):
    paths = ["README.md", "nested/file.txt"] if paths is None else paths
    return {
        "schema_version": "dcoir_required_surface_profile_groups_v1",
        "groups": {"shared_paths": paths},
        "profiles": {key: [{"group": "shared_paths"}] for key in NAMES},
    }


class GroupedProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("required_surface_profile_groups", MODULE)
        if spec is None or spec.loader is None:
            raise RuntimeError("Required grouped-source module has not been implemented")
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dcoir-groups-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / GROUPS_PATH).parent.mkdir(parents=True, exist_ok=True)
        (self.root / "nested").mkdir()
        (self.root / "README.md").write_text("safe", encoding="utf-8")
        (self.root / "nested/file.txt").write_text("safe", encoding="utf-8")
        self.write_source(fixture())

    def write_source(self, value):
        (self.root / GROUPS_PATH).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(MODULE), *args, "--repo-root", str(self.root)],
            check=False, capture_output=True, text=True, timeout=20,
        )

    def assert_bad(self, data, fragment):
        with self.assertRaisesRegex(ValueError, fragment):
            self.mod.expand_canonical(data)

    def test_ordered_expansion_and_explicit_segment(self):
        data = fixture()
        data["profiles"]["validate_on_pr"].append({"paths": ["extra.txt"]})
        expanded = self.mod.expand_canonical(data)
        self.assertEqual(list(expanded), list(NAMES))
        self.assertEqual(expanded["validate_on_pr"], ["README.md", "nested/file.txt", "extra.txt"])
        self.assertEqual(expanded["validate_on_push"], ["README.md", "nested/file.txt"])

    def test_reject_unknown_group_and_duplicate_output(self):
        data = fixture()
        data["profiles"]["validate_on_pr"] = [{"group": "missing"}]
        self.assert_bad(data, "[Uu]nknown")
        data = fixture()
        data["profiles"]["validate_on_pr"].append({"paths": ["README.md"]})
        self.assert_bad(data, "[Dd]uplicate|[Rr]epeat")

    def test_reject_invalid_schema_and_segments(self):
        data = fixture()
        data["schema_version"] = "unknown"
        self.assert_bad(data, "[Vv]ersion|[Ss]chema")
        data = fixture()
        data["unexpected"] = 1
        self.assert_bad(data, "[Kk]ey|[Ss]chema|[Pp]ropert")
        data = fixture()
        data["profiles"]["validate_on_pr"] = [{"group": "shared_paths", "paths": ["safe"]}]
        self.assert_bad(data, "[Ss]egment|[Kk]ey|[Ee]xact")
        data = fixture()
        del data["profiles"]["validate_on_push"]
        self.assert_bad(data, "[Pp]rofile|[Ee]xpect")

    def test_reject_unsafe_literals(self):
        bad = ["", "../secret", "./bad", "folder/../bad", "/etc/passwd", "C:/Windows/system.ini", "C:bad", "folder\\bad", "folder//bad", " name", "name ", "nul\0char"]
        for value in bad:
            with self.subTest(path=repr(value)):
                data = fixture([value])
                self.assert_bad(data, "[Pp]ath|[Rr]elative|[Nn]ormal")

    def test_reject_invalid_group_definition(self):
        for value in ([], "string", None, [1]):
            with self.subTest(value=value):
                data = fixture()
                data["groups"]["shared_paths"] = value
                self.assert_bad(data, "[Gg]roup|[Pp]ath|[Ll]ist")

    def test_reject_duplicate_json_keys(self):
        path = self.root / GROUPS_PATH
        path.write_text('{"schema_version":"dcoir_required_surface_profile_groups_v1","schema_version":"bad"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "[Dd]uplicate"):
            self.mod.read_groups(self.root)

    def test_generation_check_and_noop_repeat(self):
        missing = self.run_cli("--check")
        self.assertEqual(missing.returncode, 1, missing.stdout + missing.stderr)
        self.assertFalse((self.root / FLAT_PATH).exists())
        first = self.run_cli("--write")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        before = (self.root / FLAT_PATH).read_bytes()
        self.assertEqual(json.loads(before), self.mod.expand_canonical(fixture()))
        ok = self.run_cli("--check")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertEqual(self.run_cli("--write").returncode, 0)
        self.assertEqual(before, (self.root / FLAT_PATH).read_bytes())

    def test_stale_order_and_formatting_fail_closed(self):
        self.assertEqual(self.run_cli("--write").returncode, 0)
        flat = self.root / FLAT_PATH
        value = json.loads(flat.read_text(encoding="utf-8"))
        value["validate_on_pr"].reverse()
        flat.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        self.assertNotEqual(self.run_cli("--check").returncode, 0)
        self.assertEqual(self.run_cli("--write").returncode, 0)
        flat.write_text(json.dumps(json.loads(flat.read_text()), separators=(",", ":")), encoding="utf-8")
        self.assertNotEqual(self.run_cli("--check").returncode, 0)

    def test_malformed_source_write_preserves_flat(self):
        self.assertEqual(self.run_cli("--write").returncode, 0)
        original = (self.root / FLAT_PATH).read_bytes()
        (self.root / GROUPS_PATH).write_text("{bad", encoding="utf-8")
        rejected = self.run_cli("--write")
        self.assertEqual(rejected.returncode, 1)
        self.assertEqual(original, (self.root / FLAT_PATH).read_bytes())

    def test_source_symlink_escape_fails_closed(self):
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        target = Path(elsewhere.name) / "outside.json"
        target.write_text(json.dumps(fixture()), encoding="utf-8")
        link = self.root / GROUPS_PATH
        link.unlink()
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(str(exc))
        self.assertNotEqual(self.run_cli("--write").returncode, 0)
        self.assertFalse((self.root / FLAT_PATH).exists())

    def test_flat_symlink_escape_fails_closed(self):
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        target = Path(elsewhere.name) / "outside.json"
        target.write_text("outside", encoding="utf-8")
        link = self.root / FLAT_PATH
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(str(exc))
        self.assertNotEqual(self.run_cli("--write").returncode, 0)
        self.assertEqual(target.read_text(encoding="utf-8"), "outside")

    def test_group_source_symlink_loop_has_explicit_resolution_error(self):
        link = self.root / GROUPS_PATH
        link.unlink()
        try:
            link.symlink_to(link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(str(exc))
        done = self.run_cli("--check")
        self.assertEqual(done.returncode, 1)
        self.assertIn("Unable to resolve Required surface grouped profile source", done.stderr)

    def test_reject_unknown_cli_flags(self):
        r = self.run_cli("--write", "--unknown")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.root / FLAT_PATH).exists())


if __name__ == "__main__":
    unittest.main()
