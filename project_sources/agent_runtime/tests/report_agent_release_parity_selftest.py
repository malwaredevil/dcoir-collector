#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'project_sources/agent_runtime/tools/report_agent_release_parity.py'
SPEC = importlib.util.spec_from_file_location('report_agent_release_parity', SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise SystemExit('Unable to load report_agent_release_parity.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def write_json(root: Path, rel: str, value: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def write_text(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def target(target_id: str, provider: str, instruction_mode: str, knowledge_mode: str) -> dict:
    return {
        'id': target_id,
        'provider': provider,
        'runtime_model': 'fixture-model' if target_id != 'gemini_dcoir_agent' else 'runtime_managed',
        'instruction_mode': instruction_mode,
        'knowledge_mode': knowledge_mode,
        'capabilities': {'web_search': False, 'actions': False},
        'runtime_dependent_capabilities': ['enterprise_grounding'] if target_id == 'gemini_dcoir_agent' else [],
        'generated_outputs': ['fixture'],
    }


def source_manifest() -> dict:
    return {
        'schema': 'dcoir.agent_runtime.source_contract.v1',
        'source_contract_version': 'fixture-1',
        'target_ids': list(module.EXPECTED_TARGET_IDS),
        'targets': [
            target('gemini_dcoir_agent', 'gemini', 'prime_plus_sub_agents', 'direct_canonical_attachments'),
            target('openai_dcoir_analyst', 'openai', 'static_instructions', 'static_knowledge'),
            target('openai_usb_reporting', 'openai', 'static_instructions', 'static_knowledge'),
        ],
        'generated_artifact_policy': {
            'generated_outputs_are_canonical': False,
            'reverse_reconciliation_required': True,
        },
        'behavior_items': [
            {'id': 'shared.1', 'canonical': True, 'applies_to': list(module.EXPECTED_TARGET_IDS)},
            {'id': 'shared.2', 'canonical': True, 'applies_to': ['gemini_dcoir_agent', 'openai_dcoir_analyst']},
            {'id': 'gemini.nonmodule.1', 'canonical': True, 'applies_to': ['gemini_dcoir_agent']},
            {'id': 'generated.1', 'canonical': False, 'applies_to': ['gemini_dcoir_agent']},
        ],
    }


def openai_package(target_id: str, behavior_count: int, knowledge_count: int) -> dict:
    return {
        'schema': f'dcoir.agent_runtime.{target_id}.v1',
        'target_id': target_id,
        'adapter_contract_version': 'fixture-1',
        'source_base_commit': 'base-fixture',
        'behavior_coverage_count': behavior_count,
        'behavior_source_snapshot_sha256': 'a' * 64,
        'knowledge_file_count': knowledge_count,
        'strict_knowledge_file_ceiling': 20,
        'knowledge_files': [
            {'id': f'k{i}', 'order': i, 'path': f'knowledge/{target_id}/{i}.md', 'sha256': 'b' * 64}
            for i in range(knowledge_count)
        ],
        'generated_files': [
            {'path': f'packages/{target_id}/Instructions.md', 'sha256': 'c' * 64, 'bytes': 10}
        ],
        'generated_outputs_are_canonical': False,
        'direct_target_edits_require_reverse_reconciliation': True,
        'manual_deployment_required': True,
        'live_webui_validation_performed': False,
    }


def stage_repo() -> tuple[tempfile.TemporaryDirectory, Path]:
    td = tempfile.TemporaryDirectory(prefix='agent-release-parity-selftest-')
    root = Path(td.name)
    write_json(root, module.SHARED_MANIFEST.as_posix(), source_manifest())
    write_json(
        root,
        module.BEHAVIOR_MANIFEST.as_posix(),
        {
            'schema': 'dcoir.agent_runtime.behavior_modules.v1',
            'module_contract_version': 'fixture-1',
            'target_adapters': {
                'gemini_dcoir_agent': {
                    'expected_prime_chunks': 1,
                    'expected_specialists': 1,
                }
            },
            'modules': [
                {
                    'id': 'shared.1',
                    'kind': 'prime_chunk',
                    'projections': {
                        'gemini_dcoir_agent': {
                            'output_path': 'generated/prime.md',
                            'sha256': 'd' * 64,
                        }
                    },
                },
                {
                    'id': 'shared.2',
                    'kind': 'specialist',
                    'projections': {
                        'gemini_dcoir_agent': {
                            'output_path': 'generated/specialist.md',
                            'sha256': 'e' * 64,
                        }
                    },
                },
            ],
        },
    )
    write_json(
        root,
        module.KNOWLEDGE_MANIFEST.as_posix(),
        {
            'schema': 'dcoir.agent_runtime.knowledge_projection.v1',
            'projection_contract_version': 'fixture-1',
            'targets': {
                'gemini_dcoir_agent': {
                    'expected_attachment_count': 2,
                    'bundle_manifest': module.GEMINI_MANIFEST.as_posix(),
                },
                'openai_dcoir_analyst': {
                    'expected_projection_count': 2,
                    'target_manifest_path': module.OPENAI_PACKAGE_MANIFESTS['openai_dcoir_analyst'].as_posix(),
                },
                'openai_usb_reporting': {
                    'expected_projection_count': 1,
                    'target_manifest_path': module.OPENAI_PACKAGE_MANIFESTS['openai_usb_reporting'].as_posix(),
                },
            },
        },
    )
    write_json(
        root,
        module.GEMINI_MANIFEST.as_posix(),
        {
            'bundle_name': 'Fixture Gemini',
            'bundle_version': 'fixture-1',
            'knowledge_attachment_sources': ['knowledge/a.md', 'knowledge/b.md'],
            'required_files': ['README.md', 'Prime.md'],
        },
    )
    write_json(
        root,
        module.OPENAI_PACKAGE_MANIFESTS['openai_dcoir_analyst'].as_posix(),
        openai_package('openai_dcoir_analyst', 2, 2),
    )
    write_json(
        root,
        module.OPENAI_PACKAGE_MANIFESTS['openai_usb_reporting'].as_posix(),
        openai_package('openai_usb_reporting', 1, 1),
    )
    guide = '\n\n'.join(module.GUIDE_MARKERS) + '\n'
    write_text(root, module.MANUAL_GUIDE.as_posix(), guide)
    return td, root


def build(root: Path):
    return module.build_release_report(root, source_commit='fixture-commit', run_target_checks=False)


def test_valid_fixture_and_reporting_fields() -> None:
    td, root = stage_repo()
    try:
        errors, report = build(root)
        assert not errors, errors
        assert report['static_parity_status'] == 'pass'
        assert report['live_parity_status'] == 'pending_manual_readback'
        assert [item['id'] for item in report['targets']] == list(module.EXPECTED_TARGET_IDS)
        gemini_behavior = report['targets'][0]['behavior']
        assert gemini_behavior['expected_canonical_items'] == 3
        assert gemini_behavior['expected_module_count'] == 2
        assert gemini_behavior['reported_module_count'] == 2
        assert gemini_behavior['reported_prime_chunk_count'] == 1
        assert gemini_behavior['reported_specialist_count'] == 1
        assert report['targets'][0]['bundle_version'] == 'fixture-1'
        assert report['targets'][1]['knowledge']['reported_file_count'] == 2
        assert report['targets'][2]['behavior']['reported_coverage_count'] == 1
        assert report['governed_provider_differences']
        assert len(report['pending_live_evidence']) == 2
    finally:
        td.cleanup()


def test_deterministic_json_and_markdown() -> None:
    td, root = stage_repo()
    try:
        errors1, report1 = build(root)
        errors2, report2 = build(root)
        assert not errors1 and not errors2
        assert json.dumps(report1, sort_keys=True) == json.dumps(report2, sort_keys=True)
        assert module.render_markdown(report1) == module.render_markdown(report2)
    finally:
        td.cleanup()


def test_unknown_target_fails_closed() -> None:
    td, root = stage_repo()
    try:
        path = root / module.SHARED_MANIFEST
        value = json.loads(path.read_text(encoding='utf-8'))
        value['target_ids'].append('surprise_target')
        value['targets'].append(target('surprise_target', 'other', 'other', 'other'))
        write_json(root, module.SHARED_MANIFEST.as_posix(), value)
        errors, report = build(root)
        assert any('target_ids must exactly equal' in error for error in errors), errors
        assert report['static_parity_status'] == 'fail'
    finally:
        td.cleanup()


def test_missing_required_manifest_fails_closed() -> None:
    td, root = stage_repo()
    try:
        (root / module.OPENAI_PACKAGE_MANIFESTS['openai_usb_reporting']).unlink()
        errors, _ = build(root)
        assert any('Missing manifest' in error for error in errors), errors
    finally:
        td.cleanup()


def test_source_hash_changes_after_source_edit() -> None:
    td, root = stage_repo()
    try:
        errors, report1 = build(root)
        assert not errors
        path = root / module.SHARED_MANIFEST
        value = json.loads(path.read_text(encoding='utf-8'))
        value['source_contract_version'] = 'fixture-2'
        write_json(root, module.SHARED_MANIFEST.as_posix(), value)
        errors, report2 = build(root)
        assert not errors
        assert (
            report1['source_contracts']['shared_source_contract']['sha256']
            != report2['source_contracts']['shared_source_contract']['sha256']
        )
    finally:
        td.cleanup()


def test_knowledge_count_mismatch_is_blocking_gap() -> None:
    td, root = stage_repo()
    try:
        path = root / module.OPENAI_PACKAGE_MANIFESTS['openai_dcoir_analyst']
        value = json.loads(path.read_text(encoding='utf-8'))
        value['knowledge_file_count'] = 1
        write_json(root, module.OPENAI_PACKAGE_MANIFESTS['openai_dcoir_analyst'].as_posix(), value)
        errors, report = build(root)
        assert any('knowledge file count mismatch' in error for error in errors), errors
        assert report['blocking_parity_gaps']
    finally:
        td.cleanup()


def test_projection_manifest_path_escape_is_rejected() -> None:
    td, root = stage_repo()
    try:
        path = root / module.KNOWLEDGE_MANIFEST
        value = json.loads(path.read_text(encoding='utf-8'))
        value['targets']['openai_usb_reporting']['target_manifest_path'] = '../outside.json'
        write_json(root, module.KNOWLEDGE_MANIFEST.as_posix(), value)
        errors, _ = build(root)
        assert any('without traversal' in error for error in errors), errors
    finally:
        td.cleanup()


def test_manual_guide_marker_is_required() -> None:
    td, root = stage_repo()
    try:
        write_text(root, module.MANUAL_GUIDE.as_posix(), '# incomplete\n')
        errors, report = build(root)
        assert any('guide missing required marker' in error for error in errors), errors
        assert report['manual_deployment_readback_guide']['required_markers_present'] is False
    finally:
        td.cleanup()


def test_live_readback_state_changes_when_recorded() -> None:
    td, root = stage_repo()
    try:
        for target_id in ('openai_dcoir_analyst', 'openai_usb_reporting'):
            path = root / module.OPENAI_PACKAGE_MANIFESTS[target_id]
            value = json.loads(path.read_text(encoding='utf-8'))
            value['live_webui_validation_performed'] = True
            write_json(root, module.OPENAI_PACKAGE_MANIFESTS[target_id].as_posix(), value)
        errors, report = build(root)
        assert not errors, errors
        assert report['pending_live_evidence'] == []
        assert report['live_parity_status'] == 'readback_recorded'
    finally:
        td.cleanup()


def test_gemini_module_contract_mismatch_is_blocking_gap() -> None:
    td, root = stage_repo()
    try:
        path = root / module.BEHAVIOR_MANIFEST
        value = json.loads(path.read_text(encoding='utf-8'))
        value['target_adapters']['gemini_dcoir_agent']['expected_specialists'] = 2
        write_json(root, module.BEHAVIOR_MANIFEST.as_posix(), value)
        errors, report = build(root)
        assert any('behavior module mismatch' in error for error in errors), errors
        assert report['static_parity_status'] == 'fail'
    finally:
        td.cleanup()


def test_write_outputs_are_parseable_and_consistent() -> None:
    td, root = stage_repo()
    try:
        errors, report = build(root)
        assert not errors
        output = root / 'out'
        json_path, markdown_path = module.write_outputs(report, output)
        parsed = json.loads(json_path.read_text(encoding='utf-8'))
        assert parsed == report
        markdown = markdown_path.read_text(encoding='utf-8')
        assert f"`{report['source_commit']}`" in markdown
        assert f"**{report['static_parity_status']}**" in markdown
    finally:
        td.cleanup()


def main() -> int:
    tests = [
        test_valid_fixture_and_reporting_fields,
        test_deterministic_json_and_markdown,
        test_unknown_target_fails_closed,
        test_missing_required_manifest_fails_closed,
        test_source_hash_changes_after_source_edit,
        test_knowledge_count_mismatch_is_blocking_gap,
        test_projection_manifest_path_escape_is_rejected,
        test_manual_guide_marker_is_required,
        test_live_readback_state_changes_when_recorded,
        test_gemini_module_contract_mismatch_is_blocking_gap,
        test_write_outputs_are_parseable_and_consistent,
    ]
    for test in tests:
        test()
    print(json.dumps({'success': True, 'tests': [test.__name__ for test in tests]}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
