#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import build_powershell_surface_inventory as inventory_builder
from powershell_assembly_parity_test_support import PowerShellAssemblyParityTestCase, parity


# Deliberate change detectors: adding or removing a collector or harness source part
# must update these pins alongside the regenerated inventory and parity evidence.
EXPECTED_COLLECTOR_SOURCE_PARTS = 43
EXPECTED_HARNESS_SOURCE_PARTS = 18


class PowerShellAssemblyParityRealRepoTests(PowerShellAssemblyParityTestCase):
    def test_real_repo_contract_passes(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]

        # The parity CLI only accepts repository-relative inputs, so the fresh
        # inventory lives under the git-ignored project_sources/validation/out_*/.
        with tempfile.TemporaryDirectory(
            dir=repo_root / "project_sources/validation",
            prefix="out_assembly_parity_fresh_inventory_",
        ) as temp:
            temp_root = Path(temp)
            inventory_rel = (temp_root / "inventory.json").relative_to(repo_root)
            inventory_md_rel = (temp_root / "inventory.md").relative_to(repo_root)
            inventory = inventory_builder.build_inventory(
                repo_root,
                json_output=inventory_rel,
                markdown_output=inventory_md_rel,
            )
            self.assertTrue(
                inventory["validation"]["success"],
                inventory["validation"]["errors"],
            )
            (repo_root / inventory_rel).write_text(
                json.dumps(inventory, indent=2) + "\n",
                encoding="utf-8",
            )

            report, errors, _warnings = parity.build_report(
                self.args(repo_root, inventory=inventory_rel.as_posix())
            )

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(
            report["summary"]["collector_source_part_count"],
            EXPECTED_COLLECTOR_SOURCE_PARTS,
        )
        self.assertEqual(
            report["summary"]["harness_source_part_count"],
            EXPECTED_HARNESS_SOURCE_PARTS,
        )
        self.assertEqual(report["summary"]["generated_output_count"], 2)
        self.assertEqual(report["summary"]["parse_status"], "pass")
        self.assertEqual(report["summary"]["parity_status"], "pass")

        # The checked-in inventory is what the analyzer, custom checks and
        # review-assist consume, so it must agree with the fresh one too.
        checked_report, checked_errors, _warnings = parity.build_report(
            self.args(repo_root)
        )
        self.assertEqual(checked_errors, [])
        self.assertTrue(checked_report["validation"]["success"])
        checked_inventory = json.loads(
            (repo_root / parity.DEFAULT_INVENTORY).read_text(encoding="utf-8")
        )
        self.assertEqual(
            self.control_paths(checked_inventory),
            self.control_paths(inventory),
            f"{parity.DEFAULT_INVENTORY.as_posix()} is stale; regenerate it with "
            "build_powershell_surface_inventory.py",
        )

    @staticmethod
    def control_paths(inventory: dict) -> dict[str, list[str]]:
        controls = inventory["controls"]
        return {
            "collector_manifest": [
                entry["path"] for entry in controls["collector_manifest"]["paths"]
            ],
            "harness_source_parts": [
                entry["path"] for entry in controls["harness_source_parts"]["parts"]
            ],
        }
