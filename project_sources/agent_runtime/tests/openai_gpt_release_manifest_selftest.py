#!/usr/bin/env python3
"""Independent source and Knowledge manifest binding checks for the governed OpenAI GPT deployment release."""
from __future__ import annotations

import json
from pathlib import Path

from openai_gpt_release_test_fixture import (
    module,
    stage_repo,
    _build,
)

def _rewrite_governed_manifest(repo: Path, basename: str, mutate) -> None:
    path = repo / 'project_sources/agent_runtime' / basename
    value = json.loads(path.read_text(encoding='utf-8'))
    mutate(value)
    path.write_bytes(module._json_bytes(value))


def _assert_rejected_manifest_release(repo: Path, *fragments: str, early: bool = True) -> None:
    errors, report = _build(repo, 'bad_manifest')
    assert errors and report['success'] is False, report
    for fragment in fragments:
        assert any(fragment in err for err in errors), errors
    assert report['zip_path'] is None, report
    if early:
        assert not (repo / 'project_sources/validation/bad_manifest').exists()


def test_governed_runtime_model_source_and_package_must_agree() -> None:
    td, repo = stage_repo()
    try:
        _rewrite_governed_manifest(repo, 'Shared_Agent_Source_Manifest.json', lambda doc: next(
            target for target in doc['targets'] if target['id'] == 'openai_usb_reporting'
        ).update(runtime_model='GPT-TEST-NEW'))
        _assert_rejected_manifest_release(repo, 'runtime model drift', early=False)
    finally:
        td.cleanup()

    td, repo = stage_repo()
    try:
        _rewrite_governed_manifest(repo, 'Shared_Agent_Source_Manifest.json', lambda doc: next(
            target for target in doc['targets'] if target['id'] == 'openai_usb_reporting'
        ).update(runtime_model='GPT-TEST-NEW'))
        config_path = repo / 'project_sources/agent_runtime/generated/packages/openai_usb_reporting/GPT_Configuration.json'
        config = json.loads(config_path.read_text(encoding='utf-8'))
        config['runtime_model'] = 'GPT-TEST-NEW'
        config_path.write_bytes(module._json_bytes(config))
        errors, report = _build(repo, 'new_model')
        assert not errors, errors
        assert report['success'] and report['zip_path'], report
        assert next(item for item in report['targets'] if item['target_id'] == 'openai_usb_reporting')[
            'runtime_model'
        ] == 'GPT-TEST-NEW'
    finally:
        td.cleanup()


def test_release_source_manifest_invalid_values_fail_before_writing() -> None:
    source_name = 'Shared_Agent_Source_Manifest.json'
    for case in ('absent', 'bad_json', 'invalid_utf8', 'missing_model',
                 'invalid_model_type', 'invalid_model_control', 'invalid_model_surrogate',
                 'wrong_provider', 'duplicate_target', 'wrong_schema', 'invalid_target_ids'):
        td, repo = stage_repo()
        try:
            source_path = repo / 'project_sources/agent_runtime' / source_name
            if case == 'absent':
                source_path.unlink()
                expected = 'Missing'
            elif case in ('bad_json', 'invalid_utf8'):
                source_path.write_bytes(b'{' if case == 'bad_json' else b'\xff')
                expected = 'Invalid JSON' if case == 'bad_json' else 'invalid UTF-8'
            else:
                doc = json.loads(source_path.read_text(encoding='utf-8'))
                target = next(item for item in doc['targets'] if item['id'] == 'openai_dcoir_analyst')
                expected = {
                    'missing_model': 'source runtime model is missing',
                    'invalid_model_type': 'source runtime model is missing',
                    'invalid_model_control': 'source runtime model is missing',
                    'invalid_model_surrogate': 'source runtime model is missing',
                    'wrong_provider': 'source provider is not',
                    'duplicate_target': 'must appear exactly once',
                    'wrong_schema': 'source contract schema drift',
                    'invalid_target_ids': 'target_ids must be',
                }[case]
                if case == 'missing_model':
                    del target['runtime_model']
                elif case == 'invalid_model_type':
                    target['runtime_model'] = 123
                elif case == 'invalid_model_control':
                    target['runtime_model'] = 'GPT-INVALID\nINJECTED'
                elif case == 'invalid_model_surrogate':
                    target['runtime_model'] = 'GPT-INVALID\ud800'
                elif case == 'wrong_provider':
                    target['provider'] = 'other_runtime'
                elif case == 'duplicate_target':
                    doc['targets'].append(dict(target))
                elif case == 'wrong_schema':
                    doc['schema'] = 'unsupported'
                elif case == 'invalid_target_ids':
                    doc['target_ids'] = 'not-an-array'
                source_path.write_bytes(module._json_bytes(doc))
            _assert_rejected_manifest_release(repo, expected)
        finally:
            td.cleanup()


def test_release_knowledge_count_and_cross_manifest_integrity() -> None:
    proj_name = 'Knowledge_Projection_Manifest.json'
    for case in ('boolean_count', 'missing_group', 'unhashable_id', 'duplicate_group_id',
                 'bad_group_order', 'source_group_drift', 'mismatched_ceiling',
                 'projection_schema', 'nonobject_targets'):
        td, repo = stage_repo()
        try:
            path = repo / 'project_sources/agent_runtime' / proj_name
            doc = json.loads(path.read_text(encoding='utf-8'))
            usb = doc['targets']['openai_usb_reporting']
            expected = {
                'boolean_count': 'count is invalid',
                'missing_group': 'count/group mismatch',
                'unhashable_id': 'ids must be nonempty strings',
                'duplicate_group_id': 'group ids must be unique',
                'bad_group_order': 'group order is not contiguous',
                'source_group_drift': 'cross-manifest Knowledge projection group drift',
                'mismatched_ceiling': 'file ceilings disagree',
                'projection_schema': 'Knowledge projection schema drift',
                'nonobject_targets': 'projection targets must be an object',
            }[case]
            if case == 'boolean_count':
                usb['expected_projection_count'] = True
            elif case == 'missing_group':
                usb['projection_groups'] = []
            elif case == 'unhashable_id':
                usb['projection_groups'][0]['id'] = []
            elif case == 'duplicate_group_id':
                groups = doc['targets']['openai_dcoir_analyst']['projection_groups']
                groups[1]['id'] = groups[0]['id']
            elif case == 'bad_group_order':
                usb['projection_groups'][0]['order'] = 2
            elif case == 'source_group_drift':
                usb['projection_groups'][0]['id'] = 'unauthorized_group'
            elif case == 'mismatched_ceiling':
                doc['strict_file_count_ceiling'] += 1
            elif case == 'projection_schema':
                doc['schema'] = 'unsupported'
            elif case == 'nonobject_targets':
                doc['targets'] = []
            path.write_bytes(module._json_bytes(doc))
            _assert_rejected_manifest_release(repo, expected)
        finally:
            td.cleanup()

    # Both governed manifests can move together, but a stale one-file
    # package must still fail the derived (not hard-coded) Knowledge count.
    td, repo = stage_repo()
    try:
        _rewrite_governed_manifest(repo, 'Shared_Agent_Source_Manifest.json', lambda doc:
            doc['knowledge_projection_groups'].append({
                'id': 'usb_second', 'target_id': 'openai_usb_reporting', 'purpose': 'test'
            }))
        _rewrite_governed_manifest(repo, proj_name, lambda doc: (
            doc['targets']['openai_usb_reporting'].update(expected_projection_count=2),
            doc['targets']['openai_usb_reporting']['projection_groups'].append({
                'id': 'usb_second', 'order': 1,
                'output_path': 'project_sources/agent_runtime/generated/knowledge/openai_usb_reporting/02-usb-second.md'
            }),
        ))
        _assert_rejected_manifest_release(repo, 'expected 2 Knowledge files, got 1', early=False)
    finally:
        td.cleanup()

TESTS = (
    test_governed_runtime_model_source_and_package_must_agree,
    test_release_source_manifest_invalid_values_fail_before_writing,
    test_release_knowledge_count_and_cross_manifest_integrity,
)

def main() -> int:
    for test in TESTS:
        test()
    print(json.dumps({"success": True, "tests": [test.__name__ for test in TESTS]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
