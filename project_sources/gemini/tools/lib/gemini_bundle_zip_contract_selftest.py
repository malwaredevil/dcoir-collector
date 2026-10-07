#!/usr/bin/env python3
"""Regression tests for the Gemini delivery-zip identity and contract owner."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

from lib.gemini_bundle_zip_contract import (
    COMPILE_REPORT_NAME,
    BundleZipContractError,
    compiled_zip_path,
    inspect_bundle_zip,
)

PRIME = '01_GEMINI_AGENT_BUILD/Prime.md.txt'
MANIFEST = {
    'topology': {'prime_agent_file': PRIME},
    'source_only_files': ['notes/internal.md.txt'],
    'source_only_dirs': ['01_GEMINI_AGENT_BUILD/prime_agent_chunks'],
}


def write_zip(path: Path, members: list[str]) -> Path:
    with zipfile.ZipFile(path, 'w') as archive:
        for member in members:
            archive.writestr(member, 'x')
    return path


class CompiledZipPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def report(self, value: object) -> None:
        (self.out / COMPILE_REPORT_NAME).write_text(json.dumps(value), encoding='utf-8')

    def test_returns_compiled_zip_even_when_a_stale_zip_sorts_later(self) -> None:
        stale = write_zip(self.out / 'Bundle_3_0_5.zip', [f'B/{PRIME}'])
        fresh = write_zip(self.out / 'Bundle_3_0_10.zip', [f'B/{PRIME}'])
        self.assertGreater(stale.name, fresh.name)
        self.report({'zip_path': str(fresh), 'bundle_name': 'Bundle', 'bundle_version': '3_0_10'})

        self.assertEqual(compiled_zip_path(self.out), fresh)

    def test_missing_or_unusable_report_fails_closed(self) -> None:
        cases = [
            (None, 'could not be read'),
            ('{not json', 'could not be read'),
            ({}, 'does not report a zip_path'),
            ({'zip_path': ''}, 'does not report a zip_path'),
            (
                {'zip_path': str(self.out / 'Bundle_1.zip'), 'bundle_name': 'Bundle', 'bundle_version': '1'},
                'compiled delivery zip is missing',
            ),
            (
                {'zip_path': str(self.out / 'Other_1.zip'), 'bundle_name': 'Bundle', 'bundle_version': '1'},
                'does not match the reported bundle identity',
            ),
            (
                {'zip_path': str(self.out.parent / 'Bundle_1.zip'), 'bundle_name': 'Bundle', 'bundle_version': '1'},
                'not in the build output directory',
            ),
        ]
        for value, message in cases:
            with self.subTest(message=message, value=value):
                report_path = self.out / COMPILE_REPORT_NAME
                report_path.unlink(missing_ok=True)
                if isinstance(value, str):
                    report_path.write_text(value, encoding='utf-8')
                elif value is not None:
                    self.report(value)
                with self.assertRaisesRegex(BundleZipContractError, message):
                    compiled_zip_path(self.out)


class InspectBundleZipTests(unittest.TestCase):
    def inspect(self, members: list[str]) -> dict:
        with tempfile.TemporaryDirectory() as td:
            return inspect_bundle_zip(write_zip(Path(td) / 'b.zip', members), MANIFEST)

    def test_exactly_one_prime_and_no_leaks_passes(self) -> None:
        result = self.inspect([f'B/{PRIME}', 'B/00_START_HERE/Quick.md.txt'])
        self.assertTrue(result['success'], result)
        self.assertEqual(result['entry_count'], 2)

    def test_missing_duplicate_prime_and_leaks_fail(self) -> None:
        cases = {
            'missing prime': ['B/00_START_HERE/Quick.md.txt'],
            'duplicate prime': [f'B/{PRIME}', f'C/{PRIME}'],
            'source-only file': [f'B/{PRIME}', 'B/notes/internal.md.txt'],
            'source-only dir': [f'B/{PRIME}', 'B/01_GEMINI_AGENT_BUILD/prime_agent_chunks/c1.md.txt'],
        }
        for label, members in cases.items():
            with self.subTest(label=label):
                self.assertFalse(self.inspect(members)['success'])

    def test_unreadable_zip_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / 'bad.zip'
            bad.write_bytes(b'not a zip')
            with self.assertRaisesRegex(BundleZipContractError, 'could not be read'):
                inspect_bundle_zip(bad, MANIFEST)


if __name__ == '__main__':
    unittest.main()
