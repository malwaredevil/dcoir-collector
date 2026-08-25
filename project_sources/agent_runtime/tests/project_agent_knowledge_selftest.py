#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS_DIR))

import project_agent_knowledge as projector  # noqa: E402


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def _git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f'blob {len(data)}\0'.encode('ascii') + data).hexdigest()


class KnowledgeProjectionSelfTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.manifest_path = (
            self.repo
            / 'project_sources/agent_runtime/Knowledge_Projection_Manifest.json'
        )
        self.contents = {
            'alpha': b'# Alpha\n\nCanonical alpha.\n',
            'bravo': b'# Bravo\n\nCanonical bravo.\n',
        }
        self._build_fixture()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _read_manifest(self) -> dict[str, object]:
        return json.loads(self.manifest_path.read_text(encoding='utf-8'))

    def _write_manifest(self, manifest: dict[str, object]) -> None:
        _write_json(self.manifest_path, manifest)

    def _build_fixture(self) -> None:
        for source_id, content in self.contents.items():
            path = self.repo / f'knowledge/{source_id}.md'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

        contract = {
            'schema': projector.SOURCE_CONTRACT_SCHEMA,
            'canonical_source_roots': {'knowledge': 'knowledge'},
            'knowledge_projection_manifest': (
                'project_sources/agent_runtime/Knowledge_Projection_Manifest.json'
            ),
            'knowledge_projection_policy': {'strict_file_count_ceiling': 3},
            'knowledge_projection_groups': [
                {
                    'id': 'dcoir_core',
                    'target_id': 'openai_dcoir_analyst',
                    'purpose': 'DCOIR core.',
                },
                {
                    'id': 'dcoir_reference',
                    'target_id': 'openai_dcoir_analyst',
                    'purpose': 'DCOIR reference.',
                },
                {
                    'id': 'usb_core',
                    'target_id': 'openai_usb_reporting',
                    'purpose': 'USB core.',
                },
            ],
            'knowledge_items': [
                {
                    'id': 'alpha',
                    'source_path': 'knowledge/alpha.md',
                    'source_git_blob_sha': _git_blob_sha(self.contents['alpha']),
                    'applies_to': [
                        'gemini_dcoir_agent',
                        'openai_dcoir_analyst',
                        'openai_usb_reporting',
                    ],
                    'openai_dcoir_projection_group': 'dcoir_core',
                    'openai_usb_projection_group': 'usb_core',
                },
                {
                    'id': 'bravo',
                    'source_path': 'knowledge/bravo.md',
                    'source_git_blob_sha': _git_blob_sha(self.contents['bravo']),
                    'applies_to': [
                        'gemini_dcoir_agent',
                        'openai_dcoir_analyst',
                    ],
                    'openai_dcoir_projection_group': 'dcoir_reference',
                },
            ],
        }
        _write_json(
            self.repo / 'project_sources/agent_runtime/Shared_Agent_Source_Manifest.json',
            contract,
        )
        _write_json(
            self.repo / 'project_sources/gemini/bundle_source/Gemini_Bundle_Source_Manifest.json',
            {
                'knowledge_attachment_sources': [
                    'knowledge/alpha.md',
                    'knowledge/bravo.md',
                ]
            },
        )
        self._write_manifest(
            {
                'schema': projector.SCHEMA,
                'projection_contract_version': 'test',
                'source_contract': (
                    'project_sources/agent_runtime/Shared_Agent_Source_Manifest.json'
                ),
                'canonical_knowledge_root': 'knowledge',
                'generated_root': 'project_sources/agent_runtime/generated/knowledge',
                'expected_canonical_source_count': 2,
                'strict_file_count_ceiling': 3,
                'targets': {
                    'gemini_dcoir_agent': {
                        'mode': 'direct_canonical_attachments',
                        'bundle_manifest': (
                            'project_sources/gemini/bundle_source/'
                            'Gemini_Bundle_Source_Manifest.json'
                        ),
                        'expected_attachment_count': 2,
                    },
                    'openai_dcoir_analyst': {
                        'mode': 'consolidated_projection',
                        'target_manifest_path': (
                            'project_sources/agent_runtime/generated/knowledge/'
                            'openai_dcoir_analyst/manifest.json'
                        ),
                        'expected_projection_count': 2,
                        'projection_groups': [
                            {
                                'id': 'dcoir_core',
                                'order': 0,
                                'output_path': (
                                    'project_sources/agent_runtime/generated/knowledge/'
                                    'openai_dcoir_analyst/01-core.md'
                                ),
                            },
                            {
                                'id': 'dcoir_reference',
                                'order': 1,
                                'output_path': (
                                    'project_sources/agent_runtime/generated/knowledge/'
                                    'openai_dcoir_analyst/02-reference.md'
                                ),
                            },
                        ],
                    },
                    'openai_usb_reporting': {
                        'mode': 'consolidated_projection',
                        'target_manifest_path': (
                            'project_sources/agent_runtime/generated/knowledge/'
                            'openai_usb_reporting/manifest.json'
                        ),
                        'expected_projection_count': 1,
                        'projection_groups': [
                            {
                                'id': 'usb_core',
                                'order': 0,
                                'output_path': (
                                    'project_sources/agent_runtime/generated/knowledge/'
                                    'openai_usb_reporting/01-core.md'
                                ),
                            }
                        ],
                    },
                },
            }
        )

    def _run(self, check: bool) -> tuple[list[str], dict[str, object]]:
        return projector.project_knowledge(self.repo, self.manifest_path, check)

    def test_materialize_check_and_lossless_recovery(self) -> None:
        errors, report = self._run(check=False)
        self.assertEqual([], errors)
        self.assertTrue(report['success'])
        errors, _ = self._run(check=True)
        self.assertEqual([], errors)

        recovered: dict[str, bytes] = {}
        generated = self.repo / 'project_sources/agent_runtime/generated/knowledge'
        for projection in generated.rglob('*.md'):
            for entry in projector.recover_projection(projection.read_bytes()):
                recovered[entry['metadata']['id']] = entry['content']
        self.assertEqual(self.contents, recovered)

    def test_source_blob_drift_fails_closed(self) -> None:
        self.assertEqual([], self._run(check=False)[0])
        (self.repo / 'knowledge/alpha.md').write_text('drift\n', encoding='utf-8')
        errors, _ = self._run(check=True)
        self.assertTrue(any('Git blob SHA mismatch' in error for error in errors))

    def test_generated_drift_and_stale_file_fail_closed(self) -> None:
        self.assertEqual([], self._run(check=False)[0])
        generated = self.repo / 'project_sources/agent_runtime/generated/knowledge'
        (generated / 'openai_dcoir_analyst/01-core.md').write_text(
            'drift\n', encoding='utf-8'
        )
        (generated / 'stale.md').write_text('stale\n', encoding='utf-8')
        errors, _ = self._run(check=True)
        self.assertTrue(any('Generated knowledge drift' in error for error in errors))
        self.assertTrue(any('Stale generated knowledge files' in error for error in errors))

    def test_projection_budget_overflow_fails_closed(self) -> None:
        manifest = self._read_manifest()
        manifest['strict_file_count_ceiling'] = 1
        self._write_manifest(manifest)
        contract_path = (
            self.repo / 'project_sources/agent_runtime/Shared_Agent_Source_Manifest.json'
        )
        contract = json.loads(contract_path.read_text(encoding='utf-8'))
        contract['knowledge_projection_policy']['strict_file_count_ceiling'] = 1
        _write_json(contract_path, contract)
        errors, _ = self._run(check=False)
        self.assertTrue(any('exceeds ceiling' in error for error in errors))

        self._build_fixture()
        manifest = self._read_manifest()
        manifest['strict_file_count_ceiling'] = True
        self._write_manifest(manifest)
        errors, _ = self._run(check=False)
        self.assertTrue(any('positive integer' in error for error in errors))

    def test_gemini_inventory_drift_fails_closed(self) -> None:
        bundle_path = (
            self.repo
            / 'project_sources/gemini/bundle_source/Gemini_Bundle_Source_Manifest.json'
        )
        _write_json(bundle_path, {'knowledge_attachment_sources': ['knowledge/alpha.md']})
        errors, _ = self._run(check=False)
        self.assertTrue(any('Gemini attachment' in error for error in errors))

        _write_json(
            bundle_path,
            {
                'knowledge_attachment_sources': [
                    'knowledge/alpha.md',
                    'knowledge/bravo.md',
                    'knowledge/alpha.md',
                ]
            },
        )
        errors, _ = self._run(check=False)
        self.assertTrue(any('Duplicate Gemini' in error for error in errors))

    def test_path_escape_and_cross_target_output_fail_closed(self) -> None:
        manifest = self._read_manifest()
        dcoir = manifest['targets']['openai_dcoir_analyst']
        dcoir['projection_groups'][0]['output_path'] = '../escape.md'
        self._write_manifest(manifest)
        errors, _ = self._run(check=False)
        self.assertTrue(any('traversal' in error for error in errors))

        self._build_fixture()
        manifest = self._read_manifest()
        dcoir = manifest['targets']['openai_dcoir_analyst']
        dcoir['projection_groups'][0]['output_path'] = (
            'project_sources/agent_runtime/generated/knowledge/'
            'openai_usb_reporting/cross.md'
        )
        self._write_manifest(manifest)
        errors, _ = self._run(check=False)
        self.assertTrue(any('outside its declared root' in error for error in errors))

    def test_manifest_and_generated_roots_must_be_contained(self) -> None:
        outside = self.repo.parent / 'outside-projection-manifest.json'
        errors, _ = projector.project_knowledge(self.repo, outside, check=False)
        self.assertEqual(['Projection manifest must be inside the repository'], errors)

        manifest = self._read_manifest()
        manifest['generated_root'] = 'knowledge/generated'
        self._write_manifest(manifest)
        errors, _ = self._run(check=False)
        self.assertTrue(any('must be disjoint' in error for error in errors))

    def test_malformed_applicability_and_generated_symlink_fail_closed(self) -> None:
        contract_path = (
            self.repo / 'project_sources/agent_runtime/Shared_Agent_Source_Manifest.json'
        )
        contract = json.loads(contract_path.read_text(encoding='utf-8'))
        contract['knowledge_items'][0]['applies_to'] = 7
        _write_json(contract_path, contract)
        errors, _ = self._run(check=False)
        self.assertTrue(any('applies_to must be' in error for error in errors))

        self._build_fixture()
        self.assertEqual([], self._run(check=False)[0])
        generated = self.repo / 'project_sources/agent_runtime/generated/knowledge'
        (generated / 'unexpected-link').symlink_to(self.repo / 'knowledge/alpha.md')
        errors, _ = self._run(check=True)
        self.assertTrue(any('must not contain symlinks' in error for error in errors))


if __name__ == '__main__':
    unittest.main(verbosity=2)
