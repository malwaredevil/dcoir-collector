#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gemini_bundle_path_safety import GeminiBundlePathError, resolve_contained_path


class GeminiBundlePathSafetyTests(unittest.TestCase):
    def test_safe_relative_path_resolves_inside_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'bundle'
            nested = root / 'chunks' / 'part.txt'
            nested.parent.mkdir(parents=True)
            nested.write_text('safe', encoding='utf-8')

            resolved = resolve_contained_path(
                root, 'chunks/part.txt', 'chunk path'
            )

            self.assertEqual(resolved, nested.resolve())

    def test_rejects_empty_non_string_absolute_and_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'bundle'
            root.mkdir()
            bad_values = [
                '',
                None,
                7,
                '../escape.txt',
                'nested/../../escape.txt',
                str(Path(td).resolve() / 'absolute.txt'),
            ]
            for value in bad_values:
                with self.subTest(value=value):
                    with self.assertRaises(GeminiBundlePathError):
                        resolve_contained_path(root, value, 'manifest path')

    def test_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / 'bundle'
            outside = base / 'outside'
            root.mkdir()
            outside.mkdir()
            (outside / 'secret.txt').write_text('outside', encoding='utf-8')
            (root / 'escape').symlink_to(outside, target_is_directory=True)

            with self.assertRaisesRegex(
                GeminiBundlePathError, 'escapes its root'
            ):
                resolve_contained_path(
                    root, 'escape/secret.txt', 'chunk path'
                )

    def test_rejects_symlink_loop(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'bundle'
            root.mkdir()
            (root / 'loop').symlink_to('loop')

            with self.assertRaises(GeminiBundlePathError):
                resolve_contained_path(root, 'loop/file.txt', 'chunk path')


if __name__ == '__main__':
    unittest.main()
