#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
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
    raise RuntimeError('Cannot load shared source-contract validator')
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
        'canonical_source_roots': {
            'shared_contract': 'project_sources/agent_runtime',
            'shared_behavior_modules': (
                'project_sources/agent_runtime/behavior_modules'
            ),
            'gemini_source': 'project_sources/gemini',
            'gemini_runtime': 'project_sources/gemini/bundle_source',
            'knowledge': 'knowledge',
        },
        'behavior_module_manifest': (
            'project_sources/agent_runtime/Behavior_Module_Manifest.json'
        ),
        'gemini_behavioral_authority_sources': [
            'project_sources/agent_runtime/Shared_Agent_Source_Manifest.json',
            'project_sources/agent_runtime/Behavior_Module_Manifest.json',
        ],
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
                'project_sources/agent_runtime/behavior_modules/prime/'
                'prime.chunk.00.md',
                authority='canonical_shared_behavior',
            ),
            behavior(
                'sub_agent.01',
                'project_sources/agent_runtime/behavior_modules/specialists/'
                'sub_agent.01.md',
                authority='canonical_shared_behavior',
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
    lines = [
        '## Target Capability Boundary',
        '',
        '| Target | Output owner | Instruction mode | Knowledge mode | Current live lookup | Current external actions |',
        '| --- | --- | --- | --- | --- | --- |',
    ]
    for item in manifest['targets']:
        live_lookup = (
            'Runtime-dependent; never assumed'
            if 'web_search' in item.get('runtime_dependent_capabilities', [])
            else 'Unavailable'
        )
        actions = (
            'Unavailable unless returned execution evidence exists'
            if item['capabilities']['actions'] is False
            else 'Available'
        )
        lines.append(
            f"| {item['id']} | {item['output_owner']} | "
            f"{item.get('instruction_mode', '')} | {item.get('knowledge_mode', '')} | "
            f'{live_lookup} | {actions} |'
        )
    lines.extend(
        [
            '',
            '## Behavior Ownership',
            '',
            '| Stable id | Source / section | Class | Gemini | OpenAI DCOIR | OpenAI USB | Responsibility |',
            '| --- | --- | --- | --- | --- | --- | --- |',
        ]
    )
    for item in manifest['behavior_items']:
        lines.append(f"<!-- contract-behavior-id:{item['id']} -->")
        dispositions_value = item['target_dispositions']
        lines.append(
            f"| {item['id']} | {item['source_path']} / {item['source_section']} | "
            f"{item['content_class']} | "
            f"{dispositions_value['gemini_dcoir_agent']['mode']} | "
            f"{dispositions_value['openai_dcoir_analyst']['mode']} | "
            f"{dispositions_value['openai_usb_reporting']['mode']} | "
            f"{item['responsibility']} |"
        )
    lines.extend(
        [
            '',
            '## Behavior Control Details',
            '',
            '| Stable id | Applies to | Provider differences | Dependencies | Validation | Reverse sync | Decision |',
            '| --- | --- | --- | --- | --- | --- | --- |',
        ]
    )
    for item in manifest['behavior_items']:
        decision = item['unresolved_operator_decision'] or 'None'
        reverse_sync = (
            'Required'
            if item.get('reverse_reconciliation_required') is True
            else 'Not required'
        )
        lines.append(
            f"| {item['id']} | {', '.join(item['applies_to'])} | "
            f"{item['provider_specific_differences']} | "
            f"{'; '.join(item['downstream_dependencies'])} | "
            f"{'; '.join(item['validation_classes'])} | {reverse_sync} | {decision} |"
        )
    lines.extend(
        [
            '',
            '## Knowledge Disposition',
            '',
            '| Stable id | Canonical source | Class | Gemini attachment | DCOIR projection | USB projection | Boundary/hash and overlap rule |',
            '| --- | --- | --- | --- | --- | --- | --- |',
        ]
    )
    for item in manifest['knowledge_items']:
        lines.append(f"<!-- contract-knowledge-id:{item['id']} -->")
        gemini = item['gemini_attachment_disposition']
        if gemini == 'include_direct_from_canonical_source':
            gemini = 'include'
        boundary = (
            'Preserve ordered source boundary and SHA-256; '
            if item['source_boundary_hash_required']
            else ''
        ) + item['duplicate_or_overlap_notes']
        lines.append(
            f"| {item['id']} | {item['source_path']} | {item['content_class']} | "
            f"{gemini} | {item['openai_dcoir_projection_group'] or 'excluded'} | "
            f"{item['openai_usb_projection_group'] or 'excluded'} | {boundary} |"
        )
    lines.extend(
        [
            '',
            '## Stale Behavioral Authority References',
            '',
            '| Stable id | Missing path | Status | Replacement authority | Runtime action |',
            '| --- | --- | --- | --- | --- |',
        ]
    )
    for item in manifest['stale_source_references']:
        lines.append(f"<!-- contract-stale-id:{item['id']} -->")
        lines.append(
            f"| {item['id']} | {item['source_path']} | {item['status']} | "
            f"{item['replacement_authority']} | {item['runtime_cleanup']} |"
        )
    return '\n'.join(lines) + '\n'


class ContractFixture:
    def __init__(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manifest_path = (
            self.root
            / 'project_sources'
            / 'agent_runtime'
            / 'Shared_Agent_Source_Manifest.json'
        )
        self.matrix_path = (
            self.root
            / 'project_sources'
            / 'agent_runtime'
            / 'docs'
            / 'Behavior_Ownership_Matrix.md'
        )
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
                    'behavioral_authority': [
                        'project_sources/agent_runtime/Shared_Agent_Source_Manifest.json',
                        'project_sources/agent_runtime/Behavior_Module_Manifest.json',
                    ],
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
            'project_sources/agent_runtime/behavior_modules/prime/'
            'prime.chunk.00.md',
            'project_sources/agent_runtime/behavior_modules/specialists/'
            'sub_agent.01.md',
            'project_sources/gemini/bundle_source/01_GEMINI_AGENT_BUILD/'
            'prime_agent_chunks/chunk.md.txt',
            'project_sources/gemini/bundle_source/01_GEMINI_AGENT_BUILD/sub.md.txt',
            'knowledge/k.md',
        ):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture\n', encoding='utf-8')
        digest = hashlib.sha256(b'fixture\n').hexdigest()
        module_manifest_path = (
            self.root
            / 'project_sources'
            / 'agent_runtime'
            / 'Behavior_Module_Manifest.json'
        )
        module_manifest_path.write_text(
            json.dumps(
                {
                    'schema': 'dcoir.agent_runtime.behavior_modules.v1',
                    'module_contract_version': 'fixture',
                    'source_contract': (
                        'project_sources/agent_runtime/'
                        'Shared_Agent_Source_Manifest.json'
                    ),
                    'canonical_behavior_root': (
                        'project_sources/agent_runtime/behavior_modules'
                    ),
                    'modules': [
                        {
                            'id': 'prime.chunk.00',
                            'kind': 'prime_chunk',
                            'order': 0,
                            'source_path': (
                                'project_sources/agent_runtime/behavior_modules/'
                                'prime/prime.chunk.00.md'
                            ),
                            'sha256': digest,
                            'projections': {
                                'gemini_dcoir_agent': {
                                    'output_path': (
                                        'project_sources/gemini/bundle_source/'
                                        '01_GEMINI_AGENT_BUILD/prime_agent_chunks/'
                                        'chunk.md.txt'
                                    ),
                                    'projection_mode': 'byte_identity',
                                    'sha256': digest,
                                }
                            },
                        },
                        {
                            'id': 'sub_agent.01',
                            'kind': 'specialist',
                            'order': 1,
                            'source_path': (
                                'project_sources/agent_runtime/behavior_modules/'
                                'specialists/sub_agent.01.md'
                            ),
                            'sha256': digest,
                            'projections': {
                                'gemini_dcoir_agent': {
                                    'output_path': (
                                        'project_sources/gemini/bundle_source/'
                                        '01_GEMINI_AGENT_BUILD/sub.md.txt'
                                    ),
                                    'projection_mode': 'byte_identity',
                                    'sha256': digest,
                                }
                            },
                        },
                    ],
                }
            ),
            encoding='utf-8',
        )

    def write(self, matrix: str | None = None) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.matrix_path.parent.mkdir(parents=True, exist_ok=True)
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
        self.assert_error_contains('Behavior module/source-contract id disagreement')

    def test_conflicting_authority_class_fails(self) -> None:
        duplicate = copy.deepcopy(self.fixture.manifest['behavior_items'][1])
        duplicate['id'] = 'behavior.conflicting_authority'
        duplicate['authority_class'] = 'maintainer_only'
        self.fixture.manifest['behavior_items'].append(duplicate)
        self.fixture.write()
        self.assert_error_contains('Conflicting authority classes')

    def test_missing_source_without_stale_disposition_fails(self) -> None:
        missing = behavior(
            'behavior.missing', 'project_sources/gemini/not-present.md'
        )
        self.fixture.manifest['behavior_items'].append(missing)
        self.fixture.write()
        self.assert_error_contains('Missing canonical source path without stale disposition')

    def test_absolute_canonical_source_path_fails(self) -> None:
        absolute = behavior(
            'behavior.absolute',
            str((self.fixture.root / 'knowledge' / 'k.md').resolve()),
        )
        self.fixture.manifest['behavior_items'].append(absolute)
        self.fixture.write()
        self.assert_error_contains(
            'Canonical source path must be repository-relative without traversal'
        )

    def test_canonical_source_traversal_fails(self) -> None:
        traversing = behavior(
            'behavior.traversal',
            'project_sources/../knowledge/k.md',
        )
        self.fixture.manifest['behavior_items'].append(traversing)
        self.fixture.write()
        self.assert_error_contains(
            'Canonical source path must be repository-relative without traversal'
        )

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

    def test_malformed_capabilities_and_dispositions_fail_without_crashing(self) -> None:
        matrix = matrix_text(self.fixture.manifest)
        target_value = next(
            item
            for item in self.fixture.manifest['targets']
            if item['id'] == 'openai_dcoir_analyst'
        )
        target_value['capabilities'] = []
        self.fixture.manifest['behavior_items'][0]['target_dispositions'] = []
        self.fixture.write(matrix=matrix)
        errors = self.fixture.validate()
        self.assertTrue(any('lacks a capabilities object' in error for error in errors))
        self.assertTrue(any('must disposition all three targets' in error for error in errors))

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

    def test_manifest_matrix_visible_field_disagreement_fails(self) -> None:
        matrix = matrix_text(self.fixture.manifest).replace(
            ' | direct | direct | direct | fixture behavior |',
            ' | direct | exclude | direct | fixture behavior |',
            1,
        )
        self.fixture.write(matrix=matrix)
        self.assert_error_contains('Manifest/matrix Behavior Ownership mismatch')

    def test_retired_authority_cannot_return_live(self) -> None:
        bundle_path = (
            self.fixture.root
            / 'project_sources'
            / 'gemini'
            / 'bundle_source'
            / 'Gemini_Bundle_Source_Manifest.json'
        )
        bundle = json.loads(bundle_path.read_text(encoding='utf-8'))
        bundle['behavioral_authority'] = ['project_sources/missing.txt']
        bundle_path.write_text(json.dumps(bundle), encoding='utf-8')
        self.assert_error_contains('Live Gemini behavioral authority still contains')

    def test_split_source_requires_provider_neutral_projection_unit(self) -> None:
        projection_rel = (
            'project_sources/agent_runtime/knowledge_modules/shared/output.md'
        )
        projection_path = self.fixture.root / projection_rel
        projection_path.parent.mkdir(parents=True, exist_ok=True)
        projection_content = b'# Shared output rules\n\nEvidence first.\n'
        projection_path.write_bytes(projection_content)
        self.fixture.manifest['canonical_source_roots'][
            'shared_knowledge_modules'
        ] = 'project_sources/agent_runtime/knowledge_modules'
        item = self.fixture.manifest['knowledge_items'][0]
        item['content_class'] = 'split'
        item['split_disposition'] = 'Use provider-neutral target source.'
        item['target_projection_sources'] = {
            target_id: {
                'id': 'knowledge.shared.output',
                'source_path': projection_rel,
                'source_git_blob_sha': VALIDATOR._git_blob_sha(projection_content),
                'provider_neutral_required': True,
            }
            for target_id in sorted(VALIDATOR.OPENAI_TARGET_IDS)
        }
        self.fixture.write()
        self.assertEqual([], self.fixture.validate())

        leaked_content = b'# Gemini output rules\n'
        projection_path.write_bytes(leaked_content)
        for override in item['target_projection_sources'].values():
            override['source_git_blob_sha'] = VALIDATOR._git_blob_sha(leaked_content)
        self.fixture.write()
        self.assert_error_contains('contains provider-specific terms')


if __name__ == '__main__':
    unittest.main(verbosity=2)
