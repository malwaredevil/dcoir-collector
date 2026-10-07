#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import powershell_assembly_parity_builders as _builders
import powershell_assembly_parity_cli as _cli
import powershell_assembly_parity_common as _common
import powershell_assembly_parity_parsing as _parsing
from powershell_assembly_parity_test_support import PowerShellAssemblyParityTestCase, parity, write


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

    def test_facade_reexports_canonical_owners(self) -> None:
        self.assertIs(parity.build_report, _cli.build_report)
        self.assertIs(parity.main, _cli.main)
        self.assertIs(parity.build_collector_output, _builders.build_collector_output)
        self.assertIs(parity.build_harness_output, _builders.build_harness_output)
        self.assertIs(parity.parse_powershell_text, _parsing.parse_powershell_text)
        self.assertIs(parity.part_entry, _common.part_entry)

    def test_inventory_source_part_growth_fails(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            write(
                root
                / "project_sources/collector/harness/source/parts/run_DCOIR_Tests.part-001.ps1",
                'function Invoke-SecondHarnessPart { Write-Output "ok" }\n',
            )
            report, errors, _warnings = parity.build_report(self.args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(
            any(
                "harness source-part map does not match inventory controls: 2 != 1"
                in error
                for error in errors
            ),
            errors,
        )

    def test_inventory_source_part_shrink_fails(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            inventory_path = root / parity.DEFAULT_INVENTORY
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["controls"]["harness_source_parts"]["part_count"] = 2
            write(inventory_path, json.dumps(inventory, indent=2) + "\n")
            report, errors, _warnings = parity.build_report(self.args(root))

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(
            any(
                "harness source-part map does not match inventory controls: 1 != 2"
                in error
                for error in errors
            ),
            errors,
        )

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

