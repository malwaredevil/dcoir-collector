#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from agent_runtime_path_safety import resolve_repo_path
from openai_builder_knowledge_projection import validate_knowledge_projections
from openai_builder_behavior_snapshot import validate_behavior_snapshot
from openai_builder_instruction_contract import validate_instruction_cases
from openai_builder_source_contract import (
    load_adapter_source_inputs, validate_source_target_capabilities,
    read_source_bytes as _read_bytes, sha256_bytes as _sha256,
)
from openai_package_output_kernel import reconcile_generated_package
from openai_builder_validation_kernel import (
    validate_behavior_snapshot_pin,
    validate_source_output_binding,
    validate_projection_manifest_binding,
)
from openai_webui_contract import (
    DESCRIPTION_CHARACTER_CEILING as EXPECTED_DESCRIPTION_CHARACTER_CEILING,
    INSTRUCTION_CHARACTER_CEILING as EXPECTED_INSTRUCTION_CHARACTER_CEILING,
    contains_lone_surrogate as _contains_lone_surrogate,
    valid_conversation_starters_shape as _valid_conversation_starters_shape,
    webui_character_count as _webui_character_count,
    webui_paste_safe_character_count as _webui_paste_safe_character_count,
)


SCHEMA = 'dcoir.agent_runtime.openai_dcoir_adapter.v1'
SOURCE_SCHEMA = 'dcoir.agent_runtime.source_contract.v1'
BEHAVIOR_SCHEMA = 'dcoir.agent_runtime.behavior_modules.v1'
KNOWLEDGE_SCHEMA = 'dcoir.agent_runtime.knowledge_projection.target.v1'
TARGET_ID = 'openai_dcoir_analyst'
EXPECTED_EDITOR_NAME = 'AFRICOM DCOIR Analyst'
EXPECTED_RUNTIME_MODEL = 'GPT-5.6 Terra'
EXPECTED_KNOWLEDGE_FILES = 7
EXPECTED_BEHAVIOR_ITEMS = 30
EXPECTED_CASES = 22
EXPECTED_CASE_SCHEMA = 'dcoir.agent_runtime.openai_dcoir_behavioral_cases.v1'
CASE_MARKER_POLICY = 'aggregate'
EXPECTED_PATHS = {
    'source_contract': 'project_sources/agent_runtime/Shared_Agent_Source_Manifest.json',
    'behavior_module_manifest': 'project_sources/agent_runtime/Behavior_Module_Manifest.json',
    'knowledge_projection_manifest': 'project_sources/agent_runtime/Knowledge_Projection_Manifest.json',
    'knowledge_target_manifest': (
        'project_sources/agent_runtime/generated/knowledge/'
        'openai_dcoir_analyst/manifest.json'
    ),
    'canonical_instructions_source': (
        'project_sources/agent_runtime/provider_adapters/'
        'openai_dcoir_analyst/Instructions.md'
    ),
    'behavioral_cases': (
        'project_sources/agent_runtime/provider_adapters/'
        'openai_dcoir_analyst/Behavioral_Contract_Cases.json'
    ),
    'generated_root': (
        'project_sources/agent_runtime/generated/packages/openai_dcoir_analyst'
    ),
}
EXPECTED_OUTPUTS = {
    'instructions': f"{EXPECTED_PATHS['generated_root']}/Instructions.md",
    'configuration': f"{EXPECTED_PATHS['generated_root']}/GPT_Configuration.json",
    'package_manifest': f"{EXPECTED_PATHS['generated_root']}/manifest.json",
}
SECTION_HEADINGS = {
    'identity_scope': '## Identity and scope',
    'authority_evidence_lanes': '## Authority and evidence lanes',
    'analysis_workflow': '## Analysis workflow',
    'queries_commands_collection': '## Queries, commands, and collection',
    'ioc_encoded_content': '## IOC and encoded content',
    'conclusions_output': '## Conclusions and output',
    'capability_boundaries': '## Capability boundaries',
}
PROVIDER_TOPOLOGY_LEAKS = (
    'you are the prime agent',
    'gemini enterprise prime agent',
    'route intake to session readiness',
    'route to query planner',
    'handoff to sub-agent',
    'sub-agent execution',
)
REQUIRED_STATIC_MARKERS = (
    'user-provided evidence',
    'uploaded file or artifact evidence',
    'copied query result',
    'DCOIR Collector output',
    'returned public-source material',
    'tool-returned result',
    'unavailable or unverified source state',
    'planned action:',
    'requested action:',
    'executed action:',
    'returned result:',
    'Only a returned result authorizes completion wording',
    'IOC enrichment is optional and additive',
    'Silently omit unavailable or failed enrichment',
    'separate AFRICOM USB Reporting GPT',
)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')


def build_package(
    repo_root: Path, manifest_path: Path, check: bool
) -> tuple[list[str], dict[str, Any]]:
    repo_root = repo_root.resolve()
    errors: list[str] = []
    inputs = load_adapter_source_inputs(
        repo_root, manifest_path, errors,
        adapter_schema=SCHEMA, target_id=TARGET_ID,
        expected_paths=EXPECTED_PATHS, source_schema=SOURCE_SCHEMA,
        behavior_schema=BEHAVIOR_SCHEMA,
        invalid_generated_root='.invalid-openai-dcoir-generated-root',
    )
    if inputs is None:
        return errors, {'success': False, 'errors': errors}
    (manifest, generated_root, required_paths, source_contract,
     behavior_manifest, knowledge_projection_manifest, target_manifest,
     cases, source_contract_sha) = inputs
    if source_contract.get('openai_dcoir_adapter_manifest') != (
        'project_sources/agent_runtime/provider_adapters/'
        'openai_dcoir_analyst/Adapter_Manifest.json'
    ):
        errors.append('Shared source contract points to the wrong OpenAI DCOIR adapter')
    validate_projection_manifest_binding(
        knowledge_projection_manifest, manifest, TARGET_ID,
        EXPECTED_KNOWLEDGE_FILES, errors, 'OpenAI DCOIR'
    )
    if target_manifest.get('source_contract') != manifest.get('source_contract'):
        errors.append('Knowledge target points to the wrong shared source contract')
    if target_manifest.get('source_contract_sha256') != source_contract_sha:
        errors.append('Knowledge target source-contract hash drift')
    target, capabilities = validate_source_target_capabilities(
        source_contract, manifest, errors,
        target_id=TARGET_ID, label='OpenAI DCOIR',
        runtime_model=EXPECTED_RUNTIME_MODEL,
        profile_error_policy='dcoir',
    )
    coverage = manifest.get('coverage')
    if not isinstance(coverage, list):
        errors.append('Adapter coverage must be an array')
        coverage = []
    behavior_snapshot, snapshot_sha = validate_behavior_snapshot(
        repo_root, source_contract, behavior_manifest, coverage, errors,
        target_id=TARGET_ID, expected_count=EXPECTED_BEHAVIOR_ITEMS,
        instructions_path=EXPECTED_OUTPUTS['instructions'],
        section_headings=SECTION_HEADINGS,
    )
    validate_behavior_snapshot_pin(snapshot_sha, manifest, errors)
    instruction_path = required_paths.get('canonical_instructions_source')
    instructions = _read_bytes(instruction_path, 'canonical Instructions', errors) if instruction_path else b''
    case_ids = validate_instruction_cases(
        instructions, manifest, cases, errors,
        target_id=TARGET_ID, case_schema=EXPECTED_CASE_SCHEMA,
        expected_ceiling=EXPECTED_INSTRUCTION_CHARACTER_CEILING,
        section_headings=SECTION_HEADINGS,
        required_static_markers=REQUIRED_STATIC_MARKERS,
        provider_topology_leaks=PROVIDER_TOPOLOGY_LEAKS,
        expected_cases=EXPECTED_CASES,
        marker_error_policy=CASE_MARKER_POLICY,
    )
    knowledge_files = validate_knowledge_projections(
        repo_root, target_manifest, errors,
        target_id=TARGET_ID, schema=KNOWLEDGE_SCHEMA,
        expected_count=EXPECTED_KNOWLEDGE_FILES, label='DCOIR',
    )
    editor = manifest.get('editor')
    if not isinstance(editor, dict):
        errors.append('Adapter editor configuration must be an object')
        editor = {}
    if editor.get('name') != EXPECTED_EDITOR_NAME:
        errors.append(f'Editor name must remain {EXPECTED_EDITOR_NAME}')
    description = editor.get('description')
    if not isinstance(description, str) or not description.strip():
        errors.append('Editor description must be a non-empty string')
        description = ''
    if _contains_lone_surrogate(description):
        errors.append('Editor description must not contain lone UTF-16 surrogate code points')
    description_ceiling = manifest.get('description_character_ceiling')
    description_character_count = _webui_character_count(description)
    if type(description_ceiling) is not int or description_ceiling != EXPECTED_DESCRIPTION_CHARACTER_CEILING:
        errors.append(
            'description_character_ceiling must remain '
            f'{EXPECTED_DESCRIPTION_CHARACTER_CEILING}'
        )
    if description_character_count > EXPECTED_DESCRIPTION_CHARACTER_CEILING:
        errors.append(
            'Description exceeds character ceiling: '
            f'{description_character_count} > {EXPECTED_DESCRIPTION_CHARACTER_CEILING}'
        )
    starters = editor.get('conversation_starters')
    if not _valid_conversation_starters_shape(starters):
        errors.append('Exactly four non-empty conversation starters are required')
    elif any(_contains_lone_surrogate(value) for value in starters):
        errors.append('Conversation starters must not contain lone UTF-16 surrogate code points')
    elif len(set(starters)) != len(starters):
        errors.append('Conversation starters must be unique')
    configuration = {
        'schema': 'dcoir.agent_runtime.openai_webui_configuration.v1',
        'target_id': TARGET_ID,
        'name': editor.get('name'),
        'description': description,
        'conversation_starters': starters,
        'runtime_model': target.get('runtime_model') if isinstance(target, dict) else None,
        'instructions_file': manifest.get('generated_outputs', {}).get('instructions'),
        'capabilities': capabilities,
        'knowledge_files': knowledge_files,
    }
    source_hashes: dict[str, dict[str, Any]] = {}
    for key, path in required_paths.items():
        content = _read_bytes(path, f'{key} contract source', errors)
        source_hashes[key] = {
            'path': path.relative_to(repo_root).as_posix(),
            'sha256': _sha256(content),
        }
    expected_files: dict[Path, bytes] = {}
    output_map = manifest.get('generated_outputs')
    if not isinstance(output_map, dict):
        errors.append('generated_outputs must be an object')
        output_map = {}
    for key, expected in EXPECTED_OUTPUTS.items():
        if output_map.get(key) != expected:
            errors.append(f'generated {key} must remain bound to {expected}')
    validate_source_output_binding(target, TARGET_ID, EXPECTED_OUTPUTS, errors, 'OpenAI DCOIR')
    output_paths: dict[str, Path] = {}
    for key in ('instructions', 'configuration', 'package_manifest'):
        path = resolve_repo_path(
            repo_root, output_map.get(key), f'generated {key}', errors, generated_root
        )
        if path is not None:
            output_paths[key] = path
    if 'instructions' in output_paths:
        expected_files[output_paths['instructions']] = instructions
    configuration_bytes = _json_bytes(configuration)
    if 'configuration' in output_paths:
        expected_files[output_paths['configuration']] = configuration_bytes
    package_manifest = {
        'schema': 'dcoir.agent_runtime.openai_dcoir_package.v1',
        'adapter_contract_version': manifest.get('adapter_contract_version'),
        'target_id': TARGET_ID,
        'source_base_commit': manifest.get('source_base_commit'),
        'source_contracts': source_hashes,
        'source_contract_sha256': source_contract_sha,
        'behavior_source_snapshot_sha256': snapshot_sha,
        'behavior_coverage_count': len(behavior_snapshot),
        'behavior_coverage': behavior_snapshot,
        'behavioral_case_count': len(case_ids),
        'behavioral_case_ids': case_ids,
        'instruction_character_count': _webui_character_count(
            instructions.decode('utf-8', errors='ignore')
        ),
        'instruction_character_ceiling': EXPECTED_INSTRUCTION_CHARACTER_CEILING,
        'description_character_count': description_character_count,
        'description_character_ceiling': EXPECTED_DESCRIPTION_CHARACTER_CEILING,
        'knowledge_file_count': len(knowledge_files),
        'strict_knowledge_file_ceiling': target_manifest.get('strict_file_count_ceiling'),
        'knowledge_files': knowledge_files,
        'generated_files': [
            {
                'path': output_map.get('instructions'),
                'sha256': _sha256(instructions),
                'bytes': len(instructions),
            },
            {
                'path': output_map.get('configuration'),
                'sha256': _sha256(configuration_bytes),
                'bytes': len(configuration_bytes),
            },
        ],
        'generated_outputs_are_canonical': False,
        'direct_target_edits_require_reverse_reconciliation': True,
        'live_webui_validation_performed': False,
        'manual_deployment_required': True,
    }
    if 'package_manifest' in output_paths:
        expected_files[output_paths['package_manifest']] = _json_bytes(package_manifest)
    reconcile_generated_package(
        repo_root, generated_root, expected_files, errors,
        check=check, staging_prefix='.openai-dcoir-',
    )
    report = {
        'success': not errors,
        'action': 'check' if check else 'materialize',
        'target_id': TARGET_ID,
        'behavior_coverage_count': len(behavior_snapshot),
        'behavior_source_snapshot_sha256': snapshot_sha,
        'behavioral_case_count': len(case_ids),
        'knowledge_file_count': len(knowledge_files),
        'generated_file_count': len(expected_files),
        'errors': errors,
    }
    return errors, report


def main() -> int:
    default_repo = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo-root', default=str(default_repo))
    parser.add_argument(
        '--manifest',
        default=(
            'project_sources/agent_runtime/provider_adapters/'
            'openai_dcoir_analyst/Adapter_Manifest.json'
        ),
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--check', action='store_true')
    action.add_argument('--materialize', action='store_true')
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = repo_root / manifest_path
    errors, report = build_package(
        repo_root, manifest_path.resolve(), check=not args.materialize
    )
    print(json.dumps(report, indent=2), file=sys.stderr if errors else sys.stdout)
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
