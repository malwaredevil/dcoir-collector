#!/usr/bin/env python3
"""Contract tests for the shared agent-runtime path-safety owner."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS_DIR))

from agent_runtime_path_safety import (
    UnsafePathError,
    resolve_contained_path,
    resolve_repo_path,
    validate_relative_path_syntax,
)


class ResolveContainedPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / 'root'
        self.root.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_link_or_skip(self, link: Path, target: Path | str) -> None:
        try:
            link.symlink_to(target, target_is_directory=Path(target).is_dir())
        except (NotImplementedError, OSError):
            self.skipTest('symlinks are not supported')

    def test_safe_relative_path_resolves_inside_root(self) -> None:
        nested = self.root / 'chunks' / 'part.txt'
        nested.parent.mkdir()
        nested.write_text('safe', encoding='utf-8')

        self.assertEqual(
            resolve_contained_path(self.root, 'chunks/part.txt', 'chunk path'),
            nested.resolve(),
        )

    def test_rejects_unsafe_syntax_under_posix_and_windows_rules(self) -> None:
        bad_values = [
            '',
            None,
            7,
            '../escape.txt',
            'nested/../../escape.txt',
            '..\\escape.txt',
            'nested\\..\\..\\escape.txt',
            '\\rooted.txt',
            'C:\\temp\\escape.txt',
            'C:escape.txt',
            'bad\x00name',
            'bad\nname',
            str(self.base.resolve() / 'absolute.txt'),
        ]
        for value in bad_values:
            with self.subTest(value=value), self.assertRaises(UnsafePathError):
                resolve_contained_path(self.root, value, 'manifest path')

    def test_root_itself_is_rejected_unless_allowed(self) -> None:
        for value in ('.', './', 'nested/..'):
            with self.subTest(value=value):
                if '..' not in value:
                    self.assertEqual(
                        resolve_contained_path(self.root, value, 'probe', allow_root=True),
                        self.root.resolve(),
                    )
                with self.assertRaises(UnsafePathError):
                    resolve_contained_path(self.root, value, 'probe')

    def test_symlink_escape_is_rejected(self) -> None:
        outside = self.base / 'outside'
        outside.mkdir()
        (outside / 'secret.txt').write_text('outside', encoding='utf-8')
        self.make_link_or_skip(self.root / 'escape', outside)

        with self.assertRaisesRegex(UnsafePathError, 'escapes its root'):
            resolve_contained_path(self.root, 'escape/secret.txt', 'chunk path')

    def test_symlink_loop_is_rejected(self) -> None:
        self.make_link_or_skip(self.root / 'loop', 'loop')

        with self.assertRaisesRegex(UnsafePathError, 'chunk path path could not be resolved'):
            resolve_contained_path(self.root, 'loop/file.txt', 'chunk path')

    def test_symlink_loop_in_root_is_rejected_before_path_resolution(self) -> None:
        loop_root = self.base / 'loop-root'
        self.make_link_or_skip(loop_root, 'loop-root')
        original_resolve = Path.resolve

        def leave_loop_unresolved(path: Path, *args: object, **kwargs: object) -> Path:
            if path == loop_root or loop_root in path.parents:
                return path.absolute()
            return original_resolve(path, *args, **kwargs)

        with patch.object(Path, 'resolve', leave_loop_unresolved):
            with self.assertRaisesRegex(
                UnsafePathError, 'chunk path root could not be resolved'
            ):
                resolve_contained_path(loop_root, 'file.txt', 'chunk path')

    def test_empty_value_message_names_the_expected_kind(self) -> None:
        with self.assertRaisesRegex(UnsafePathError, 'must be a non-empty filename-safe value'):
            validate_relative_path_syntax('', 'bundle_name', 'filename-safe value')


class ResolveRepoPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        (self.repo / 'docs').mkdir(parents=True)
        (self.repo / 'docs' / 'guide.md').write_text('guide', encoding='utf-8')

    def tearDown(self) -> None:
        self.temp.cleanup()

    def resolve(self, value: object, **kwargs: object) -> tuple[Path | None, list[str]]:
        errors: list[str] = []
        return resolve_repo_path(self.repo, value, 'probe', errors, **kwargs), errors

    def test_contained_path_resolves_without_errors(self) -> None:
        resolved, errors = self.resolve('docs/guide.md', required_root=self.repo / 'docs')
        self.assertEqual(resolved, (self.repo / 'docs' / 'guide.md').resolve())
        self.assertEqual(errors, [])

    def test_failures_are_collected_not_raised(self) -> None:
        with tempfile.TemporaryDirectory() as outside_dir:
            cases = [
                ({'value': '.'}, 'probe must name a path inside the repository, not the root itself'),
                ({'value': '../outside.md'}, 'probe must not be absolute or contain traversal'),
                ({'value': None}, 'probe must be a non-empty repository-relative path'),
                (
                    {'value': 'docs/guide.md', 'required_root': Path(outside_dir)},
                    'probe declared root escapes the repository',
                ),
                (
                    {'value': 'docs/guide.md', 'required_root': self.repo / 'other'},
                    'probe is outside its declared root',
                ),
            ]
            for kwargs, message in cases:
                with self.subTest(message=message):
                    resolved, errors = self.resolve(**kwargs)
                    self.assertIsNone(resolved)
                    self.assertEqual(len(errors), 1, errors)
                    self.assertIn(message, errors[0])

    def test_symlink_escape_and_loop_are_collected(self) -> None:
        outside = self.base / 'outside.txt'
        outside.write_text('outside', encoding='utf-8')
        try:
            (self.repo / 'escape').symlink_to(outside)
            (self.repo / 'loop').symlink_to('loop')
        except (NotImplementedError, OSError):
            self.skipTest('symlinks are not supported')

        resolved, errors = self.resolve('escape')
        self.assertIsNone(resolved)
        self.assertIn('probe escapes the repository', errors[0])

        resolved, errors = self.resolve('loop/file.md')
        self.assertIsNone(resolved)
        self.assertIn('probe path could not be resolved:', errors[0])


if __name__ == '__main__':
    unittest.main()
