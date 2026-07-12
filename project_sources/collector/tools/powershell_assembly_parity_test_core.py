#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from powershell_assembly_parity_test_support import PowerShellAssemblyParityTestCase, parity


class PowerShellAssemblyParityCoreTests(PowerShellAssemblyParityTestCase):
    def test_clean_control_passes_and_maps_counts(self) -> None:
        with self.make_repo(checked_in_harness_text='function Invoke-HarnessPart { Write-Output "ok" }\n') as temp:
            report, errors, warnings = parity.build_report(self.args(Path(temp)))

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertTrue(warnings)
        self.assertEqual(report["summary"]["collector_source_part_count"], 1)
        self.assertEqual(report["summary"]["harness_source_part_count"], 1)
        self.assertEqual(report["summary"]["generated_output_count"], 2)
        self.assertEqual(report["summary"]["parse_status"], "pass")
        self.assertEqual(report["summary"]["parity_status"], "pass")
        self.assertTrue(all(output["line_mapping"] for output in report["generated_outputs"]))

    def test_stale_checked_in_generated_output_fails(self) -> None:
        with self.make_repo(checked_in_harness_text='Write-Output "stale"\n') as temp:
            report, errors, _warnings = parity.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("checked-in generated harness is stale" in error for error in errors))

    def test_missing_source_part_fails(self) -> None:
        missing = "project_sources/collector/source/parts/DCOIR_Collector.99_Missing.ps1"
        with self.make_repo(manifest_parts=[missing]) as temp:
            report, errors, _warnings = parity.build_report(self.args(Path(temp)))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("collector source part is missing" in error for error in errors))

