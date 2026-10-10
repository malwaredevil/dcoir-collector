#!/usr/bin/env python3
"""Regression controls for the Code Review P1: inventory can omit new scripts."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from powershell_surface_inventory_test_cases.common import InventoryTestCase, write
from powershell_surface_inventory_outputs import build_inventory
from verify_powershell_surface_inventory_ci import verify_inventory


class PowerShellInventoryFreshnessTests(InventoryTestCase):
    def test_new_tracked_invoke_expression_tool_is_rejected_until_regenerated(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            subprocess.run(['git', 'init', '-q', str(root)], check=True, capture_output=True)
            subprocess.run(['git', '-C', str(root), 'add', '-A'], check=True, capture_output=True)
            inventory = root / 'inventory.json'
            inventory.write_text(json.dumps(build_inventory(root)), encoding='utf-8')
            self.assertEqual(verify_inventory(root, Path('inventory.json')), 0)

            # A genuine tracked, previously unlisted script bypassed the old scan.
            rel = '.github/scripts/new_operator_tool.ps1'
            write(root / rel, 'Invoke-Expression $untrusted\n')
            subprocess.run(['git', '-C', str(root), 'add', rel], check=True, capture_output=True)
            stale = json.loads(inventory.read_text())
            self.assertNotIn(rel, [s['path'] for s in stale['surfaces']])
            self.assertEqual(verify_inventory(root, Path('inventory.json')), 1)
            discovered = build_inventory(root)
            self.assertIn(rel, [s['path'] for s in discovered['surfaces']])
            inventory.write_text(json.dumps(discovered), encoding='utf-8')
            self.assertEqual(verify_inventory(root, Path('inventory.json')), 0)

    def test_modified_file_or_false_exclusion_is_rejected(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            inventory = root / 'inventory.json'
            record = build_inventory(root)
            inventory.write_text(json.dumps(record), encoding='utf-8')
            self.assertEqual(verify_inventory(root, Path('inventory.json')), 0)
            rel = '.github/operator_tools/sample/Invoke-DcoirSample.ps1'
            write(root / rel, "Invoke-Expression 'bad'\n")
            self.assertEqual(verify_inventory(root, Path('inventory.json')), 1)
            updated = build_inventory(root)
            next(s for s in updated['surfaces'] if s['path'] == rel)['inclusion_decision'] = 'exclude'
            inventory.write_text(json.dumps(updated), encoding='utf-8')
            self.assertEqual(verify_inventory(root, Path('inventory.json')), 1)

    def test_nonsemantic_runner_metadata_does_not_invalidate_source_evidence(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            doc = build_inventory(root)
            doc['discovery_command'] = 'CI checkout context can differ by runner'
            doc['source_of_truth'] = 'different checkout discovery label'
            doc['controls'] = {'diagnostic_metadata': 'not a source fact'}
            inventory = root / 'inventory.json'
            inventory.write_text(json.dumps(doc), encoding='utf-8')
            self.assertEqual(verify_inventory(root, Path('inventory.json')), 0)
            doc['summary']['total_surfaces'] = 9999
            inventory.write_text(json.dumps(doc), encoding='utf-8')
            self.assertEqual(verify_inventory(root, Path('inventory.json')), 1)

    def test_line_endings_only_are_stable(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            inventory = root / 'inventory.json'
            inventory.write_text(json.dumps(build_inventory(root)), encoding='utf-8')
            rel = '.github/operator_tools/sample/Invoke-DcoirSample.ps1'
            path = root / rel
            path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
            self.assertEqual(verify_inventory(root, Path('inventory.json')), 0)

    def test_existing_analyzer_action_checks_freshness_before_scanning(self) -> None:
        action = Path(__file__).resolve().parents[3] / '.github/actions/run-psscriptanalyzer/action.yml'
        contents = action.read_text(encoding='utf-8')
        gate = contents.index('verify_powershell_surface_inventory_ci.py')
        analyzer = contents.index('run_powershell_analyzer.py')
        self.assertLess(gate, analyzer)
        self.assertIn('refusing partial analysis', contents)

    def test_invalid_baseline_and_invalid_current_inventory_fail_closed(self) -> None:
        with self.make_minimal_repo() as temp:
            root = Path(temp)
            inventory = root / 'inventory.json'
            current = build_inventory(root)
            current['validation']['success'] = False
            inventory.write_text(json.dumps(current), encoding='utf-8')
            self.assertEqual(verify_inventory(root, Path('inventory.json')), 1)
            current['validation']['success'] = True
            inventory.write_text(json.dumps(current), encoding='utf-8')
            (root / 'project_sources/collector/source/DCOIR_Collector.ps1').unlink()
            self.assertEqual(verify_inventory(root, Path('inventory.json')), 1)


if __name__ == '__main__':
    unittest.main()
