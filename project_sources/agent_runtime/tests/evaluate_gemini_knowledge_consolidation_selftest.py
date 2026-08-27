#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS_DIR))

import evaluate_gemini_knowledge_consolidation as evaluator  # noqa: E402
import project_agent_knowledge as projector  # noqa: E402


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def _git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f'blob {len(data)}\0'.encode('ascii') + data).hexdigest()


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class GeminiKnowledgeConsolidationEvaluationSelfTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.manifest_path = (
            self.repo
            / 'project_sources/agent_runtime/Knowledge_Projection_Manifest.json'
        )
        self.contract_path = (
            self.repo
            / 'project_sources/agent_runtime/Shared_Agent_Source_Manifest.json'
        )
        self.bundle_path = (
            self.repo
            / 'project_sources/gemini/bundle_source/Gemini_Bundle_Source_Manifest.json'
        )
        self.contents = {
            'alpha': b'# Alpha\n\nCanonical full alpha with provider-specific details.\n',
            'bravo': b'# Bravo\n\nReference bravo.\n',
            'charlie': b'# Charlie\n\nGemini-only maintainer material.\n',
            'delta': b'# Delta\n\nAdditional core runtime material.\n',
        }
        self.shared_alpha = b'# Shared alpha\n\nNeutral shared output rules.\n'
        self._build_fixture()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _read_json(self, path: Path) -> dict[str, object]:
        return json.loads(path.read_text(encoding='utf-8'))

    def _write_manifest(self, manifest: dict[str, object]) -> None:
        _write_json(self.manifest_path, manifest)

    def _write_contract(self, contract: dict[str, object]) -> None:
        _write_json(self.contract_path, contract)

    def _build_fixture(self) -> None:
        for source_id, content in self.contents.items():
            path = self.repo / f'knowledge/{source_id}.md'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        shared_path = (
            self.repo
            / 'project_sources/agent_runtime/knowledge_modules/shared-alpha.md'
        )
        shared_path.parent.mkdir(parents=True, exist_ok=True)
        shared_path.write_bytes(self.shared_alpha)

        contract = {
            'schema': projector.SOURCE_CONTRACT_SCHEMA,
            'canonical_source_roots': {
                'knowledge': 'knowledge',
                'shared_knowledge_modules': (
                    'project_sources/agent_runtime/knowledge_modules'
                ),
            },
            'knowledge_projection_manifest': (
                'project_sources/agent_runtime/Knowledge_Projection_Manifest.json'
            ),
            'knowledge_projection_policy': {'strict_file_count_ceiling': 4},
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
                    'id': 'knowledge.alpha',
                    'source_path': 'knowledge/alpha.md',
                    'source_git_blob_sha': _git_blob_sha(self.contents['alpha']),
                    'content_class': 'split',
                    'applies_to': [
                        'gemini_dcoir_agent',
                        'openai_dcoir_analyst',
                        'openai_usb_reporting',
                    ],
                    'gemini_attachment_disposition': (
                        'include_direct_from_canonical_source'
                    ),
                    'openai_dcoir_projection_group': 'dcoir_core',
                    'openai_usb_projection_group': 'usb_core',
                    'target_projection_sources': {
                        target_id: {
                            'id': 'knowledge.alpha.shared',
                            'source_path': (
                                'project_sources/agent_runtime/knowledge_modules/'
                                'shared-alpha.md'
                            ),
                            'source_git_blob_sha': _git_blob_sha(self.shared_alpha),
                            'provider_neutral_required': True,
                        }
                        for target_id in projector.OPENAI_TARGETS
                    },
                },
                {
                    'id': 'knowledge.bravo',
                    'source_path': 'knowledge/bravo.md',
                    'source_git_blob_sha': _git_blob_sha(self.contents['bravo']),
                    'content_class': 'runtime_reference',
                    'applies_to': [
                        'gemini_dcoir_agent',
                        'openai_dcoir_analyst',
                    ],
                    'gemini_attachment_disposition': (
                        'include_direct_from_canonical_source'
                    ),
                    'openai_dcoir_projection_group': 'dcoir_reference',
                    'openai_usb_projection_group': None,
                },
                {
                    'id': 'knowledge.gemini.only',
                    'source_path': 'knowledge/charlie.md',
                    'source_git_blob_sha': _git_blob_sha(self.contents['charlie']),
                    'content_class': 'maintainer_only',
                    'applies_to': ['gemini_dcoir_agent'],
                    'gemini_attachment_disposition': (
                        'include_direct_from_canonical_source'
                    ),
                    'openai_dcoir_projection_group': None,
                    'openai_usb_projection_group': None,
                },
                {
                    'id': 'knowledge.delta',
                    'source_path': 'knowledge/delta.md',
                    'source_git_blob_sha': _git_blob_sha(self.contents['delta']),
                    'content_class': 'runtime_reference',
                    'applies_to': [
                        'gemini_dcoir_agent',
                        'openai_dcoir_analyst',
                    ],
                    'gemini_attachment_disposition': (
                        'include_direct_from_canonical_source'
                    ),
                    'openai_dcoir_projection_group': 'dcoir_core',
                    'openai_usb_projection_group': None,
                },
            ],
        }
        self._write_contract(contract)
        _write_json(
            self.bundle_path,
            {
                'knowledge_attachment_sources': [
                    'knowledge/alpha.md',
                    'knowledge/bravo.md',
                    'knowledge/charlie.md',
                    'knowledge/delta.md',
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
                'canonical_projection_source_roots': [
                    'project_sources/agent_runtime/knowledge_modules'
                ],
                'generated_root': 'project_sources/agent_runtime/generated/knowledge',
                'expected_canonical_source_count': 4,
                'expected_projection_source_count': 1,
                'strict_file_count_ceiling': 4,
                'targets': {
                    'gemini_dcoir_agent': {
                        'mode': 'direct_canonical_attachments',
                        'bundle_manifest': (
                            'project_sources/gemini/bundle_source/'
                            'Gemini_Bundle_Source_Manifest.json'
                        ),
                        'expected_attachment_count': 4,
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
        errors, _ = projector.project_knowledge(
            self.repo, self.manifest_path, check=False
        )
        self.assertEqual(errors, [])

    def _evaluate(
        self,
        *,
        live_status: str = 'unavailable',
        live_run: str | None = None,
        manifest: Path | None = None,
        tracker: int = 184,
    ) -> tuple[list[str], dict[str, object]]:
        return evaluator.evaluate_consolidation(
            self.repo,
            manifest or self.manifest_path,
            baseline_commit='fixture-base',
            live_evidence_status=live_status,
            live_evidence_run=live_run,
            behavior_tracker_issue=tracker,
        )

    def _snapshot(self) -> dict[str, str]:
        return {
            path.relative_to(self.repo).as_posix(): _file_digest(path)
            for path in sorted(self.repo.rglob('*'))
            if path.is_file()
        }

    def test_clean_candidate_is_lossless_and_deferred_without_live_evidence(self) -> None:
        errors, report = self._evaluate()
        self.assertEqual(errors, [])
        self.assertTrue(report['success'])
        self.assertEqual(report['baseline']['active_attachment_count'], 4)
        self.assertEqual(report['candidate']['file_count'], 3)
        self.assertEqual(report['candidate']['source_count'], 4)
        self.assertEqual(report['candidate']['attachment_reduction_count'], 1)
        self.assertTrue(report['candidate']['exact_source_coverage'])
        self.assertTrue(report['candidate']['lossless_reconstruction'])
        self.assertTrue(report['candidate']['active_contract_unchanged'])
        self.assertEqual(
            report['candidate']['gemini_only_source_ids'],
            ['knowledge.gemini.only'],
        )
        self.assertEqual(report['decision']['recommended'], 'DEFER')

    def test_candidate_output_is_deterministic(self) -> None:
        first_errors, first = self._evaluate()
        second_errors, second = self._evaluate()
        self.assertEqual(first_errors, [])
        self.assertEqual(second_errors, [])
        self.assertEqual(first, second)

    def test_live_pass_requires_specific_run(self) -> None:
        errors, report = self._evaluate(live_status='pass')
        self.assertTrue(any('live_evidence_run is required' in error for error in errors))
        self.assertEqual(report['decision']['recommended'], 'REVISE')

    def test_live_pass_with_run_can_recommend_promote(self) -> None:
        errors, report = self._evaluate(
            live_status='pass',
            live_run='https://example.invalid/run/123',
        )
        self.assertEqual(errors, [])
        self.assertEqual(report['decision']['recommended'], 'PROMOTE')

    def test_live_failure_defers(self) -> None:
        errors, report = self._evaluate(
            live_status='fail',
            live_run='https://example.invalid/run/124',
        )
        self.assertEqual(errors, [])
        self.assertEqual(report['decision']['recommended'], 'DEFER')

    def test_live_failure_requires_specific_run(self) -> None:
        errors, report = self._evaluate(live_status='fail')
        self.assertTrue(
            any('live_evidence_run is required' in error for error in errors)
        )
        self.assertEqual(report['decision']['recommended'], 'REVISE')

    def test_missing_source_fails_closed(self) -> None:
        (self.repo / 'knowledge/charlie.md').unlink()
        errors, report = self._evaluate()
        self.assertTrue(errors)
        self.assertFalse(report['success'])
        self.assertEqual(report['decision']['recommended'], 'REVISE')

    def test_source_hash_drift_fails_closed(self) -> None:
        (self.repo / 'knowledge/bravo.md').write_bytes(b'# Bravo\n\nDrifted.\n')
        errors, report = self._evaluate()
        self.assertTrue(any('Git blob SHA mismatch' in error for error in errors))
        self.assertFalse(report['success'])

    def test_duplicate_source_is_rejected(self) -> None:
        contract = self._read_json(self.contract_path)
        duplicate = copy.deepcopy(contract['knowledge_items'][1])
        contract['knowledge_items'].append(duplicate)
        self._write_contract(contract)
        errors, report = self._evaluate()
        self.assertTrue(any('Duplicate knowledge id' in error for error in errors))
        self.assertEqual(report['decision']['recommended'], 'REVISE')

    def test_unknown_candidate_group_is_rejected(self) -> None:
        contract = self._read_json(self.contract_path)
        contract['knowledge_items'][3]['openai_dcoir_projection_group'] = 'unknown'
        self._write_contract(contract)
        errors, report = self._evaluate()
        self.assertTrue(
            any('unknown' in error.casefold() for error in errors),
            errors,
        )
        self.assertEqual(report['decision']['recommended'], 'REVISE')

    def test_unsafe_candidate_group_id_is_rejected(self) -> None:
        contract = self._read_json(self.contract_path)
        contract['knowledge_projection_groups'][0]['id'] = 'bad/group'
        contract['knowledge_items'][0]['openai_dcoir_projection_group'] = 'bad/group'
        contract['knowledge_items'][3]['openai_dcoir_projection_group'] = 'bad/group'
        self._write_contract(contract)
        errors, report = self._evaluate()
        self.assertTrue(
            any('unsafe' in error.casefold() and 'group' in error.casefold() for error in errors),
            errors,
        )
        self.assertEqual(report['decision']['recommended'], 'REVISE')

    def test_active_gemini_mode_cannot_be_silently_changed(self) -> None:
        manifest = self._read_json(self.manifest_path)
        manifest['targets']['gemini_dcoir_agent']['mode'] = 'consolidated_projection'
        self._write_manifest(manifest)
        errors, report = self._evaluate()
        self.assertTrue(
            any('direct_canonical_attachments' in error for error in errors),
            errors,
        )
        self.assertFalse(report['candidate']['active_contract_unchanged'])

    def test_malformed_manifest_fails_closed(self) -> None:
        self.manifest_path.write_text('{not-json', encoding='utf-8')
        errors, report = self._evaluate()
        self.assertTrue(errors)
        self.assertFalse(report['success'])
        self.assertEqual(report['decision']['recommended'], 'REVISE')

    def test_manifest_path_traversal_is_rejected(self) -> None:
        errors, report = self._evaluate(manifest=Path('../outside.json'))
        self.assertTrue(
            any('traversal' in error or 'inside the repository' in error for error in errors),
            errors,
        )
        self.assertFalse(report['success'])

    def test_underlying_resolver_failure_is_reported_not_raised(self) -> None:
        with mock.patch.object(
            evaluator.knowledge_projection,
            'project_knowledge',
            side_effect=RuntimeError('symlink loop'),
        ):
            errors, report = self._evaluate()
        self.assertTrue(
            any('symlink loop' in error for error in errors),
            errors,
        )
        self.assertEqual(report['decision']['recommended'], 'REVISE')

    def test_corrupt_candidate_recovery_is_rejected(self) -> None:
        with mock.patch.object(
            evaluator.knowledge_projection,
            'recover_projection',
            return_value=[],
        ):
            errors, report = self._evaluate()
        self.assertTrue(errors)
        self.assertFalse(report['candidate']['exact_source_coverage'])
        self.assertFalse(report['candidate']['lossless_reconstruction'])

    def test_extra_recovered_candidate_source_is_rejected(self) -> None:
        original_recover = evaluator.knowledge_projection.recover_projection
        injected = False

        def recover_with_extra(data: bytes) -> list[dict[str, object]]:
            nonlocal injected
            recovered = original_recover(data)
            if (
                recovered
                and not injected
                and b'- Target: gemini_dcoir_agent_candidate\n' in data
            ):
                injected = True
                recovered.append(
                    {
                        'metadata': {'id': 'knowledge.unexpected.extra'},
                        'content': b'unexpected extra source',
                    }
                )
            return recovered

        with mock.patch.object(
            evaluator.knowledge_projection,
            'recover_projection',
            side_effect=recover_with_extra,
        ):
            errors, report = self._evaluate()
        self.assertTrue(injected)
        self.assertTrue(errors)
        self.assertTrue(
            any(
                'not losslessly recoverable' in error
                or 'source coverage' in error
                for error in errors
            ),
            errors,
        )
        self.assertFalse(report['candidate']['exact_source_coverage'])
        self.assertFalse(report['candidate']['lossless_reconstruction'])
        self.assertEqual(report['decision']['recommended'], 'REVISE')

    def test_evaluation_does_not_mutate_active_repository_state(self) -> None:
        before = self._snapshot()
        errors, _ = self._evaluate()
        after = self._snapshot()
        self.assertEqual(errors, [])
        self.assertEqual(before, after)

    def test_virtual_candidate_paths_stay_on_evaluation_surface(self) -> None:
        errors, report = self._evaluate()
        self.assertEqual(errors, [])
        prefix = (
            'project_sources/agent_runtime/generated/evaluations/'
            'gemini_knowledge_consolidation/'
        )
        self.assertTrue(report['candidate']['groups'])
        for group in report['candidate']['groups']:
            self.assertTrue(group['virtual_output_path'].startswith(prefix))

    def test_markdown_decision_matches_report(self) -> None:
        errors, report = self._evaluate()
        self.assertEqual(errors, [])
        markdown = evaluator._render_markdown(report)
        self.assertIn('Recommended decision: **DEFER**', markdown)
        self.assertIn('Active attachment count: 4', markdown)
        self.assertIn('Candidate file count: 3', markdown)

    def test_invalid_direct_api_inputs_fail_closed(self) -> None:
        errors, report = evaluator.evaluate_consolidation(
            self.repo,
            self.manifest_path,
            live_evidence_status='maybe',
            behavior_tracker_issue=0,
        )
        self.assertTrue(any('live_evidence_status' in error for error in errors))
        self.assertTrue(any('behavior_tracker_issue' in error for error in errors))
        self.assertEqual(report['decision']['recommended'], 'REVISE')


if __name__ == '__main__':
    unittest.main(verbosity=2)
