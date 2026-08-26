#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'project_sources/agent_runtime/tools/build_openai_usb_reporting.py'
SPEC = importlib.util.spec_from_file_location('build_openai_usb_reporting', SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise SystemExit('Unable to load build_openai_usb_reporting.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def copy_tree(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def stage_repo() -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix='openai-usb-selftest-'))
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
    return temp_dir


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
    repo = stage_repo()
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


def test_generated_drift_is_rejected() -> None:
    repo = stage_repo()
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


def test_unknown_capability_is_rejected() -> None:
    repo = stage_repo()
    manifest_path = repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['capabilities']['web_search'] = True
    manifest['capabilities']['surprise'] = False
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    errors, _ = module.build_package(repo, manifest_path, check=True)
    assert any('Unsupported capability' in error for error in errors), errors
    assert any('exactly the governed keys' in error for error in errors), errors


def test_behavior_coverage_order_is_rejected() -> None:
    repo = stage_repo()
    manifest_path = repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['coverage'] = list(reversed(manifest['coverage']))
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    errors, _ = module.build_package(repo, manifest_path, check=True)
    assert any('Behavior coverage must exactly match' in error for error in errors), errors


def test_behavior_source_hash_drift_is_rejected() -> None:
    repo = stage_repo()
    source = repo / 'project_sources/agent_runtime/behavior_modules/prime/prime.chunk.00.md'
    source.write_text(source.read_text(encoding='utf-8') + '\nDRIFT\n', encoding='utf-8')
    errors, _ = module.build_package(
        repo,
        repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json',
        check=True,
    )
    assert any('Behavior source hash drift for prime.chunk.00' in error for error in errors), errors


def test_knowledge_drift_is_rejected() -> None:
    repo = stage_repo()
    projection = repo / 'project_sources/agent_runtime/generated/knowledge/openai_usb_reporting/01-usb-reporting-core.md'
    projection.write_text(projection.read_text(encoding='utf-8') + '\nDRIFT\n', encoding='utf-8')
    errors, _ = module.build_package(
        repo,
        repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json',
        check=True,
    )
    assert any('Knowledge projection drift' in error for error in errors), errors


def test_missing_confirmation_marker_is_rejected() -> None:
    repo = stage_repo()
    instructions = repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Instructions.md'
    text = instructions.read_text(encoding='utf-8')
    instructions.write_text(text.replace('require operator confirmation before final report drafting', ''), encoding='utf-8')
    errors, _ = module.build_package(
        repo,
        repo / 'project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Adapter_Manifest.json',
        check=True,
    )
    assert any('require operator confirmation' in error for error in errors), errors


def test_stale_generated_file_is_rejected() -> None:
    repo = stage_repo()
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
    ]
    for test in tests:
        test()
    print(json.dumps({'success': True, 'tests': [test.__name__ for test in tests]}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
