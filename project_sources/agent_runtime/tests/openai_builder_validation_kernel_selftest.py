#!/usr/bin/env python3
"""Independent adversarial regression for the shared OpenAI builder safety gates."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / 'project_sources/agent_runtime/tools'
sys.path.insert(0, str(TOOLS))

import build_openai_dcoir_analyst as dcoir
import build_openai_usb_reporting as usb
import openai_builder_validation_kernel as kernel

ADAPTERS = (('dcoir', 'openai_dcoir_analyst', dcoir), ('usb', 'openai_usb_reporting', usb))
COMMON = (
    'project_sources/agent_runtime/Shared_Agent_Source_Manifest.json',
    'project_sources/agent_runtime/Behavior_Module_Manifest.json',
    'project_sources/agent_runtime/Knowledge_Projection_Manifest.json',
    'project_sources/agent_runtime/behavior_modules',
)


def copy_path(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)


def staged_builder(target_id: str) -> tuple[tempfile.TemporaryDirectory, Path, Path]:
    tmp = tempfile.TemporaryDirectory(prefix='openai-builder-kernel-')
    repo = Path(tmp.name)
    for rel in (*COMMON,
                f'project_sources/agent_runtime/provider_adapters/{target_id}',
                f'project_sources/agent_runtime/generated/knowledge/{target_id}'):
        copy_path(ROOT / rel, repo / rel)
    manifest = repo / f'project_sources/agent_runtime/provider_adapters/{target_id}/Adapter_Manifest.json'
    return tmp, repo, manifest


def test_knowledge_ceiling_both_targets() -> None:
    for _, target_id, builder in ADAPTERS:
        assert builder.validate_knowledge_file_ceiling is kernel.validate_knowledge_file_ceiling
        manifest = json.loads((
            ROOT / f'project_sources/agent_runtime/generated/knowledge/{target_id}/manifest.json'
        ).read_text(encoding='utf-8'))
        count = len(manifest['projections'])
        for ceiling in (count, 20):
            errors: list[str] = []
            entries = builder._knowledge_files(
                ROOT, {**manifest, 'strict_file_count_ceiling': ceiling}, errors
            )
            assert not errors and len(entries) == count, (target_id, ceiling, errors)
        for ceiling in (None, False, True, -1, 0, 21, count - 1):
            errors = []
            builder._knowledge_files(
                ROOT, {**manifest, 'strict_file_count_ceiling': ceiling}, errors
            )
            assert 'Knowledge projection count or ceiling is invalid' in errors, (
                target_id, repr(ceiling), errors
            )


def test_generated_root_symlinks_both_targets() -> None:
    for _, target_id, builder in ADAPTERS:
        assert builder.validate_generated_root_no_symlink is kernel.validate_generated_root_no_symlink
        for loop in (False, True):
            tmp, repo, manifest = staged_builder(target_id)
            try:
                root = repo / f'project_sources/agent_runtime/generated/packages/{target_id}'
                root.parent.mkdir(parents=True, exist_ok=True)
                external = repo / 'redirect'
                external.mkdir()
                marker = external / 'preserve.txt'
                marker.write_text('sentinel', encoding='utf-8')
                try:
                    root.symlink_to(root if loop else external, target_is_directory=True)
                except (NotImplementedError, OSError):
                    continue
                for check in (True, False):
                    errors, report = builder.build_package(repo, manifest, check=check)
                    assert errors and not report.get('success'), (target_id, loop, check, report)
                    assert any(
                        'Generated package root must not be a symlink' in e
                        or 'path could not be resolved' in e
                        for e in errors
                    ), (target_id, loop, check, errors)
                    assert root.is_symlink() and marker.read_text() == 'sentinel'
                    assert sorted(path.name for path in external.iterdir()) == ['preserve.txt']
            finally:
                tmp.cleanup()


def test_helper_negative_and_opposite_polarity_controls() -> None:
    errors: list[str] = []
    kernel.validate_generated_root_no_symlink(ROOT, None, errors)
    kernel.validate_generated_root_no_symlink(ROOT, '', errors)
    assert not errors
    kernel.validate_generated_root_no_symlink(ROOT, '\x00', errors)
    assert errors and 'could not be checked' in errors[-1]
    for ceiling in (1, 20):
        errors = []
        kernel.validate_knowledge_file_ceiling({'strict_file_count_ceiling': ceiling}, ceiling, errors)
        assert not errors
    for ceiling in ('20', [], {}, 21, 0):
        errors = []
        kernel.validate_knowledge_file_ceiling({'strict_file_count_ceiling': ceiling}, 1, errors)
        assert errors == ['Knowledge projection count or ceiling is invalid']


def main() -> int:
    test_knowledge_ceiling_both_targets()
    test_generated_root_symlinks_both_targets()
    test_helper_negative_and_opposite_polarity_controls()
    print('PASS: both OpenAI builders reject malformed Knowledge ceilings and symlinked roots')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
