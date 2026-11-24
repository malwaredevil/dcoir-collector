#!/usr/bin/env python3
"""Static release parity regression tests using independent fixture support."""
from __future__ import annotations

import json

from openai_release_parity_test_fixture import (
    module, write_json, write_text, target, stage_repo, build,
)

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
        source_hash = report['source_contracts']['shared_source_contract']['sha256']
        assert all(
            item['package_source_contract_sha256'] == source_hash
            for item in report['targets'] if item['id'].startswith('openai_')
        )
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
        errors, original = build(root)
        assert not errors
        path = root / module.SHARED_MANIFEST
        value = json.loads(path.read_text(encoding='utf-8'))
        value['source_contract_version'] = 'fixture-2'
        write_json(root, module.SHARED_MANIFEST.as_posix(), value)
        errors, drifted = build(root)
        assert drifted['static_parity_status'] == 'fail'
        assert sum('package source_contract_sha256' in error for error in errors) == 2
        new_hash = drifted['source_contracts']['shared_source_contract']['sha256']
        assert original['source_contracts']['shared_source_contract']['sha256'] != new_hash
        for rel in module.OPENAI_PACKAGE_MANIFESTS.values():
            package = json.loads((root / rel).read_text(encoding='utf-8'))
            package['source_contract_sha256'] = new_hash
            nested = package['source_contracts'].get('source_contract')
            if isinstance(nested, dict):
                nested['sha256'] = new_hash
            write_json(root, rel.as_posix(), package)
        errors, refreshed = build(root)
        assert not errors, errors
        assert refreshed['static_parity_status'] == 'pass'
    finally:
        td.cleanup()



def test_both_openai_provenance_mutants_fail_closed() -> None:
    missing = object()
    variants = (
        ('source_contract_sha256', missing, 'source_contract_sha256'),
        ('source_contract_sha256', '0' * 64, 'source_contract_sha256'),
        ('manual_deployment_required', False, 'manual_deployment_required'),
        ('source_contract_sha256', True, 'source_contract_sha256'),
        ('source_contract_sha256', '', 'source_contract_sha256'),
        ('manual_deployment_required', missing, 'manual_deployment_required'),
        ('manual_deployment_required', 'true', 'manual_deployment_required'),
        ('source_contracts', [], 'source_contracts'),
        ('source_contracts', missing, 'source_contracts'),
        ('unexpected_extra', 'field', 'top-level field'),
        ('source_contracts', {'source_contract': {'path': 'wrong-source-file', 'sha256': '0' * 64}}, 'nested package'),
    )
    for target_id, rel in module.OPENAI_PACKAGE_MANIFESTS.items():
        for field, value, expected in variants:
            td, root = stage_repo()
            try:
                package = json.loads((root / rel).read_text())
                if value is missing:
                    package.pop(field)
                else:
                    package[field] = value
                write_json(root, rel.as_posix(), package)
                errors, report = build(root)
                assert any(expected in error for error in errors), (target_id, field, errors)
                assert report['static_parity_status'] == 'fail'
                assert any(expected in gap['message'] for gap in report['blocking_parity_gaps'])
            finally:
                td.cleanup()


def test_joint_forged_hashes_still_fail_against_canonical_source() -> None:
    td, root = stage_repo()
    try:
        for rel in module.OPENAI_PACKAGE_MANIFESTS.values():
            pkg = json.loads((root / rel).read_text())
            pkg['source_contract_sha256'] = '0' * 64
            nested = pkg['source_contracts'].get('source_contract')
            if isinstance(nested, dict):
                nested['sha256'] = '0' * 64
            write_json(root, rel.as_posix(), pkg)
        errors, report = build(root)
        assert sum('package source_contract_sha256' in e for e in errors) == 2, errors
        assert report['static_parity_status'] == 'fail'
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
        assert any('must not be absolute or contain traversal' in error for error in errors), errors
    finally:
        td.cleanup()


def test_non_string_projection_manifest_path_is_reported_without_crash() -> None:
    td, root = stage_repo()
    try:
        path = root / module.KNOWLEDGE_MANIFEST
        value = json.loads(path.read_text(encoding='utf-8'))
        value['targets']['gemini_dcoir_agent']['bundle_manifest'] = 5
        write_json(root, module.KNOWLEDGE_MANIFEST.as_posix(), value)
        errors, report = build(root)
        assert any('must be a non-empty repository-relative path' in error for error in errors), errors
        assert report['static_parity_status'] == 'fail'
    finally:
        td.cleanup()


def test_projection_manifest_symlink_loop_is_reported_without_crash() -> None:
    td, root = stage_repo()
    try:
        loop = root / 'loop.json'
        try:
            loop.symlink_to(loop)
        except (NotImplementedError, OSError):
            return
        path = root / module.KNOWLEDGE_MANIFEST
        value = json.loads(path.read_text(encoding='utf-8'))
        value['targets']['openai_usb_reporting']['target_manifest_path'] = 'loop.json'
        write_json(root, module.KNOWLEDGE_MANIFEST.as_posix(), value)
        try:
            errors, report = build(root)
        except RuntimeError as exc:
            raise AssertionError(f'expected validation error instead of exception: {exc}') from exc
        assert any(
            'path could not be resolved: RuntimeError' in error
            or 'path could not be resolved: OSError' in error
            for error in errors
        ), errors
        assert report['static_parity_status'] == 'fail'
    finally:
        td.cleanup()


def test_projection_manifest_below_looping_directory_is_reported() -> None:
    # On Windows with Python 3.13+, a file below a looping directory stats as
    # missing rather than as a loop, so every link on the path must be followed.
    td, root = stage_repo()
    try:
        loop = root / 'loop-dir'
        try:
            loop.symlink_to(loop, target_is_directory=True)
        except (NotImplementedError, OSError):
            return
        path = root / module.KNOWLEDGE_MANIFEST
        value = json.loads(path.read_text(encoding='utf-8'))
        value['targets']['openai_usb_reporting']['target_manifest_path'] = 'loop-dir/manifest.json'
        write_json(root, module.KNOWLEDGE_MANIFEST.as_posix(), value)
        errors, report = build(root)
        assert any('path could not be resolved: OSError' in error for error in errors), errors
        assert report['static_parity_status'] == 'fail'
    finally:
        td.cleanup()


def test_repo_root_symlink_loop_returns_failure_report_without_crash() -> None:
    td, root = stage_repo()
    try:
        loop = root / 'repo-loop'
        try:
            loop.symlink_to(loop, target_is_directory=True)
        except (NotImplementedError, OSError):
            return
        try:
            errors, report = module.build_release_report(
                loop, source_commit='fixture-commit', run_target_checks=False
            )
        except RuntimeError as exc:
            raise AssertionError(f'expected failure report instead of exception: {exc}') from exc
        assert any(
            'Repository root could not be resolved: RuntimeError:' in error
            or 'Repository root could not be resolved: OSError:' in error
            for error in errors
        ), errors
        assert report['source_commit'] == 'fixture-commit'
        assert report['targets'] == []
        assert report['static_parity_status'] == 'fail'
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
        test_both_openai_provenance_mutants_fail_closed,
        test_joint_forged_hashes_still_fail_against_canonical_source,
        test_knowledge_count_mismatch_is_blocking_gap,
        test_projection_manifest_path_escape_is_rejected,
        test_non_string_projection_manifest_path_is_reported_without_crash,
        test_projection_manifest_symlink_loop_is_reported_without_crash,
        test_projection_manifest_below_looping_directory_is_reported,
        test_repo_root_symlink_loop_returns_failure_report_without_crash,
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
