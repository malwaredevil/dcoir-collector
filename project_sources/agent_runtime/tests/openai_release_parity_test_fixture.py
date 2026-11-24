#!/usr/bin/env python3
"""Shared isolated manifest fixture, not another test entrypoint."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / 'project_sources/agent_runtime/tools/report_agent_release_parity.py'
sys.path.insert(0, str(SCRIPT.parent))
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
    dcoir_groups = ['dcoir_core', 'dcoir_ops']
    usb_groups = ['usb_reporting_core']
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
        'knowledge_projection_policy': {
            'strict_file_count_ceiling': 20,
            'count_unit': 'unique_projection_groups_per_target',
            'lossless_source_boundaries_required': True,
            'per_source_sha256_required': True,
        },
        'knowledge_projection_groups': [
            *(
                {'id': group_id, 'target_id': 'openai_dcoir_analyst'}
                for group_id in dcoir_groups
            ),
            *(
                {'id': group_id, 'target_id': 'openai_usb_reporting'}
                for group_id in usb_groups
            ),
        ],
        'behavior_items': [
            {'id': 'shared.1', 'canonical': True, 'applies_to': list(module.EXPECTED_TARGET_IDS)},
            {'id': 'shared.2', 'canonical': True, 'applies_to': ['gemini_dcoir_agent', 'openai_dcoir_analyst']},
            {'id': 'gemini.nonmodule.1', 'canonical': True, 'applies_to': ['gemini_dcoir_agent']},
            {'id': 'generated.1', 'canonical': False, 'applies_to': ['gemini_dcoir_agent']},
        ],
    }


def openai_package(target_id: str, behavior_count: int, knowledge_count: int, source_sha: str) -> dict:
    return {
        'schema': f'dcoir.agent_runtime.{target_id}.v1',
        'target_id': target_id,
        'adapter_contract_version': 'fixture-1',
        'source_base_commit': 'base-fixture',
        'source_contract_sha256': source_sha,
        'source_contracts': (
            {'source_contract': {'path': module.SHARED_MANIFEST.as_posix(), 'sha256': source_sha}}
            if target_id == 'openai_dcoir_analyst' else {}
        ),
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


def projection_groups(target_id: str, group_ids: list[str]) -> list[dict]:
    return [
        {
            'id': group_id,
            'order': index,
            'output_path': f'knowledge/{target_id}/{index}.md',
        }
        for index, group_id in enumerate(group_ids)
    ]


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
            'strict_file_count_ceiling': 20,
            'targets': {
                'gemini_dcoir_agent': {
                    'expected_attachment_count': 2,
                    'bundle_manifest': module.GEMINI_MANIFEST.as_posix(),
                },
                'openai_dcoir_analyst': {
                    'expected_projection_count': 2,
                    'target_manifest_path': module.OPENAI_PACKAGE_MANIFESTS['openai_dcoir_analyst'].as_posix(),
                    'projection_groups': projection_groups(
                        'openai_dcoir_analyst', ['dcoir_core', 'dcoir_ops'],
                    ),
                },
                'openai_usb_reporting': {
                    'expected_projection_count': 1,
                    'target_manifest_path': module.OPENAI_PACKAGE_MANIFESTS['openai_usb_reporting'].as_posix(),
                    'projection_groups': projection_groups(
                        'openai_usb_reporting', ['usb_reporting_core'],
                    ),
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
    shared_source_sha = hashlib.sha256((root / module.SHARED_MANIFEST).read_bytes()).hexdigest()
    write_json(
        root,
        module.OPENAI_PACKAGE_MANIFESTS['openai_dcoir_analyst'].as_posix(),
        openai_package('openai_dcoir_analyst', 2, 2, shared_source_sha),
    )
    write_json(
        root,
        module.OPENAI_PACKAGE_MANIFESTS['openai_usb_reporting'].as_posix(),
        openai_package('openai_usb_reporting', 1, 1, shared_source_sha),
    )
    guide = '\n\n'.join(module.GUIDE_MARKERS) + '\n'
    write_text(root, module.MANUAL_GUIDE.as_posix(), guide)
    return td, root


def build(root: Path):
    return module.build_release_report(root, source_commit='fixture-commit', run_target_checks=False)
