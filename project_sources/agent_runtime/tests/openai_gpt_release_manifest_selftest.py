#!/usr/bin/env python3
"""Independent source and Knowledge manifest binding checks for the governed OpenAI GPT deployment release."""
from __future__ import annotations

import json
from pathlib import Path

import openai_release_parity_test_fixture as parity

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
    if basename == 'Shared_Agent_Source_Manifest.json':
        source_sha256 = module._sha256_file(path)
        for target_id in ('openai_dcoir_analyst', 'openai_usb_reporting'):
            package_path = (
                repo / 'project_sources/agent_runtime/generated/packages'
                / target_id / 'manifest.json'
            )
            package_manifest = json.loads(package_path.read_text(encoding='utf-8'))
            package_manifest['source_contract_sha256'] = source_sha256
            nested = package_manifest.get('source_contracts', {}).get('source_contract')
            if isinstance(nested, dict):
                nested['sha256'] = source_sha256
            package_path.write_bytes(module._json_bytes(package_manifest))


def _rewrite_package_manifest(repo: Path, target_id: str, mutate) -> None:
    path = repo / 'project_sources/agent_runtime/generated/packages' / target_id / 'manifest.json'
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

    # Both GPTs must reject disabled-capability drift from either source owner.
    for target_id in ('openai_dcoir_analyst', 'openai_usb_reporting'):
        for plane, kind in (
            ('source', 'enabled'), ('source', 'integer'), ('source', 'missing'),
            ('config', 'enabled'), ('config', 'integer'), ('config', 'missing'),
            ('config', 'extra'),
        ):
            td, repo = stage_repo()
            try:
                def corrupt_capabilities(capabilities):
                    if kind == 'enabled':
                        capabilities['image_generation'] = True
                    elif kind == 'integer':
                        capabilities['actions'] = 1
                    elif kind == 'missing':
                        capabilities.pop('canvas')
                    else:
                        capabilities['unauthorized_capability'] = False
                if plane == 'source':
                    _rewrite_governed_manifest(
                        repo, 'Shared_Agent_Source_Manifest.json',
                        lambda doc: corrupt_capabilities(next(
                            target for target in doc['targets'] if target['id'] == target_id
                        )['capabilities']),
                    )
                    expected = (
                        'source capabilities must contain exactly the governed keys'
                        if kind == 'missing'
                        else 'source unsupported capability must be false'
                    )
                else:
                    config_path = (
                        repo / 'project_sources/agent_runtime/generated/packages'
                        / target_id / 'GPT_Configuration.json'
                    )
                    config = json.loads(config_path.read_text(encoding='utf-8'))
                    corrupt_capabilities(config['capabilities'])
                    config_path.write_bytes(module._json_bytes(config))
                    expected = (
                        'WebUI capabilities must contain exactly the governed keys'
                        if kind in ('missing', 'extra')
                        else 'WebUI unsupported capability must be false'
                    )
                _assert_rejected_manifest_release(repo, expected)
            finally:
                td.cleanup()



def test_release_source_manifest_invalid_values_fail_before_writing() -> None:
    source_name = 'Shared_Agent_Source_Manifest.json'
    for case in ('absent', 'bad_json', 'invalid_utf8', 'missing_model',
                 'invalid_model_type', 'invalid_model_control', 'invalid_model_surrogate',
                 'wrong_provider', 'duplicate_target', 'wrong_schema', 'invalid_target_ids',
                 'unknown_target', 'missing_gemini', 'ids_only_unknown', 'ids_only_missing',
                 'targets_only_unknown', 'targets_only_missing', 'unhashable_target_id',
                 'duplicate_gemini'):
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
                    'unknown_target': 'must contain each governed target exactly once',
                    'missing_gemini': 'must contain each governed target exactly once',
                    'ids_only_unknown': 'target_ids must contain each governed target exactly once',
                    'ids_only_missing': 'target_ids must contain each governed target exactly once',
                    'targets_only_unknown': 'source targets must contain each governed target exactly once',
                    'targets_only_missing': 'source targets must contain each governed target exactly once',
                    'unhashable_target_id': 'source targets must contain each governed target exactly once',
                    'duplicate_gemini': 'source targets must contain each governed target exactly once',
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
                elif case in ('unknown_target', 'ids_only_unknown', 'targets_only_unknown'):
                    if case != 'targets_only_unknown':
                        doc['target_ids'].append('rogue_target')
                    if case != 'ids_only_unknown':
                        doc['targets'].append({**target, 'id': 'rogue_target'})
                elif case in ('missing_gemini', 'ids_only_missing', 'targets_only_missing'):
                    if case != 'targets_only_missing':
                        doc['target_ids'].remove('gemini_dcoir_agent')
                    if case != 'ids_only_missing':
                        doc['targets'] = [
                            item for item in doc['targets'] if item['id'] != 'gemini_dcoir_agent'
                        ]
                elif case == 'unhashable_target_id':
                    doc['targets'][0]['id'] = []
                elif case == 'duplicate_gemini':
                    doc['targets'].append(dict(next(
                        item for item in doc['targets'] if item['id'] == 'gemini_dcoir_agent'
                    )))
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
        _assert_rejected_manifest_release(repo, 'Knowledge target projection file count drift')
    finally:
        td.cleanup()

    # Matching poisoned source/projection ceilings must not bypass the fixed
    # per-GPT maximum (and bool must never count as an integer ceiling).
    for poisoned_limit in (21, 2**31, True):
        td, repo = stage_repo()
        try:
            _rewrite_governed_manifest(
                repo, 'Shared_Agent_Source_Manifest.json',
                lambda doc: doc['knowledge_projection_policy'].__setitem__(
                    'strict_file_count_ceiling', poisoned_limit
                ),
            )
            _rewrite_governed_manifest(
                repo, 'Knowledge_Projection_Manifest.json',
                lambda doc: doc.__setitem__('strict_file_count_ceiling', poisoned_limit),
            )
            _assert_rejected_manifest_release(repo, 'file ceilings disagree or are invalid')
        finally:
            td.cleanup()

    # A same-root rogue Knowledge file with a correct hash is still forbidden.
    for target_id in ('openai_dcoir_analyst', 'openai_usb_reporting'):
        for kind in ('rogue_file', 'wrong_id', 'boolean_order', 'wrong_hash',
                     'wrong_bytes', 'missing_file', 'rogue_target_manifest',
                     'unapproved_target_manifest_path'):
            td, repo = stage_repo()
            try:
                package_root = repo / 'project_sources/agent_runtime/generated/packages' / target_id
                config_path = package_root / 'GPT_Configuration.json'
                config = json.loads(config_path.read_text(encoding='utf-8'))
                entry = config['knowledge_files'][0]
                expected = 'WebUI Knowledge entry 0 disagrees with governed projection'
                if kind in ('rogue_file', 'missing_file'):
                    path = repo / 'project_sources/agent_runtime/generated/knowledge' / target_id / 'rogue.md'
                    contents = b'unapproved but hash-consistent bytes\n'
                    if kind == 'rogue_file':
                        path.write_bytes(contents)
                    entry.update(id='unapproved_rogue', path=path.relative_to(repo).as_posix(),
                                 sha256=module._sha256_bytes(contents), bytes=len(contents))
                elif kind == 'wrong_id':
                    entry['id'] = 'wrong_id'
                elif kind == 'boolean_order':
                    entry['order'] = False
                elif kind == 'wrong_hash':
                    entry['sha256'] = '0' * 64
                elif kind == 'wrong_bytes':
                    entry['bytes'] += 1
                elif kind == 'rogue_target_manifest':
                    mpath = repo / 'project_sources/agent_runtime/generated/knowledge' / target_id / 'manifest.json'
                    m = json.loads(mpath.read_text(encoding='utf-8'))
                    m['projections'][0]['id'] = 'unapproved_rogue'
                    mpath.write_bytes(module._json_bytes(m))
                    expected = 'Knowledge target projections disagree with governed projection groups'
                elif kind == 'unapproved_target_manifest_path':
                    ppath = repo / 'project_sources/agent_runtime/Knowledge_Projection_Manifest.json'
                    p = json.loads(ppath.read_text(encoding='utf-8'))
                    p['targets'][target_id]['target_manifest_path'] = 'unapproved/manifest.json'
                    ppath.write_bytes(module._json_bytes(p))
                    expected = 'governed Knowledge target manifest path drift'
                config_path.write_bytes(module._json_bytes(config))
                _assert_rejected_manifest_release(repo, expected)
            finally:
                td.cleanup()



def test_release_package_source_provenance_must_match_current_manifest() -> None:
    for nested in ({}, {'source_contract': None}, {'source_contract': []}):
        td, repo = parity.stage_repo()
        try:
            path = parity.module.OPENAI_PACKAGE_MANIFESTS['openai_dcoir_analyst']
            package = json.loads((repo / path).read_text(encoding='utf-8'))
            package['source_contracts'] = nested
            parity.write_json(repo, path.as_posix(), package)
            errors, report = parity.build(repo)
            assert any('nested package' in error for error in errors), errors
            assert report['static_parity_status'] == 'fail'
        finally:
            td.cleanup()
    for target_id in ('openai_dcoir_analyst', 'openai_usb_reporting'):
        for field, value, expected in (
            ('source_contract_sha256', None, 'missing source_contract_sha256'),
            ('source_contract_sha256', '0' * 64, 'source_contract_sha256 does not match'),
        ):
            td, repo = stage_repo()
            try:
                def mutate(manifest):
                    if value is None:
                        manifest.pop(field, None)
                    else:
                        manifest[field] = value
                _rewrite_package_manifest(repo, target_id, mutate)
                _assert_rejected_manifest_release(repo, expected)
            finally:
                td.cleanup()

    for nested_mutation, expected in (
        ('remove_record', 'missing its nested source contract'),
        ('remove_hash', 'nested package source contract is missing sha256'),
        ('stale_hash', 'nested package source contract sha256 does not match'),
    ):
        td, repo = stage_repo()
        try:
            def mutate(manifest):
                if nested_mutation == 'remove_record':
                    manifest['source_contracts'].pop('source_contract')
                elif nested_mutation == 'remove_hash':
                    manifest['source_contracts']['source_contract'].pop('sha256')
                else:
                    manifest['source_contracts']['source_contract']['sha256'] = '0' * 64
            _rewrite_package_manifest(repo, 'openai_dcoir_analyst', mutate)
            _assert_rejected_manifest_release(repo, expected)
        finally:
            td.cleanup()


TESTS = (
    test_governed_runtime_model_source_and_package_must_agree,
    test_release_source_manifest_invalid_values_fail_before_writing,
    test_release_knowledge_count_and_cross_manifest_integrity,
    test_release_package_source_provenance_must_match_current_manifest,
)

def main() -> int:
    for test in TESTS:
        test()
    print(json.dumps({"success": True, "tests": [test.__name__ for test in TESTS]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
