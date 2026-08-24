#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


TOOL_PATH = (
    Path(__file__).resolve().parents[1]
    / 'tools'
    / 'materialize_agent_behavior_adapters.py'
)
SPEC = importlib.util.spec_from_file_location('behavior_adapter', TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError('Cannot load behavior adapter tool')
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class BehaviorAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp.name)
        self.agent_root = self.repo_root / 'project_sources' / 'agent_runtime'
        self.gemini_root = (
            self.repo_root / 'project_sources' / 'gemini' / 'bundle_source'
        )
        self.prime_source_rel = (
            'project_sources/agent_runtime/behavior_modules/prime/prime.chunk.00.md'
        )
        self.specialist_source_rel = (
            'project_sources/agent_runtime/behavior_modules/specialists/sub_agent.01.md'
        )
        self.prime_output_rel = (
            'project_sources/gemini/bundle_source/01_GEMINI_AGENT_BUILD/'
            'prime_agent_chunks/chunk.md.txt'
        )
        self.specialist_output_rel = (
            'project_sources/gemini/bundle_source/01_GEMINI_AGENT_BUILD/sub.md.txt'
        )
        self.prime_bytes = b'prime behavior\n'
        self.specialist_bytes = b'specialist behavior'
        self._write_bytes(self.prime_source_rel, self.prime_bytes)
        self._write_bytes(self.specialist_source_rel, self.specialist_bytes)
        self._write_json(
            'project_sources/gemini/bundle_source/'
            '01_GEMINI_AGENT_BUILD/prime_agent_chunks/chunks.json',
            {
                'chunks': [
                    {
                        'path': (
                            '01_GEMINI_AGENT_BUILD/prime_agent_chunks/chunk.md.txt'
                        )
                    }
                ]
            },
        )
        self._write_json(
            'project_sources/gemini/bundle_source/Gemini_Bundle_Source_Manifest.json',
            {
                'topology': {
                    'prime_agent_chunk_manifest': (
                        '01_GEMINI_AGENT_BUILD/prime_agent_chunks/chunks.json'
                    ),
                    'sub_agent_files': ['01_GEMINI_AGENT_BUILD/sub.md.txt'],
                }
            },
        )
        self._write_json(
            'project_sources/agent_runtime/Shared_Agent_Source_Manifest.json',
            {
                'behavior_module_manifest': (
                    'project_sources/agent_runtime/Behavior_Module_Manifest.json'
                ),
                'behavior_items': [
                    {
                        'id': 'prime.chunk.00',
                        'source_path': self.prime_source_rel,
                        'canonical': True,
                    },
                    {
                        'id': 'sub_agent.01',
                        'source_path': self.specialist_source_rel,
                        'canonical': True,
                    },
                ],
            },
        )
        self.manifest = self._base_manifest()
        self.manifest_path = (
            self.agent_root / 'Behavior_Module_Manifest.json'
        )
        self._save_manifest()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_bytes(self, relative: str, value: bytes) -> None:
        path = self.repo_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)

    def _write_json(self, relative: str, value: dict) -> None:
        self._write_bytes(
            relative, (json.dumps(value, indent=2) + '\n').encode('utf-8')
        )

    def _base_manifest(self) -> dict:
        return {
            'schema': ADAPTER.SCHEMA,
            'module_contract_version': 'fixture',
            'source_contract': (
                'project_sources/agent_runtime/Shared_Agent_Source_Manifest.json'
            ),
            'canonical_behavior_root': (
                'project_sources/agent_runtime/behavior_modules'
            ),
            'generated_target_policy': {
                'generated_outputs_are_canonical': False,
                'direct_target_edits_require_reverse_reconciliation': True,
            },
            'target_adapters': {
                ADAPTER.TARGET_ID: {
                    'output_root': 'project_sources/gemini/bundle_source',
                    'projection_mode': 'byte_identity',
                    'bundle_manifest': (
                        'project_sources/gemini/bundle_source/'
                        'Gemini_Bundle_Source_Manifest.json'
                    ),
                    'prime_chunk_manifest': (
                        'project_sources/gemini/bundle_source/'
                        '01_GEMINI_AGENT_BUILD/prime_agent_chunks/chunks.json'
                    ),
                    'expected_prime_chunks': 1,
                    'expected_specialists': 1,
                }
            },
            'modules': [
                self._module(
                    'prime.chunk.00',
                    'prime_chunk',
                    0,
                    self.prime_source_rel,
                    self.prime_output_rel,
                    self.prime_bytes,
                ),
                self._module(
                    'sub_agent.01',
                    'specialist',
                    1,
                    self.specialist_source_rel,
                    self.specialist_output_rel,
                    self.specialist_bytes,
                ),
            ],
        }

    @staticmethod
    def _module(
        module_id: str,
        kind: str,
        order: int,
        source_path: str,
        output_path: str,
        data: bytes,
    ) -> dict:
        digest = sha256(data)
        return {
            'id': module_id,
            'kind': kind,
            'order': order,
            'source_path': source_path,
            'sha256': digest,
            'projections': {
                ADAPTER.TARGET_ID: {
                    'output_path': output_path,
                    'projection_mode': 'byte_identity',
                    'sha256': digest,
                }
            },
        }

    def _save_manifest(self) -> None:
        self._write_json(
            'project_sources/agent_runtime/Behavior_Module_Manifest.json',
            self.manifest,
        )

    def _run(self, action: str = 'check') -> tuple[int, dict]:
        return ADAPTER.execute(
            self.repo_root,
            self.manifest_path,
            ADAPTER.TARGET_ID,
            action,
        )

    def test_materialize_then_check_preserves_exact_bytes(self) -> None:
        code, report = self._run('materialize')
        self.assertEqual(code, 0, report)
        self.assertEqual(
            (self.repo_root / self.prime_output_rel).read_bytes(),
            self.prime_bytes,
        )
        self.assertEqual(
            (self.repo_root / self.specialist_output_rel).read_bytes(),
            self.specialist_bytes,
        )
        code, report = self._run('check')
        self.assertEqual(code, 0, report)
        self.assertEqual(report['module_count'], 2)

    def test_check_rejects_adapter_drift(self) -> None:
        self.assertEqual(self._run('materialize')[0], 0)
        self._write_bytes(self.prime_output_rel, b'drift\n')
        code, report = self._run('check')
        self.assertEqual(code, 1)
        self.assertTrue(
            any('Generated adapter drift' in error for error in report['errors'])
        )

    def test_rejects_source_hash_mismatch(self) -> None:
        self.manifest['modules'][0]['sha256'] = '0' * 64
        self.manifest['modules'][0]['projections'][ADAPTER.TARGET_ID][
            'sha256'
        ] = '0' * 64
        self._save_manifest()
        code, report = self._run('materialize')
        self.assertEqual(code, 1)
        self.assertTrue(any('source sha256 mismatch' in e for e in report['errors']))

    def test_rejects_source_path_escape(self) -> None:
        self.manifest['modules'][0]['source_path'] = '../outside.md'
        self._save_manifest()
        code, report = self._run('materialize')
        self.assertEqual(code, 1)
        self.assertTrue(any('traversal' in error for error in report['errors']))

    def test_rejects_output_outside_target_root(self) -> None:
        self.manifest['modules'][0]['projections'][ADAPTER.TARGET_ID][
            'output_path'
        ] = 'project_sources/agent_runtime/not-a-gemini-output.md'
        self._save_manifest()
        code, report = self._run('materialize')
        self.assertEqual(code, 1)
        self.assertTrue(
            any('outside its declared root' in error for error in report['errors'])
        )

    def test_rejects_duplicate_output(self) -> None:
        self.manifest['modules'][1]['projections'][ADAPTER.TARGET_ID][
            'output_path'
        ] = self.prime_output_rel
        self._save_manifest()
        code, report = self._run('materialize')
        self.assertEqual(code, 1)
        self.assertTrue(
            any('Duplicate target adapter output' in e for e in report['errors'])
        )

    def test_rejects_duplicate_order_slot(self) -> None:
        self.manifest['modules'][1]['kind'] = 'prime_chunk'
        self.manifest['modules'][1]['order'] = 0
        self._save_manifest()
        code, report = self._run('materialize')
        self.assertEqual(code, 1)
        self.assertTrue(
            any('Duplicate behavior module order slot' in e for e in report['errors'])
        )

    def test_malformed_module_fails_without_crashing(self) -> None:
        self.manifest['modules'][0]['id'] = None
        self.manifest['target_adapters'][ADAPTER.TARGET_ID][
            'expected_prime_chunks'
        ] = True
        self._save_manifest()
        code, report = self._run('materialize')
        self.assertEqual(code, 1)
        self.assertTrue(any('valid id' in error for error in report['errors']))
        self.assertTrue(
            any('invalid expected_prime_chunks' in error for error in report['errors'])
        )

    def test_rejects_topology_disagreement(self) -> None:
        changed = copy.deepcopy(self.manifest)
        changed['modules'][0]['projections'][ADAPTER.TARGET_ID][
            'output_path'
        ] = (
            'project_sources/gemini/bundle_source/'
            '01_GEMINI_AGENT_BUILD/prime_agent_chunks/other.md.txt'
        )
        self.manifest = changed
        self._save_manifest()
        code, report = self._run('materialize')
        self.assertEqual(code, 1)
        self.assertTrue(
            any('topology disagrees' in error for error in report['errors'])
        )

    def test_rejects_source_contract_disagreement(self) -> None:
        contract_path = (
            self.agent_root / 'Shared_Agent_Source_Manifest.json'
        )
        contract = json.loads(contract_path.read_text(encoding='utf-8'))
        contract['behavior_items'][0]['source_path'] = 'wrong.md'
        contract_path.write_text(json.dumps(contract), encoding='utf-8')
        code, report = self._run('materialize')
        self.assertEqual(code, 1)
        self.assertTrue(
            any(
                'source path disagrees with the shared source contract' in error
                for error in report['errors']
            )
        )

if __name__ == '__main__':
    unittest.main()
