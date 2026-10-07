#!/usr/bin/env python3
"""Regression tests for delivery-zip identity in surface_delivery_zip.py."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import surface_delivery_zip


class FindZipPathTests(unittest.TestCase):
    def test_uses_only_the_top_level_zip_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            delivered = Path(td) / 'Bundle_3_0_10.zip'
            nested = Path(td) / 'Bundle_3_0_5.zip'
            delivered.write_bytes(b'')
            nested.write_bytes(b'')
            report = {
                'zip_path': str(delivered),
                'steps': [{'report': {'zip_path': str(nested)}}],
            }

            self.assertEqual(surface_delivery_zip.find_zip_path(report), delivered)

    def test_nested_zip_paths_are_never_a_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            nested = Path(td) / 'Bundle_3_0_5.zip'
            nested.write_bytes(b'')
            cases = [
                ({'steps': [{'report': {'zip_path': str(nested)}}]}, 'no top-level zip_path'),
                ({'zip_path': str(Path(td) / 'missing.zip')}, 'does not exist'),
            ]
            for report, message in cases:
                with self.subTest(message=message):
                    with self.assertRaisesRegex(SystemExit, message):
                        surface_delivery_zip.find_zip_path(report)


if __name__ == '__main__':
    unittest.main()
