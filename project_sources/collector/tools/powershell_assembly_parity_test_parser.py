#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from powershell_assembly_parity_test_support import PowerShellAssemblyParityTestCase, parity, write


class PowerShellAssemblyParityParserTests(PowerShellAssemblyParityTestCase):
    def test_missing_source_output_mapping_fails(self) -> None:
        with self.make_repo(manifest_parts=[]) as temp:
            report, errors, _warnings = parity.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("collector_part_files must be a non-empty list" in error for error in errors))
        self.assertTrue(any("source/output mapping is missing" in error for error in errors))

    def test_generated_output_parse_failure_fails(self) -> None:
        with self.make_repo(collector_part_text="function Broken {\n") as temp:
            report, errors, _warnings = parity.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("generated output parse check failed" in error for error in errors))

    def test_native_parser_uses_file_argument_for_temp_path(self) -> None:
        captured: dict[str, list[str]] = {}

        class Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake_run(command: list[str], **_kwargs: object) -> Completed:
            captured["command"] = command
            parser_path = Path(command[-2])
            target_path = Path(command[-1])
            self.assertTrue(parser_path.is_file())
            self.assertTrue(target_path.is_file())
            self.assertIn("Parser]::ParseFile", parser_path.read_text(encoding="utf-8"))
            self.assertEqual(target_path.read_text(encoding="utf-8"), 'Write-Output "ok"\n')
            return Completed()

        original_which = parity.shutil.which
        original_run = parity.subprocess.run
        try:
            parity.shutil.which = lambda _name: "pwsh"
            parity.subprocess.run = fake_run
            report = parity.parse_powershell_text('Write-Output "ok"\n')
        finally:
            parity.shutil.which = original_which
            parity.subprocess.run = original_run

        command = captured["command"]
        self.assertEqual(report["method"], "powershell_language_parser")
        self.assertTrue(report["success"])
        self.assertIn("-File", command)
        self.assertNotIn("-Command", command)
        self.assertFalse(Path(command[-2]).exists())
        self.assertFalse(Path(command[-1]).exists())

    def test_native_parser_reports_temp_cleanup_failure(self) -> None:
        captured_paths: list[Path] = []

        class Completed:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake_run(command: list[str], **_kwargs: object) -> Completed:
            captured_paths.extend([Path(command[-2]), Path(command[-1])])
            return Completed()

        original_which = parity.shutil.which
        original_run = parity.subprocess.run
        original_unlink = parity.Path.unlink

        def fail_unlink(path: Path, *args: object, **kwargs: object) -> None:
            if path in captured_paths:
                raise OSError("locked")
            original_unlink(path, *args, **kwargs)

        try:
            parity.shutil.which = lambda _name: "pwsh"
            parity.subprocess.run = fake_run
            parity.Path.unlink = fail_unlink
            report = parity.parse_powershell_text('Write-Output "ok"\n')
        finally:
            parity.shutil.which = original_which
            parity.subprocess.run = original_run
            parity.Path.unlink = original_unlink
            for path in captured_paths:
                if path.exists():
                    path.unlink()

        self.assertFalse(report["success"])
        self.assertTrue(
            any("failed to remove temporary PowerShell" in error for error in report["errors"])
        )

    def test_baseline_shrink_without_exception_fails(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            baseline = {
                "schema_version": parity.SCHEMA_VERSION,
                "summary": {
                    "collector_source_part_count": 2,
                    "harness_source_part_count": 1,
                    "source_part_count": 3,
                    "generated_output_count": 2,
                },
            }
            baseline_path = root / "baseline.json"
            write(baseline_path, json.dumps(baseline, indent=2) + "\n")
            report, errors, _warnings = parity.build_report(
                self.args(root, baseline_report="baseline.json")
            )

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("unexpectedly shrank without approved exception" in error for error in errors))
