#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'project_sources/agent_runtime/tools/build_openai_usb_reporting.py'
RELEASE_REPORTER = ROOT / 'project_sources/agent_runtime/tools/report_agent_release_parity.py'
RELEASE_SELFTEST = ROOT / 'project_sources/agent_runtime/tests/report_agent_release_parity_selftest.py'
SPEC = importlib.util.spec_from_file_location('build_openai_usb_reporting', SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise SystemExit('Unable to load build_openai_usb_reporting.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f'Unable to load {path.name}')
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def copy_tree(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def stage_repo() -> tuple[tempfile.TemporaryDirectory, Path]:
    td = tempfile.TemporaryDirectory(prefix='openai-usb-selftest-')
    temp_dir = Path(td.name)
    paths = [
        'project_sources/agent_runtime/Shared_Agent_Source_Manifest.json',
        'project_sources/agent_runtime/Behavior_Module_Manifest.json',
        'project_sources/agent_runtime/behavior_modules/prime/prime.chunk.00.md',
        'project_sources/agent_runtime/behavior_modules/prime/prime.chunk.01.md',
        'project_sources/agent_runtime/behavior_modules/prime/prime.chunk.03.md',
        'project_sources/agent_runtime/behavior_modules/prime/prime.chunk.04.md',
        'project_sources/agent_runtime/behavior_modules/prime/prime.chunk.08.md',
        'project_sources/agent_runtime/behavior_modules/prime/prime.chunk.11.md',
        'project_sources/agent_runtime/behavior_modules/prime/prime.chunk.15.md',
        'project_sources/agent_runtime/behavior_modules/prime/prime.chunk.17.md',
        'project_sources/agent_runtime/behavior_modules/prime/prime.chunk.20.md',
        'project_sources/agent_runtime/behavior_modules/specialists/sub_agent.10.md',
        'project_sources/agent_runtime/behavior_modules/specialists/sub_agent.11.md',
        'project_sources/agent_runtime/Knowledge_Projection_Manifest.json',
        'project_sources/agent_runtime/generated/knowledge/openai_usb_reporting',
        'project_sources/agent_runtime/provider_adapters/openai_usb_reporting',
    ]
    for rel in paths:
        copy_tree(ROOT / rel, temp_dir / rel)
    return td, temp_dir


def expect_failure(repo: Path, reason: str, mutate) -> None:
    mutate(repo)
    errors, _ = module.build_package(
        repo,
        repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json',
        check=True,
    )
    if not errors:
        raise AssertionError(f'expected failure for {reason}')


def test_materialize_and_check() -> None:
    td, repo = stage_repo()
    try:
        errors, report = module.build_package(
            repo,
            repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json',
            check=False,
        )
        assert not errors, report
        assert report['behavior_coverage_count'] == 11
        assert report['knowledge_file_count'] == 2
        errors, report = module.build_package(
            repo,
            repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json',
            check=True,
        )
        assert not errors, report
    finally:
        td.cleanup()


def test_generated_drift_is_rejected() -> None:
    td, repo = stage_repo()
    try:
        module.build_package(
            repo,
            repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json',
            check=False,
        )
        generated = repo / 'project_sources/agent_runtime/generated/packages/openai_usb_reporting/Instructions.md'
        generated.write_text(generated.read_text(encoding='utf-8') + '\nDRIFT\n', encoding='utf-8')
        errors, _ = module.build_package(
            repo,
            repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json',
            check=True,
        )
        assert any('Generated package drift' in error for error in errors), errors
    finally:
        td.cleanup()


def test_unknown_capability_is_rejected() -> None:
    td, repo = stage_repo()
    try:
        manifest_path = repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['capabilities']['web_search'] = True
        manifest['capabilities']['surprise'] = False
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        errors, _ = module.build_package(repo, manifest_path, check=True)
        assert any('Unsupported capability' in error for error in errors), errors
        assert any('exactly the governed keys' in error for error in errors), errors
    finally:
        td.cleanup()


def test_behavior_coverage_order_is_rejected() -> None:
    td, repo = stage_repo()
    try:
        manifest_path = repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['coverage'] = list(reversed(manifest['coverage']))
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        errors, _ = module.build_package(repo, manifest_path, check=True)
        assert any('Behavior coverage must exactly match' in error for error in errors), errors
    finally:
        td.cleanup()


def test_behavior_source_hash_drift_is_rejected() -> None:
    td, repo = stage_repo()
    try:
        source = repo / 'project_sources/agent_runtime/behavior_modules/prime/prime.chunk.00.md'
        source.write_text(source.read_text(encoding='utf-8') + '\nDRIFT\n', encoding='utf-8')
        errors, _ = module.build_package(
            repo,
            repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json',
            check=True,
        )
        assert any('Behavior source hash drift for prime.chunk.00' in error for error in errors), errors
    finally:
        td.cleanup()


def test_knowledge_drift_is_rejected() -> None:
    td, repo = stage_repo()
    try:
        projection = repo / 'project_sources/agent_runtime/generated/knowledge/openai_usb_reporting/01-usb-reporting-core.md'
        projection.write_text(projection.read_text(encoding='utf-8') + '\nDRIFT\n', encoding='utf-8')
        errors, _ = module.build_package(
            repo,
            repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json',
            check=True,
        )
        assert any('Knowledge projection drift' in error for error in errors), errors
    finally:
        td.cleanup()


def test_missing_confirmation_marker_is_rejected() -> None:
    td, repo = stage_repo()
    try:
        instructions = repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Instructions.md'
        text = instructions.read_text(encoding='utf-8')
        instructions.write_text(text.replace('require operator confirmation before final report drafting', ''), encoding='utf-8')
        errors, _ = module.build_package(
            repo,
            repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json',
            check=True,
        )
        assert any('require operator confirmation' in error for error in errors), errors
    finally:
        td.cleanup()


def test_stale_generated_file_is_rejected() -> None:
    td, repo = stage_repo()
    try:
        module.build_package(
            repo,
            repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json',
            check=False,
        )
        stale = repo / 'project_sources/agent_runtime/generated/packages/openai_usb_reporting/stale.txt'
        stale.write_text('stale', encoding='utf-8')
        errors, _ = module.build_package(
            repo,
            repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json',
            check=True,
        )
        assert any('Stale generated package files' in error for error in errors), errors
    finally:
        td.cleanup()


def test_generated_root_symlink_is_rejected() -> None:
    td, repo = stage_repo()
    try:
        generated_root = repo / 'project_sources/agent_runtime/generated/packages/openai_usb_reporting'
        redirect = repo / 'project_sources/agent_runtime/generated/packages/openai_usb_reporting_redirect'
        shutil.rmtree(generated_root, ignore_errors=True)
        redirect.mkdir(parents=True, exist_ok=True)
        generated_root.parent.mkdir(parents=True, exist_ok=True)
        try:
            generated_root.symlink_to(redirect, target_is_directory=True)
        except (NotImplementedError, OSError):
            return
        errors, _ = module.build_package(
            repo,
            repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json',
            check=True,
        )
        assert any('Generated package root must not be a symlink' in error for error in errors), errors
    finally:
        td.cleanup()


def test_generated_root_symlink_loop_is_reported_without_crash() -> None:
    td, repo = stage_repo()
    try:
        generated_root = repo / 'project_sources/agent_runtime/generated/packages/openai_usb_reporting'
        shutil.rmtree(generated_root, ignore_errors=True)
        generated_root.parent.mkdir(parents=True, exist_ok=True)
        try:
            generated_root.symlink_to(generated_root, target_is_directory=True)
        except (NotImplementedError, OSError):
            return
        try:
            errors, _ = module.build_package(
                repo,
                repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json',
                check=True,
            )
        except RuntimeError as exc:
            raise AssertionError(f'expected validation error instead of exception: {exc}') from exc
        assert any(
            'path could not be resolved:' in error
            or 'Generated package root must not be a symlink' in error
            for error in errors
        ), errors
    finally:
        td.cleanup()


def test_absolute_generated_root_symlink_is_reported_without_crash() -> None:
    td, repo = stage_repo()
    outside_td = tempfile.TemporaryDirectory(prefix='openai-usb-outside-')
    try:
        manifest_path = repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json'
        outside = Path(outside_td.name)
        target = outside / 'redirect-target'
        symlink = outside / 'redirect-link'
        target.mkdir(parents=True, exist_ok=True)
        try:
            symlink.symlink_to(target, target_is_directory=True)
        except (NotImplementedError, OSError):
            return
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['generated_root'] = symlink.as_posix()
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        errors, _ = module.build_package(repo, manifest_path, check=True)
        assert any('generated_root must remain bound' in error for error in errors), errors
        assert any('generated_root must not be absolute' in error for error in errors), errors
        assert any('Generated package root must not be a symlink' in error for error in errors), errors
    finally:
        outside_td.cleanup()
        td.cleanup()


def test_instruction_character_ceiling_is_rejected() -> None:
    td, repo = stage_repo()
    try:
        manifest_path = repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        instructions = repo / manifest['canonical_instructions_source']
        text = instructions.read_text(encoding='utf-8')
        excess = manifest['instruction_character_ceiling'] - len(text) + 1
        assert excess > 0
        instructions.write_text(text + ('x' * excess), encoding='utf-8')
        errors, _ = module.build_package(repo, manifest_path, check=True)
        assert any('Instructions exceed character ceiling' in error for error in errors), errors
    finally:
        td.cleanup()


def test_description_character_ceiling_is_rejected() -> None:
    td, repo = stage_repo()
    try:
        manifest_path = repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['editor']['description'] = 'x' * (manifest['description_character_ceiling'] + 1)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        errors, _ = module.build_package(repo, manifest_path, check=True)
        assert any('Description exceeds character ceiling' in error for error in errors), errors
    finally:
        td.cleanup()


def test_non_bmp_instruction_uses_webui_safe_counting() -> None:
    td, repo = stage_repo()
    try:
        manifest_path = repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        ceiling = manifest['instruction_character_ceiling']
        instructions = repo / manifest['canonical_instructions_source']
        text = ('x' * (ceiling - 1)) + '😀'
        assert len(text) == ceiling
        assert module._webui_character_count(text) == ceiling + 1
        instructions.write_text(text, encoding='utf-8')
        errors, _ = module.build_package(repo, manifest_path, check=True)
        assert any('Instructions exceed character ceiling' in error for error in errors), errors
    finally:
        td.cleanup()


def test_lone_surrogate_description_fails_closed() -> None:
    td, repo = stage_repo()
    try:
        manifest_path = repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['editor']['description'] = 'surrogate-' + '\ud800'
        assert module._webui_character_count(manifest['editor']['description']) == 11
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        errors, _ = module.build_package(repo, manifest_path, check=True)
        assert any('lone UTF-16 surrogate' in error for error in errors), errors
    finally:
        td.cleanup()


def test_unified_release_parity_report() -> None:
    selftest = load_module(RELEASE_SELFTEST, 'report_agent_release_parity_selftest')
    assert selftest.main() == 0

    reporter = load_module(RELEASE_REPORTER, 'report_agent_release_parity')
    errors, report = reporter.build_release_report(ROOT, run_target_checks=True)
    assert not errors, errors
    assert report['static_parity_status'] == 'pass'
    assert report['scope']['target_ids'] == list(reporter.EXPECTED_TARGET_IDS)
    assert report['live_parity_status'] in {'pending_manual_readback', 'readback_recorded'}
    json_path, markdown_path = reporter.write_outputs(
        report,
        reporter.default_output_root(ROOT),
    )
    assert json.loads(json_path.read_text(encoding='utf-8')) == report
    assert '# Agent Release and Parity Report' in markdown_path.read_text(encoding='utf-8')


def main() -> int:
    tests = [
        test_materialize_and_check,
        test_generated_drift_is_rejected,
        test_unknown_capability_is_rejected,
        test_behavior_coverage_order_is_rejected,
        test_behavior_source_hash_drift_is_rejected,
        test_knowledge_drift_is_rejected,
        test_missing_confirmation_marker_is_rejected,
        test_stale_generated_file_is_rejected,
        test_generated_root_symlink_is_rejected,
        test_generated_root_symlink_loop_is_reported_without_crash,
        test_absolute_generated_root_symlink_is_reported_without_crash,
        test_instruction_character_ceiling_is_rejected,
        test_description_character_ceiling_is_rejected,
        test_non_bmp_instruction_uses_webui_safe_counting,
        test_lone_surrogate_description_fails_closed,
        test_unified_release_parity_report,
    ]
    for test in tests:
        test()
    print(json.dumps({'success': True, 'tests': [test.__name__ for test in tests]}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
