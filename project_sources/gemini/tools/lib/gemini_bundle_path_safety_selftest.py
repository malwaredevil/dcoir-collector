#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gemini_bundle_path_safety import (
    UnsafePathError,
    resolve_contained_path,
    validate_bundle_identity,
    validate_bundle_identity_component,
    validate_manifest_paths,
)


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
                '..\\escape.txt',
                'nested\\..\\..\\escape.txt',
                '\\rooted.txt',
                'C:\\temp\\escape.txt',
                'C:escape.txt',
                'bad\x00name',
                str(Path(td).resolve() / 'absolute.txt'),
                '.',
                './',
                'nested/..',
            ]
            for value in bad_values:
                with self.subTest(value=value):
                    with self.assertRaises(UnsafePathError):
                        resolve_contained_path(root, value, 'manifest path')

    def test_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / 'bundle'
            outside = base / 'outside'
            root.mkdir()
            outside.mkdir()
            (outside / 'secret.txt').write_text('outside', encoding='utf-8')
            try:
                (root / 'escape').symlink_to(outside, target_is_directory=True)
            except (NotImplementedError, OSError):
                self.skipTest('symlinks are not supported')

            with self.assertRaisesRegex(
                UnsafePathError, 'escapes its root'
            ):
                resolve_contained_path(
                    root, 'escape/secret.txt', 'chunk path'
                )

    def test_rejects_symlink_loop(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'bundle'
            root.mkdir()
            try:
                (root / 'loop').symlink_to('loop')
            except (NotImplementedError, OSError):
                self.skipTest('symlinks are not supported')

            with self.assertRaises(UnsafePathError):
                resolve_contained_path(root, 'loop/file.txt', 'chunk path')

    def test_manifest_container_shape_errors_are_structured(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source_root = base / 'bundle'
            repo_root = base / 'repo'
            source_root.mkdir()
            repo_root.mkdir()
            cases = [
                ({'required_files': None}, 'required_files must be a list'),
                (
                    {'knowledge_attachment_sources': 7},
                    'knowledge_attachment_sources must be a list',
                ),
                (
                    {'topology': {'sub_agent_files': None}},
                    'topology.sub_agent_files must be a list',
                ),
                (
                    {'topology': {'prime_agent_chunk_sources': 7}},
                    'topology.prime_agent_chunk_sources must be a list',
                ),
                ({'topology': None}, 'topology must be an object'),
            ]
            for manifest, marker in cases:
                with self.subTest(marker=marker):
                    errors = validate_manifest_paths(
                        manifest,
                        source_root,
                        repo_root,
                    )
                    self.assertTrue(
                        any(marker in error for error in errors),
                        errors,
                    )

            self.assertEqual(
                validate_manifest_paths([], source_root, repo_root),
                ['Gemini bundle manifest must be an object'],
            )

    def test_chunk_manifest_shape_and_read_errors_are_structured(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source_root = base / 'bundle'
            repo_root = base / 'repo'
            source_root.mkdir()
            repo_root.mkdir()
            chunk_manifest = source_root / 'chunks.json'
            manifest = {'prime_agent_chunk_manifest': 'chunks.json'}
            cases = [
                (b'[]', 'must contain a JSON object'),
                (b'{"chunks": 5}', 'prime_agent_chunk_manifest.chunks must be a list'),
                (b'{', 'JSONDecodeError'),
                (b'\xff', 'UnicodeDecodeError'),
            ]
            for raw, marker in cases:
                with self.subTest(marker=marker):
                    chunk_manifest.write_bytes(raw)
                    errors = validate_manifest_paths(
                        manifest,
                        source_root,
                        repo_root,
                    )
                    self.assertTrue(
                        any(marker in error for error in errors),
                        errors,
                    )

    def test_bundle_identity_component_accepts_safe_values(self) -> None:
        for value in (
            'DCOIR_Gemini_Email_Build_Bundle',
            '3_0_5',
            'release-1.2.3',
        ):
            with self.subTest(value=value):
                self.assertEqual(
                    validate_bundle_identity_component(value, 'bundle identity'),
                    value,
                )

    def test_bundle_identity_component_rejects_cross_platform_escapes(self) -> None:
        bad_values = [
            '',
            None,
            '.',
            '..',
            '../escaped',
            '..\\escaped',
            '/tmp/escaped',
            'C:\\temp\\escaped',
            'C:escaped',
            'nested/name',
            'nested\\name',
            'bad:name',
            'bad|name',
            'bad?name',
            'bad*name',
            'bad\x00name',
            'trailing.',
            'trailing ',
            'CON',
            'nul.tar',
            'Com1',
            'LPT9.zip',
        ]
        for value in bad_values:
            with self.subTest(value=value):
                with self.assertRaises(UnsafePathError):
                    validate_bundle_identity_component(
                        value,
                        'bundle identity',
                    )

    def test_bundle_identity_reports_each_unsafe_component(self) -> None:
        self.assertEqual(validate_bundle_identity('SafeBundle', '3_0_5'), [])
        errors = validate_bundle_identity('../escaped', '..\\escaped')
        self.assertEqual(len(errors), 2, errors)
        self.assertIn('bundle_name', errors[0])
        self.assertIn('bundle_version', errors[1])
        self.assertIn(
            'bundle_version must be a non-empty filename-safe value',
            validate_bundle_identity('SafeBundle', None),
        )

    def test_manifest_preflight_leaves_bundle_identity_to_identity_check(self) -> None:
        # The archive name uses the effective version (override or generated index),
        # so the path preflight must not reject a manifest version that is never used.
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source_root = base / 'bundle'
            repo_root = base / 'repo'
            source_root.mkdir()
            repo_root.mkdir()
            manifest = {'bundle_name': '../escaped', 'bundle_version': '..\\escaped'}

            self.assertEqual(
                validate_manifest_paths(manifest, source_root, repo_root),
                [],
            )

    def test_manifest_preflight_rejects_fields_naming_the_root(self) -> None:
        cases = [
            ({'generated_knowledge_attachment_dir': '.'}, None, 'generated_knowledge_attachment_dir'),
            ({'source_only_dirs': ['./']}, None, 'source_only_dirs'),
            ({'knowledge_attachment_sources': ['.']}, None, 'knowledge_attachment_sources'),
            ({}, '{"generated_prime_agent_file":"."}', 'generated_prime_agent_file'),
            ({}, '{"chunks":[{"path":"./"}]}', 'prime agent chunk path'),
        ]
        for fields, chunk_manifest, marker in cases:
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as td:
                base = Path(td)
                source_root = base / 'bundle'
                repo_root = base / 'repo'
                source_root.mkdir()
                repo_root.mkdir()
                manifest = {'generated_knowledge_attachment_dir': 'generated', **fields}
                if chunk_manifest is not None:
                    (source_root / 'chunks.json').write_text(
                        chunk_manifest, encoding='utf-8'
                    )
                    manifest['prime_agent_chunk_manifest'] = 'chunks.json'

                errors = validate_manifest_paths(manifest, source_root, repo_root)

                self.assertEqual(len(errors), 1, errors)
                self.assertIn(marker, errors[0])
                self.assertIn('not the root itself', errors[0])

    def test_safe_manifest_and_chunk_manifest_return_no_errors(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source_root = base / 'bundle'
            repo_root = base / 'repo'
            source_root.mkdir()
            repo_root.mkdir()
            (source_root / 'chunks.json').write_text(
                '{"generated_prime_agent_file":"generated.txt",'
                '"chunks":[{"path":"part.txt"}]}',
                encoding='utf-8',
            )
            manifest = {
                'required_files': [],
                'knowledge_attachment_sources': [],
                'prime_agent_chunk_manifest': 'chunks.json',
                'topology': {
                    'sub_agent_files': [],
                    'prime_agent_chunk_sources': [],
                },
            }

            self.assertEqual(
                validate_manifest_paths(manifest, source_root, repo_root),
                [],
            )


if __name__ == '__main__':
    unittest.main()
