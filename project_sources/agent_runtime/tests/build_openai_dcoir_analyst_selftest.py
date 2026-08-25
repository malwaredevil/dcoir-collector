#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_PATH = (
    REPO_ROOT / 'project_sources/agent_runtime/tools/build_openai_dcoir_analyst.py'
)
SPEC = importlib.util.spec_from_file_location('build_openai_dcoir_analyst', TOOL_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError('Unable to load OpenAI DCOIR build tool')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

MANIFEST_REL = Path(
    'project_sources/agent_runtime/provider_adapters/'
    'openai_dcoir_analyst/Adapter_Manifest.json'
)
COPY_PATHS = (
    Path('project_sources/agent_runtime/Shared_Agent_Source_Manifest.json'),
    Path('project_sources/agent_runtime/Behavior_Module_Manifest.json'),
    Path('project_sources/agent_runtime/Knowledge_Projection_Manifest.json'),
    Path('project_sources/agent_runtime/behavior_modules'),
    Path('project_sources/agent_runtime/provider_adapters/openai_dcoir_analyst'),
    Path('project_sources/agent_runtime/generated/knowledge/openai_dcoir_analyst'),
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


class OpenAIDCOIRBuildSelfTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        for relative in COPY_PATHS:
            source = REPO_ROOT / relative
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
        self.manifest_path = self.repo / MANIFEST_REL

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self, check: bool = False) -> tuple[list[str], dict]:
        return MODULE.build_package(self.repo, self.manifest_path, check=check)

    def materialize_valid(self) -> None:
        errors, _ = self.build(check=False)
        self.assertEqual([], errors)

    def assert_error_contains(self, expected: str, check: bool = True) -> None:
        errors, _ = self.build(check=check)
        self.assertTrue(
            any(expected in error for error in errors),
            f'{expected!r} not found in {errors!r}',
        )

    def test_valid_materialize_and_check(self) -> None:
        self.materialize_valid()
        errors, report = self.build(check=True)
        self.assertEqual([], errors)
        self.assertTrue(report['success'])
        self.assertEqual(30, report['behavior_coverage_count'])
        self.assertEqual(16, report['behavioral_case_count'])
        self.assertEqual(7, report['knowledge_file_count'])
        self.assertEqual(3, report['generated_file_count'])

    def test_repeated_materialization_is_deterministic(self) -> None:
        self.materialize_valid()
        generated = self.repo / (
            'project_sources/agent_runtime/generated/packages/openai_dcoir_analyst'
        )
        first = {path.name: path.read_bytes() for path in generated.iterdir()}
        self.materialize_valid()
        second = {path.name: path.read_bytes() for path in generated.iterdir()}
        self.assertEqual(first, second)

    def test_behavior_source_drift_fails(self) -> None:
        path = self.repo / (
            'project_sources/agent_runtime/behavior_modules/prime/prime.chunk.00.md'
        )
        path.write_text(path.read_text(encoding='utf-8') + '\ndrift\n', encoding='utf-8')
        self.assert_error_contains('Behavior source hash drift', check=False)
        self.assert_error_contains('Behavior source snapshot drift', check=False)

    def test_duplicate_coverage_fails(self) -> None:
        manifest = _read_json(self.manifest_path)
        manifest['coverage'].insert(1, manifest['coverage'][0])
        _write_json(self.manifest_path, manifest)
        self.assert_error_contains('Duplicate behavior coverage id', check=False)

    def test_reordered_coverage_fails(self) -> None:
        manifest = _read_json(self.manifest_path)
        manifest['coverage'][0], manifest['coverage'][1] = (
            manifest['coverage'][1], manifest['coverage'][0]
        )
        _write_json(self.manifest_path, manifest)
        self.assert_error_contains('Behavior coverage must exactly match', check=False)

    def test_unsupported_capability_fails(self) -> None:
        manifest = _read_json(self.manifest_path)
        manifest['capabilities']['web_search'] = True
        _write_json(self.manifest_path, manifest)
        self.assert_error_contains('Unsupported capability must remain false', check=False)

    def test_unknown_capability_fails(self) -> None:
        manifest = _read_json(self.manifest_path)
        manifest['capabilities']['browser'] = False
        _write_json(self.manifest_path, manifest)
        self.assert_error_contains('exactly the governed keys', check=False)

    def test_missing_behavioral_marker_fails(self) -> None:
        path = self.repo / (
            'project_sources/agent_runtime/provider_adapters/'
            'openai_dcoir_analyst/Instructions.md'
        )
        path.write_text(
            path.read_text(encoding='utf-8').replace('bounded absence', 'empty result'),
            encoding='utf-8',
        )
        self.assert_error_contains('zero_result missing Instructions marker', check=False)

    def test_missing_action_state_marker_fails(self) -> None:
        path = self.repo / (
            'project_sources/agent_runtime/provider_adapters/'
            'openai_dcoir_analyst/Instructions.md'
        )
        path.write_text(
            path.read_text(encoding='utf-8').replace('planned action:', 'planned:'),
            encoding='utf-8',
        )
        self.assert_error_contains('required static contract marker', check=False)

    def test_provider_topology_leak_fails(self) -> None:
        path = self.repo / (
            'project_sources/agent_runtime/provider_adapters/'
            'openai_dcoir_analyst/Instructions.md'
        )
        path.write_text(
            path.read_text(encoding='utf-8') + '\nYou are the Prime Agent.\n',
            encoding='utf-8',
        )
        self.assert_error_contains('Provider-topology leakage', check=False)

    def test_knowledge_projection_drift_fails(self) -> None:
        path = self.repo / (
            'project_sources/agent_runtime/generated/knowledge/'
            'openai_dcoir_analyst/01-dcoir-core.md'
        )
        path.write_bytes(path.read_bytes() + b'drift')
        self.assert_error_contains('Knowledge projection drift', check=False)

    def test_generated_instruction_drift_fails(self) -> None:
        self.materialize_valid()
        path = self.repo / (
            'project_sources/agent_runtime/generated/packages/'
            'openai_dcoir_analyst/Instructions.md'
        )
        path.write_bytes(path.read_bytes() + b'drift')
        self.assert_error_contains('Generated package drift')

    def test_stale_generated_file_fails(self) -> None:
        self.materialize_valid()
        path = self.repo / (
            'project_sources/agent_runtime/generated/packages/'
            'openai_dcoir_analyst/stale.txt'
        )
        path.write_text('stale', encoding='utf-8')
        self.assert_error_contains('Stale generated package files')

    def test_generated_path_escape_fails(self) -> None:
        manifest = _read_json(self.manifest_path)
        manifest['generated_outputs']['instructions'] = '../escape.md'
        _write_json(self.manifest_path, manifest)
        self.assert_error_contains('must not be absolute or contain traversal', check=False)

    def test_generated_root_rebinding_fails(self) -> None:
        manifest = _read_json(self.manifest_path)
        manifest['generated_root'] = 'project_sources/agent_runtime/generated/packages'
        _write_json(self.manifest_path, manifest)
        self.assert_error_contains('generated_root must remain bound', check=False)

    def test_canonical_source_rebinding_fails(self) -> None:
        manifest = _read_json(self.manifest_path)
        manifest['canonical_instructions_source'] = (
            'project_sources/agent_runtime/README.md'
        )
        _write_json(self.manifest_path, manifest)
        self.assert_error_contains(
            'canonical_instructions_source must remain bound', check=False
        )

    def test_invalid_source_base_commit_fails(self) -> None:
        manifest = _read_json(self.manifest_path)
        manifest['source_base_commit'] = 'main'
        _write_json(self.manifest_path, manifest)
        self.assert_error_contains('source_base_commit must be', check=False)

    def test_knowledge_source_contract_drift_fails(self) -> None:
        manifest = _read_json(self.manifest_path)
        target_path = self.repo / manifest['knowledge_target_manifest']
        target = _read_json(target_path)
        target['source_contract_sha256'] = '0' * 64
        _write_json(target_path, target)
        self.assert_error_contains('Knowledge target source-contract hash drift', check=False)

    def test_editor_identity_drift_fails(self) -> None:
        manifest = _read_json(self.manifest_path)
        manifest['editor']['name'] = 'Generic Analyst'
        _write_json(self.manifest_path, manifest)
        self.assert_error_contains('Editor name must remain', check=False)

    def test_duplicate_behavioral_case_fails(self) -> None:
        manifest = _read_json(self.manifest_path)
        cases_path = self.repo / manifest['behavioral_cases']
        cases = _read_json(cases_path)
        cases['cases'].append(cases['cases'][0])
        _write_json(cases_path, cases)
        self.assert_error_contains('Duplicate behavioral case id', check=False)

    def test_behavioral_case_without_scenario_fails(self) -> None:
        manifest = _read_json(self.manifest_path)
        cases_path = self.repo / manifest['behavioral_cases']
        cases = _read_json(cases_path)
        cases['cases'][0]['scenario'] = ''
        _write_json(cases_path, cases)
        self.assert_error_contains('lacks a non-empty scenario', check=False)

    def test_behavioral_cases_cannot_claim_live_evidence(self) -> None:
        manifest = _read_json(self.manifest_path)
        cases_path = self.repo / manifest['behavioral_cases']
        cases = _read_json(cases_path)
        cases['live_model_evidence'] = True
        _write_json(cases_path, cases)
        self.assert_error_contains('must not claim live model evidence', check=False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
