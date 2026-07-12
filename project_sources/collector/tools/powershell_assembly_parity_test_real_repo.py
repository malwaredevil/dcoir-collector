#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from powershell_assembly_parity_test_support import PowerShellAssemblyParityTestCase, parity


class PowerShellAssemblyParityRealRepoTests(PowerShellAssemblyParityTestCase):
    def test_real_repo_contract_passes(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        report, errors, _warnings = parity.build_report(self.args(repo_root))

        self.assertEqual(errors, [])
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(report["summary"]["collector_source_part_count"], 43)
        self.assertEqual(report["summary"]["harness_source_part_count"], 17)
        self.assertEqual(report["summary"]["generated_output_count"], 2)
        self.assertEqual(report["summary"]["parse_status"], "pass")
        self.assertEqual(report["summary"]["parity_status"], "pass")
