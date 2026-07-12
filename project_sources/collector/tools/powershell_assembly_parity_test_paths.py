#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import unittest.mock
from pathlib import Path

from powershell_assembly_parity_test_support import PowerShellAssemblyParityTestCase, parity, write


class PowerShellAssemblyParityPathSafetyTests(PowerShellAssemblyParityTestCase):
    def assert_manifest_path_rejected(
        self,
        *,
        expected_error_fragment: str,
        manifest_wrapper: str | None = None,
        manifest_parts: list[str] | None = None,
    ) -> None:
        with self.make_repo(manifest_wrapper=manifest_wrapper, manifest_parts=manifest_parts) as temp:
            report, errors, _warnings = parity.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any(expected_error_fragment in error for error in errors), errors)

    def test_literal_dot_slash_manifest_paths_pass(self) -> None:
        wrapper = "project_sources/collector/source/DCOIR_Collector.ps1"
        collector_part = "project_sources/collector/source/parts/DCOIR_Collector.01_Core.ps1"
        with self.make_repo(
            manifest_wrapper="./" + wrapper,
            manifest_parts=["./" + collector_part],
            checked_in_harness_text='function Invoke-HarnessPart { Write-Output "ok" }\n',
        ) as temp:
            report, errors, _warnings = parity.build_report(self.args(Path(temp)))

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["collector_source_part_count"], 1)

    def test_absolute_collector_wrapper_path_fails_before_normalization(self) -> None:
        self.assert_manifest_path_rejected(
            manifest_wrapper="/project_sources/collector/source/DCOIR_Collector.ps1",
            expected_error_fragment="collector manifest: collector_wrapper_source must be a repo-relative path without traversal",
        )

    def test_parent_traversal_collector_wrapper_path_fails_before_normalization(self) -> None:
        self.assert_manifest_path_rejected(
            manifest_wrapper="../project_sources/collector/source/DCOIR_Collector.ps1",
            expected_error_fragment="collector manifest: collector_wrapper_source must be a repo-relative path without traversal",
        )

    def test_absolute_collector_part_path_fails_before_normalization(self) -> None:
        self.assert_manifest_path_rejected(
            manifest_parts=["/project_sources/collector/source/parts/DCOIR_Collector.01_Core.ps1"],
            expected_error_fragment="collector manifest: collector_part_files[1] must be a repo-relative path without traversal",
        )

    def test_windows_parent_traversal_collector_part_path_fails_before_normalization(self) -> None:
        unsafe_part = "..\\project_sources\\collector\\source\\parts\\DCOIR_Collector.01_Core.ps1"
        self.assert_manifest_path_rejected(
            manifest_parts=[unsafe_part],
            expected_error_fragment="collector manifest: collector_part_files[1] must be a repo-relative path without traversal",
        )

    def test_unsafe_manifest_paths_do_not_reach_part_entry_or_file_facts(self) -> None:
        scenarios = [
            {
                "name": "absolute wrapper",
                "manifest_wrapper": "ABSOLUTE_WRAPPER",
                "manifest_parts": None,
                "symlink_part": False,
                "expected_fragment": "repo-relative path without traversal",
            },
            {
                "name": "drive-qualified wrapper",
                "manifest_wrapper": "C:outside/wrapper.ps1",
                "manifest_parts": None,
                "symlink_part": False,
                "expected_fragment": "repo-relative path without traversal",
            },
            {
                "name": "parent traversal part",
                "manifest_wrapper": None,
                "manifest_parts": ["../outside_part.ps1"],
                "symlink_part": False,
                "expected_fragment": "repo-relative path without traversal",
            },
            {
                "name": "symlink part escape",
                "manifest_wrapper": None,
                "manifest_parts": ["project_sources/collector/source/parts/outside_link.ps1"],
                "symlink_part": True,
                "expected_fragment": "resolve inside the repository root",
            },
        ]
        for scenario in scenarios:
            with self.subTest(scenario=scenario["name"]):
                with self.make_repo(
                    manifest_wrapper=None if scenario["manifest_wrapper"] == "ABSOLUTE_WRAPPER" else scenario["manifest_wrapper"],
                    manifest_parts=scenario["manifest_parts"],
                ) as temp:
                    root = Path(temp).resolve()
                    outside_wrapper = root.parent / "outside_wrapper.ps1"
                    outside_part = root.parent / "outside_part.ps1"
                    write(outside_wrapper, 'function Invoke-OutsideWrapper { Write-Output "outside" }\n')
                    write(outside_part, 'function Invoke-OutsidePart { Write-Output "outside" }\n')
                    if scenario["manifest_wrapper"] == "ABSOLUTE_WRAPPER":
                        manifest_path = root / parity.DEFAULT_MANIFEST
                        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                        manifest["collector_wrapper_source"] = outside_wrapper.as_posix()
                        write(manifest_path, json.dumps(manifest, indent=2) + "\n")
                    if scenario["symlink_part"]:
                        link = root / "project_sources/collector/source/parts/outside_link.ps1"
                        try:
                            link.unlink(missing_ok=True)
                            link.symlink_to(outside_part)
                        except (NotImplementedError, OSError) as exc:
                            self.skipTest(f"symlink creation is unavailable: {exc}")
                    original_part_entry = parity.part_entry
                    original_file_facts = parity.file_facts

                    def assert_repo_contained(path: Path) -> None:
                        try:
                            path.resolve().relative_to(root)
                        except ValueError as exc:
                            raise AssertionError(f"unsafe source fact collection attempted: {path}") from exc

                    def guarded_part_entry(path: Path, repo_root: Path) -> dict[str, object]:
                        assert_repo_contained(path)
                        return original_part_entry(path, repo_root)

                    def guarded_file_facts(path: Path, repo_root: Path) -> dict[str, object]:
                        assert_repo_contained(path)
                        return original_file_facts(path, repo_root)

                    with unittest.mock.patch.object(parity, "part_entry", side_effect=guarded_part_entry), unittest.mock.patch.object(parity, "file_facts", side_effect=guarded_file_facts):
                        report, errors, _warnings = parity.build_report(self.args(root))

                self.assertFalse(report["validation"]["success"])
                self.assertTrue(any(scenario["expected_fragment"] in error for error in errors), errors)

    def test_symlinked_harness_part_root_fails_before_glob_or_read(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp).resolve()
            outside = root.parent / "outside_harness_parts"
            write(outside / "run_DCOIR_Tests.part-000.ps1.txt", 'function Invoke-OutsideHarnessRoot { Write-Output "outside" }\n')
            harness_root = root / parity.HARNESS_PARTS_ROOT
            try:
                shutil.rmtree(harness_root)
                harness_root.symlink_to(outside, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"directory symlink creation is unavailable: {exc}")
            original_glob = parity.Path.glob

            def guarded_glob(path: Path, pattern: str):
                if path == harness_root:
                    raise AssertionError(f"unsafe harness source root glob attempted: {path}")
                return original_glob(path, pattern)

            with unittest.mock.patch.object(parity.Path, "glob", guarded_glob):
                report, errors, _warnings = parity.build_report(self.args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("harness source parts root must resolve inside the repository root" in error for error in errors), errors)

    def test_symlinked_harness_part_fails_before_part_entry_or_read(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp).resolve()
            outside = root.parent / "outside_harness_part.ps1.txt"
            write(outside, 'function Invoke-OutsideHarness { Write-Output "outside" }\n')
            harness_link = root / "project_sources/collector/harness/source/parts/run_DCOIR_Tests.part-000.ps1.txt"
            try:
                harness_link.unlink()
                harness_link.symlink_to(outside)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")
            original_part_entry = parity.part_entry
            original_read_part_text = parity.read_part_text

            def assert_repo_contained(path: Path) -> None:
                try:
                    path.resolve().relative_to(root)
                except ValueError as exc:
                    raise AssertionError(f"unsafe harness source read attempted: {path}") from exc

            def guarded_part_entry(path: Path, repo_root: Path) -> dict[str, object]:
                assert_repo_contained(path)
                return original_part_entry(path, repo_root)

            def guarded_read_part_text(path: Path) -> str:
                assert_repo_contained(path)
                return original_read_part_text(path)

            with unittest.mock.patch.object(parity, "part_entry", side_effect=guarded_part_entry), unittest.mock.patch.object(parity, "read_part_text", side_effect=guarded_read_part_text):
                report, errors, _warnings = parity.build_report(self.args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("harness source part must resolve inside the repository root" in error for error in errors), errors)
