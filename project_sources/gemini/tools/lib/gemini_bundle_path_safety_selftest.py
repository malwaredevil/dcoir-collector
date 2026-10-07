#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Import through the lib package exactly as the Gemini tools do.
TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))
SYS_PATH_AFTER_TOOLS_DIR = list(sys.path)

from lib import gemini_bundle_path_safety
from lib.gemini_bundle_path_safety import (
    UnsafePathError,
    validate_bundle_identity,
    validate_bundle_identity_component,
    validate_manifest_paths,
)


class GeminiBundlePathSafetyTests(unittest.TestCase):
    def test_containment_comes_from_the_shared_owner_without_sys_path_changes(self) -> None:
        shared = sys.modules['agent_runtime_path_safety']
        self.assertEqual(
            Path(shared.__file__).resolve(),
            TOOLS_DIR.parent.parent / 'agent_runtime' / 'tools' / 'agent_runtime_path_safety.py',
        )
        self.assertIs(gemini_bundle_path_safety.resolve_contained_path, shared.resolve_contained_path)
        self.assertIs(gemini_bundle_path_safety.UnsafePathError, shared.UnsafePathError)
        self.assertEqual(sys.path, SYS_PATH_AFTER_TOOLS_DIR)

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

    def run_preflight(self, manifest: dict, chunk_manifest: str | None = None) -> list[str]:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source_root = base / 'bundle'
            repo_root = base / 'repo'
            source_root.mkdir()
            repo_root.mkdir()
            if chunk_manifest is not None:
                (source_root / 'chunks.json').write_text(chunk_manifest, encoding='utf-8')
                manifest = {**manifest, 'prime_agent_chunk_manifest': 'chunks.json'}
            return validate_manifest_paths(manifest, source_root, repo_root)

    def test_every_manifest_path_field_is_preflighted(self) -> None:
        cases = [
            *(({field: ['../escaped']}, field) for field in (
                'required_files',
                'source_required_files',
                'runtime_generated_files',
                'source_only_files',
                'source_only_dirs',
                'knowledge_attachment_sources',
            )),
            ({'generated_knowledge_attachment_dir': '../escaped'}, 'generated_knowledge_attachment_dir'),
            ({'prime_agent_chunk_manifest': '../escaped'}, 'prime_agent_chunk_manifest'),
            *(({'topology': {field: '../escaped'}}, f'topology.{field}') for field in (
                'prime_agent_file',
                'generated_index_file',
                'quick_start_file',
                'prime_agent_chunk_manifest',
            )),
            *(({'topology': {field: ['../escaped']}}, f'topology.{field}') for field in (
                'sub_agent_files',
                'prime_agent_chunk_sources',
            )),
        ]
        for manifest, label in cases:
            with self.subTest(label=label):
                errors = self.run_preflight(manifest)
                self.assertEqual(len(errors), 1, errors)
                self.assertTrue(
                    errors[0].startswith(f'{label} must not be absolute or contain traversal'),
                    errors,
                )

    def test_non_canonical_spellings_are_rejected(self) -> None:
        for value in ('./notes/x.md.txt', 'notes//x.md.txt', 'notes/', 'notes\\x.md.txt'):
            for manifest, chunk_manifest, label in (
                ({'source_only_files': [value]}, None, 'source_only_files'),
                ({'source_only_dirs': [value]}, None, 'source_only_dirs'),
                ({}, '{"chunks":[{"path":"%s"}]}' % value.replace('\\', '\\\\'), 'prime agent chunk path'),
                ({}, '{"generated_prime_agent_file":"%s"}' % value.replace('\\', '\\\\'), 'generated_prime_agent_file'),
            ):
                with self.subTest(value=value, label=label):
                    errors = self.run_preflight(manifest, chunk_manifest)
                    self.assertEqual(len(errors), 1, errors)
                    self.assertTrue(
                        errors[0].startswith(f'{label} must use canonical forward-slash spelling'),
                        errors,
                    )

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
