#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import build_powershell_surface_inventory as inventory_builder
from powershell_assembly_parity_test_support import PowerShellAssemblyParityTestCase, parity


class PowerShellAssemblyParityRealRepoTests(PowerShellAssemblyParityTestCase):
    def test_real_repo_contract_passes(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]

        with tempfile.TemporaryDirectory(
            dir=repo_root / "project_sources/collector",
            prefix=".assembly-parity-fresh-inventory-",
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

        expected_harness_parts = inventory["controls"]["harness_source_parts"][
            "part_count"
        ]
        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["collector_source_part_count"], 43)
        self.assertEqual(
            report["summary"]["harness_source_part_count"],
            expected_harness_parts,
        )
        self.assertEqual(report["summary"]["generated_output_count"], 2)
        self.assertEqual(report["summary"]["parse_status"], "pass")
        self.assertEqual(report["summary"]["parity_status"], "pass")
