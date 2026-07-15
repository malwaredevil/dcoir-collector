#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import re
import tempfile
import unittest
import unittest.mock
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent / "build_powershell_surface_inventory.py"
_SPEC = importlib.util.spec_from_file_location("build_powershell_surface_inventory", _MODULE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load inventory module from {_MODULE_PATH}")
inventory = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(inventory)


class PowerShellSurfaceInventoryPathSafetyTests(unittest.TestCase):
    def _write_manifest(self, root: Path, wrapper: str, parts: list[str] | None = None) -> None:
        manifest_path = root / inventory.MANIFEST_PATH
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "collector_wrapper_source": wrapper,
                    "collector_part_files": parts or [],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_changed_file_paths_preserve_valid_repo_relative_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = inventory.normalize_changed_files([
                "project_sources\\collector\\source\\DCOIR_Collector.ps1",
                "./project_sources/collector/source/parts/DCOIR_Collector.01_Core.ps1",
                ".github/workflows/validate.yml",
            ], root)
        self.assertEqual(paths, [
            ".github/workflows/validate.yml",
            "project_sources/collector/source/DCOIR_Collector.ps1",
            "project_sources/collector/source/parts/DCOIR_Collector.01_Core.ps1",
        ])

    def test_changed_file_absolute_path_under_repo_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            absolute = root / "project_sources/collector/source/DCOIR_Collector.ps1"
            with self.assertRaises(ValueError):
                inventory.normalize_changed_files([absolute.as_posix()], root)

    def test_changed_file_inputs_must_not_escape_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            cases = [
                "../outside.ps1",
                "project_sources/../outside.ps1",
                "/project_sources/collector/source/DCOIR_Collector.ps1",
                (root.parent / "outside.ps1").as_posix(),
                "C:\\outside\\collector.ps1",
                "C:outside\\collector.ps1",
                "\\\\server\\share\\collector.ps1",
                "",
            ]
            for value in cases:
                with self.subTest(value=value):
                    with self.assertRaises(ValueError):
                        inventory.normalize_changed_files([value], root)

    def test_changed_files_from_preserves_embedded_blank_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            changed_files = root / "changed-files.txt"
            changed_files.write_text(
                "project_sources/collector/source/DCOIR_Collector.ps1\n\nother.ps1\n",
                encoding="utf-8",
            )
            records = inventory.load_changed_files_from(changed_files)
            self.assertEqual(records, ["project_sources/collector/source/DCOIR_Collector.ps1", "", "other.ps1"])
            with self.assertRaises(ValueError):
                inventory.normalize_changed_files(records, root)

    def test_changed_files_from_preserves_embedded_whitespace_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            changed_files = root / "changed-files.txt"
            changed_files.write_text(
                "project_sources/collector/source/DCOIR_Collector.ps1\n   \nother.ps1\n",
                encoding="utf-8",
            )
            records = inventory.load_changed_files_from(changed_files)
            self.assertEqual(records, ["project_sources/collector/source/DCOIR_Collector.ps1", "   ", "other.ps1"])
            with self.assertRaises(ValueError):
                inventory.normalize_changed_files(records, root)

    def test_changed_files_from_blank_only_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            changed_files = root / "changed-files.txt"
            changed_files.write_text("\n", encoding="utf-8")
            records = inventory.load_changed_files_from(changed_files)
            self.assertEqual(records, [""])
            with self.assertRaises(ValueError):
                inventory.normalize_changed_files(records, root)

    def test_changed_files_from_whitespace_only_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            changed_files = root / "changed-files.txt"
            changed_files.write_text(" \t \n", encoding="utf-8")
            records = inventory.load_changed_files_from(changed_files)
            self.assertEqual(records, [" \t "])
            with self.assertRaises(ValueError):
                inventory.normalize_changed_files(records, root)

    def test_changed_files_from_empty_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            changed_files = root / "changed-files.txt"
            changed_files.write_text("", encoding="utf-8")
            records = inventory.load_changed_files_from(changed_files)
            self.assertEqual(records, [""])
            with self.assertRaises(ValueError):
                inventory.normalize_changed_files(records, root)

    def test_changed_file_normalized_outputs_are_not_rooted_or_drive_qualified(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            paths = inventory.normalize_changed_files([
                ".github/workflows/validate.yml",
                "project_sources/collector/source/DCOIR_Collector.ps1",
            ], root)
        for path in paths:
            with self.subTest(path=path):
                self.assertFalse(Path(path).is_absolute())
                self.assertIsNone(re.match(r"^[A-Za-z]:", path.replace("\\", "/")))

    def test_symlinked_inventory_file_fails_closed_before_hashing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            outside = root.parent / "outside_inventory.ps1"
            outside.write_text('Write-Output "outside"\n', encoding="utf-8")
            rel = ".github/operator_tools/linked.ps1"
            link = root / rel
            link.parent.mkdir(parents=True, exist_ok=True)
            try:
                link.symlink_to(outside)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")

            surface = inventory.make_surface(
                root,
                rel,
                "operator_tooling",
                "tooling",
                "include",
                "test symlink surface",
                True,
            )
            validation = inventory.validate_inventory(
                [surface],
                "changed",
                {},
                {"input_paths": [rel], "rules": []},
            )

        self.assertIsNone(surface["sha256"])
        self.assertFalse(validation["success"])
        self.assertTrue(
            any("file facts could not be collected safely inside the repository root" in error for error in validation["errors"]),
            validation["errors"],
        )

    def test_harness_source_part_directory_symlink_is_not_globbed(self) -> None:
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside_temp:
            root = Path(temp).resolve()
            outside = Path(outside_temp).resolve()
            (outside / "run_DCOIR_Tests.part-000.ps1").write_text('Write-Output "outside"\n', encoding="utf-8")
            harness_root = root / inventory.HARNESS_PARTS_ROOT
            harness_root.parent.mkdir(parents=True, exist_ok=True)
            try:
                harness_root.symlink_to(outside, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"directory symlink creation is unavailable: {exc}")
            original_glob = inventory.Path.glob

            def guarded_glob(path: Path, pattern: str):
                if path == harness_root:
                    raise AssertionError(f"unsafe harness source root glob attempted: {path}")
                return original_glob(path, pattern)

            with unittest.mock.patch.object(inventory.Path, "glob", guarded_glob):
                paths = inventory.harness_source_part_paths(root)

        self.assertEqual(paths, [])

    def test_manifest_paths_preserve_valid_repo_relative_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            self._write_manifest(root, "./project_sources/collector/source/DCOIR_Collector.ps1", [
                "project_sources\\collector\\source\\parts\\DCOIR_Collector.01_Core.ps1",
            ])
            paths = inventory.collector_manifest_paths(root)
        self.assertEqual(paths, [
            "project_sources/collector/source/DCOIR_Collector.ps1",
            "project_sources/collector/source/parts/DCOIR_Collector.01_Core.ps1",
        ])

    def test_manifest_paths_filter_unsafe_entries_before_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            self._write_manifest(root, "project_sources/collector/source/DCOIR_Collector.ps1", [
                "../outside.ps1",
                "/project_sources/collector/source/parts/DCOIR_Collector.01_Core.ps1",
                "C:\\outside\\collector.ps1",
                "\\\\server\\share\\collector.ps1",
                "",
            ])
            paths = inventory.collector_manifest_paths(root)
            manifest_error = inventory.manifest_error(root)
            expanded, expansion = inventory.expand_changed_files(root, [inventory.MANIFEST_PATH.as_posix()])
        self.assertEqual(paths, ["project_sources/collector/source/DCOIR_Collector.ps1"])
        self.assertIsNotNone(manifest_error)
        self.assertIn("collector_part_files[0]", manifest_error)
        self.assertIn("collector_part_files[1]", manifest_error)
        self.assertIn("collector_part_files[2]", manifest_error)
        self.assertIn("collector_part_files[3]", manifest_error)
        self.assertIn("collector_part_files[4]", manifest_error)
        self.assertIn("project_sources/collector/source/DCOIR_Collector.ps1", expanded)
        self.assertNotIn("../outside.ps1", expanded)
        self.assertNotIn("/project_sources/collector/source/parts/DCOIR_Collector.01_Core.ps1", expanded)
        self.assertNotIn("C:/outside/collector.ps1", expanded)
        self.assertNotIn("//server/share/collector.ps1", expanded)
        added_paths = expansion["rules"][0]["added_paths"]
        self.assertEqual(added_paths, ["project_sources/collector/source/DCOIR_Collector.ps1"])

    def test_manifest_wrapper_rejects_unsafe_input(self) -> None:
        cases = [
            "../outside.ps1",
            "/project_sources/collector/source/DCOIR_Collector.ps1",
            "C:\\outside\\collector.ps1",
            "C:outside\\collector.ps1",
            "\\\\server\\share\\collector.ps1",
            "",
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            for value in cases:
                with self.subTest(value=value):
                    self._write_manifest(root, value, [])
                    self.assertEqual(inventory.collector_manifest_paths(root), [])
                    self.assertIsNotNone(inventory.manifest_error(root))



if __name__ == "__main__":
    raise SystemExit(unittest.main())
