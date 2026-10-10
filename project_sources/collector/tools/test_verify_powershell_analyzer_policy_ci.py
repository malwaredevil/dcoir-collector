#!/usr/bin/env python3
"""Checks the native CI policy proof does not mistake a skipped bad rule for success."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from verify_powershell_analyzer_policy_ci import RULE, verify_policy

ROOT = Path(__file__).resolve().parents[3]


class NativePolicyFixtureTests(unittest.TestCase):
    def fake_analyzer(self, *, suppress_bad_finding: bool = False):
        observed: list[str] = []

        def run(command, *, input, **_kwargs):
            request = json.loads(input)
            target = request['target']
            source = Path(target['analysis_path']).read_text(encoding='utf-8')
            observed.append(target['path'])
            bad = 'Invoke-Expression' in source
            findings = []
            if bad and not suppress_bad_finding:
                findings.append({
                    'path': target['analysis_path'], 'line': 2, 'column': 11,
                    'rule_name': RULE, 'severity': 'Warning',
                    'observed_problem': 'Avoid Invoke-Expression',
                    'recommended_fix': 'Use a bounded command interface',
                })
            response = {
                'analyzer_name': 'FakePSScriptAnalyzer', 'analyzer_version': '1.25.0',
                'powershell_engine': 'Core', 'powershell_version': '7.6.6',
                'target_path': target['path'], 'analyzed': True, 'findings': findings,
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(response), '')
        return run, observed

    def test_bad_fixture_blocks_and_safe_control_passes(self):
        fake, seen = self.fake_analyzer()
        with patch('powershell_analyzer_execution.subprocess.run', side_effect=fake):
            verify_policy(ROOT, analyzer_command=[sys.executable, 'fake-native-analyzer'])
        self.assertEqual(len(seen), 2)
        self.assertTrue(seen[0].endswith('bad/invoke_expression.ps1'))
        self.assertTrue(seen[1].endswith('safe_control.ps1'))

    def test_skipped_bad_rule_fails_closed(self):
        fake, seen = self.fake_analyzer(suppress_bad_finding=True)
        with patch('powershell_analyzer_execution.subprocess.run', side_effect=fake):
            with self.assertRaisesRegex(RuntimeError, 'failed to produce blocking'):
                verify_policy(ROOT, analyzer_command=[sys.executable, 'fake-native-analyzer'])
        self.assertEqual(len(seen), 1)


if __name__ == '__main__':
    unittest.main()
