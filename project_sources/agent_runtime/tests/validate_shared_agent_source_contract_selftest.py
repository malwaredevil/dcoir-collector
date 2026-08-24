#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


VALIDATOR_PATH = (
    Path(__file__).resolve().parents[1]
    / 'tools'
    / 'validate_shared_agent_source_contract.py'
)
SPEC = importlib.util.spec_from_file_location('shared_contract_validator', VALIDATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f'Cannot load validator from {VALIDATOR_PATH}')
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


CAPABILITIES = {
    'web_search': False,
    'code_interpreter_data_analysis': False,
    'canvas': False,
    'image_generation': False,
    'apps': False,
    'actions': False,
    'live_elastic_access': False,
    'live_collector_execution': False,
    'github_supabase_connectors': False,
    'persistent_cross_conversation_memory': False,
}


def target(target_id: str) -> dict:
    value = {
        'id': target_id,
        'output_owner': 'fixture compiler',
        'generated_outputs': ['fixture output'],
        'capabilities': copy.deepcopy(CAPABILITIES),
    }
    if target_id.startswith('openai_'):
        value['optional_future_capabilities'] = {
            'public_lookup': {'current_available': False}
        }
    return value


def dispositions() -> dict:
    return {
        target_id: {
            'mode': 'direct',
            'owner': 'fixture',
            'generated_output': None,
            'notes': 'fixture',
        }
        for target_id in sorted(VALIDATOR.EXPECTED_TARGET_IDS)
    }


def behavior(item_id: str, source_path: str, authority: str = 'canonical') -> dict:
    return {
        'id': item_id,
        'source_path': source_path,
        'source_section': 'whole-file',
        'responsibility': 'fixture behavior',
        'content_class': 'shared_behavior_source',
        'authority_class': authority,
        'canonical': authority != 'generated',
        'split_disposition': None,
        'applies_to': sorted(VALIDATOR.EXPECTED_TARGET_IDS),
        'target_dispositions': dispositions(),
        'provider_specific_differences': 'fixture differences',
        'downstream_dependencies': ['fixture'],
        'validation_classes': ['fixture'],
        'source_map_required': True,
        'reverse_reconciliation_required': True,
        'unresolved_operator_decision': None,
    }


def base_manifest() -> dict:
    return {
        'schema': 'dcoir.agent_runtime.source_contract.v1',
        'source_contract_version': 'test',
        'target_ids': sorted(VALIDATOR.EXPECTED_TARGET_IDS),
        'targets': [target(target_id) for target_id in sorted(VALIDATOR.EXPECTED_TARGET_IDS)],
        'generated_artifact_policy': {
            'generated_outputs_are_canonical': False,
            'reverse_reconciliation_required': True,
            'reconciliation_rule': 'Reconcile target edits to source and rebuild.',
        },
        'knowledge_projection_policy': {'strict_file_count_ceiling': 20},
        'knowledge_projection_groups': [
            {'id': 'dcoir_group', 'target_id': 'openai_dcoir_analyst'},
            {'id': 'usb_group', 'target_id': 'openai_usb_reporting'},
        ],
        'ioc_enrichment_contract': {
            'behavior_source_ids': ['prime.chunk.00']
        },
        'behavior_items': [
            behavior(
                'prime.chunk.00',
                'project_sources/gemini/bundle_source/01_GEMINI_AGENT_BUILD/'
                'prime_agent_chunks/chunk.md.txt',
            ),
            behavior(
                'sub_agent.01',
                'project_sources/gemini/bundle_source/01_GEMINI_AGENT_BUILD/'
                'sub.md.txt',
            ),
            behavior(
                'gemini.runtime.generated_prime',
                'project_sources/gemini/bundle_source/01_GEMINI_AGENT_BUILD/'
                'Prime.md.txt',
                authority='generated',
            ),
        ],
        'knowledge_items': [
            {
                'id': 'knowledge.fixture',
                'source_path': 'knowledge/k.md',
                'content_class': 'runtime_reference',
                'canonical': True,
                'split_disposition': None,
                'applies_to': sorted(VALIDATOR.EXPECTED_TARGET_IDS),
                'gemini_attachment_disposition': 'include',
                'openai_dcoir_projection_group': 'dcoir_group',
                'openai_usb_projection_group': 'usb_group',
                'source_boundary_hash_required': True,
                'duplicate_or_overlap_notes': 'fixture',
                'consolidation_validation': ['sha256'],
            }
        ],
        'stale_source_references': [
            {
                'id': 'stale.fixture',
                'source_path': 'project_sources/missing.txt',
                'status': 'missing_retired_reference',
                'live_evidence': 'fixture missing path',
                'replacement_authority': 'fixture current source',
                'runtime_cleanup': 'deferred fixture cleanup',
            }
        ],
    }


def matrix_text(manifest: dict) -> str:
    lines = []
    for item in manifest['behavior_items']:
        lines.append(f"<!-- contract-behavior-id:{item['id']} -->")
    for item in manifest['knowledge_items']:
        lines.append(f"<!-- contract-knowledge-id:{item['id']} -->")
    for item in manifest['stale_source_references']:
        lines.append(f"<!-- contract-stale-id:{item['id']} -->")
    return '\n'.join(lines) + '\n'


class ContractFixture:
    def __init__(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manifest_path = self.root / 'contract.json'
        self.matrix_path = self.root / 'matrix.md'
        self.manifest = base_manifest()
        self._write_repo_sources()
        self.write()

    def _write_repo_sources(self) -> None:
        bundle_root = self.root / 'project_sources' / 'gemini' / 'bundle_source'
        prime_rel = Path('01_GEMINI_AGENT_BUILD/prime_agent_chunks/chunks.json')
        (bundle_root / prime_rel).parent.mkdir(parents=True, exist_ok=True)
        (bundle_root / prime_rel).write_text(
            json.dumps(
                {
                    'chunks': [
                        {
                            'path': '01_GEMINI_AGENT_BUILD/'
                            'prime_agent_chunks/chunk.md.txt'
                        }
                    ]
                }
            ),
            encoding='utf-8',
        )
        (bundle_root / 'Gemini_Bundle_Source_Manifest.json').write_text(
            json.dumps(
                {
                    'behavioral_authority': ['project_sources/missing.txt'],
                    'topology': {
                        'prime_agent_chunk_manifest': prime_rel.as_posix(),
                        'sub_agent_files': ['01_GEMINI_AGENT_BUILD/sub.md.txt'],
                    },
                    'knowledge_attachment_sources': ['knowledge/k.md'],
                }
            ),
            encoding='utf-8',
        )
        for relative in (
            'project_sources/gemini/bundle_source/01_GEMINI_AGENT_BUILD/'
            'prime_agent_chunks/chunk.md.txt',
            'project_sources/gemini/bundle_source/01_GEMINI_AGENT_BUILD/sub.md.txt',
            'knowledge/k.md',
        ):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture\n', encoding='utf-8')

    def write(self, matrix: str | None = None) -> None:
        self.manifest_path.write_text(
            json.dumps(self.manifest, indent=2), encoding='utf-8'
        )
        self.matrix_path.write_text(
            matrix if matrix is not None else matrix_text(self.manifest),
            encoding='utf-8',
        )

    def validate(self) -> list[str]:
        errors, _ = VALIDATOR.validate_contract(
            self.manifest_path, self.matrix_path, self.root
        )
        return errors

    def close(self) -> None:
        self.temp.cleanup()


class SharedAgentSourceContractSelfTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = ContractFixture()

    def tearDown(self) -> None:
        self.fixture.close()

    def assert_error_contains(self, needle: str) -> None:
        errors = self.fixture.validate()
        self.assertTrue(
            any(needle in error for error in errors),
            msg=f'Expected {needle!r}; got {errors}',
        )

    def test_valid_contract_passes(self) -> None:
        self.assertEqual([], self.fixture.validate())

    def test_unmapped_prime_fails(self) -> None:
        self.fixture.manifest['behavior_items'].pop(0)
        self.fixture.write()
        self.assert_error_contains('Prime source is not mapped exactly once')

    def test_conflicting_authority_class_fails(self) -> None:
        duplicate = copy.deepcopy(self.fixture.manifest['behavior_items'][1])
        duplicate['id'] = 'behavior.conflicting_authority'
        duplicate['authority_class'] = 'maintainer_only'
        self.fixture.manifest['behavior_items'].append(duplicate)
        self.fixture.write()
        self.assert_error_contains('Conflicting authority classes')

    def test_missing_source_without_stale_disposition_fails(self) -> None:
        missing = behavior('behavior.missing', 'project_sources/not-present.md')
        self.fixture.manifest['behavior_items'].append(missing)
        self.fixture.write()
        self.assert_error_contains('Missing canonical source path without stale disposition')

    def test_generated_output_marked_canonical_fails(self) -> None:
        generated = self.fixture.manifest['behavior_items'][2]
        generated['canonical'] = True
        self.fixture.write()
        self.assert_error_contains('Generated output is marked canonical')

    def test_unavailable_openai_capability_claim_fails(self) -> None:
        target_value = next(
            item
            for item in self.fixture.manifest['targets']
            if item['id'] == 'openai_dcoir_analyst'
        )
        target_value['capabilities']['web_search'] = True
        self.fixture.write()
        self.assert_error_contains('claims unavailable capability')

    def test_projection_group_ceiling_fails(self) -> None:
        self.fixture.manifest['knowledge_projection_policy'][
            'strict_file_count_ceiling'
        ] = 1
        self.fixture.manifest['knowledge_projection_groups'].append(
            {'id': 'dcoir_second', 'target_id': 'openai_dcoir_analyst'}
        )
        self.fixture.write()
        self.assert_error_contains('Knowledge projection group ceiling exceeded')

    def test_missing_source_map_and_reverse_metadata_fails(self) -> None:
        item = self.fixture.manifest['behavior_items'][0]
        del item['source_map_required']
        del item['reverse_reconciliation_required']
        self.fixture.write()
        errors = self.fixture.validate()
        self.assertTrue(any('source-map metadata' in error for error in errors))
        self.assertTrue(any('reverse-reconciliation metadata' in error for error in errors))

    def test_duplicate_target_and_stable_ids_fail(self) -> None:
        self.fixture.manifest['targets'].append(
            copy.deepcopy(self.fixture.manifest['targets'][0])
        )
        self.fixture.manifest['knowledge_items'][0]['id'] = 'prime.chunk.00'
        self.fixture.write()
        errors = self.fixture.validate()
        self.assertTrue(any('Duplicate target id' in error for error in errors))
        self.assertTrue(any('Duplicate stable item id' in error for error in errors))

    def test_manifest_matrix_id_disagreement_fails(self) -> None:
        matrix = matrix_text(self.fixture.manifest).replace(
            '<!-- contract-knowledge-id:knowledge.fixture -->\n', ''
        )
        self.fixture.write(matrix=matrix)
        self.assert_error_contains('Manifest/matrix knowledge id disagreement')

    def test_stale_authority_substitution_fails(self) -> None:
        self.fixture.manifest['stale_source_references'][0][
            'source_path'
        ] = 'project_sources/different-missing.txt'
        self.fixture.write()
        self.assert_error_contains('Stale authority source is not mapped exactly once')


if __name__ == '__main__':
    unittest.main(verbosity=2)
