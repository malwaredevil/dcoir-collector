#!/usr/bin/env python3
"""Canonical deterministic OpenAI GPT editor, configuration and package assembly.

Target builders declare their package schema, output roots and source hash
selection. This module owns identical output validation and byte construction.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_runtime_path_safety import resolve_repo_path
from openai_builder_source_contract import read_source_bytes, sha256_bytes
from openai_builder_validation_kernel import validate_source_output_binding
from openai_package_output_kernel import reconcile_generated_package
from openai_webui_contract import (
    DESCRIPTION_CHARACTER_CEILING,
    INSTRUCTION_CHARACTER_CEILING,
    contains_lone_surrogate,
    valid_conversation_starters_shape,
    webui_character_count,
)


@dataclass(frozen=True)
class PackageSettings:
    target_id: str
    package_schema: str
    editor_name: str
    expected_outputs: dict[str, str]
    output_label: str
    staging_prefix: str
    source_hash_keys: tuple[str, ...] | None = None
    description_ceiling: int = DESCRIPTION_CHARACTER_CEILING
    instruction_ceiling: int = INSTRUCTION_CHARACTER_CEILING


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')


def assemble_package_files(
    repo_root: Path,
    generated_root: Path,
    adapter: dict[str, Any],
    target: dict[str, Any],
    required_paths: dict[str, Path],
    instructions: bytes,
    knowledge_files: list[dict[str, Any]],
    knowledge_target: dict[str, Any],
    behavior_snapshot: list[dict[str, Any]],
    snapshot_sha: str,
    case_ids: list[str],
    capabilities: dict[str, Any],
    source_contract_sha: str,
    errors: list[str],
    *,
    settings: PackageSettings,
    check: bool,
) -> dict[Path, bytes]:
    """Produce three governed GPT files and reconcile them through safe IO."""
    editor = adapter.get('editor')
    if not isinstance(editor, dict):
        errors.append('Adapter editor configuration must be an object')
        editor = {}
    if editor.get('name') != settings.editor_name:
        errors.append(f'Editor name must remain {settings.editor_name}')
    description = editor.get('description')
    if not isinstance(description, str) or not description.strip():
        errors.append('Editor description must be a non-empty string')
        description = ''
    if contains_lone_surrogate(description):
        errors.append('Editor description must not contain lone UTF-16 surrogate code points')
    description_ceiling = adapter.get('description_character_ceiling')
    description_character_count = webui_character_count(description)
    if type(description_ceiling) is not int or description_ceiling != settings.description_ceiling:
        errors.append(
            'description_character_ceiling must remain '
            f'{settings.description_ceiling}'
        )
    if description_character_count > settings.description_ceiling:
        errors.append(
            'Description exceeds character ceiling: '
            f'{description_character_count} > {settings.description_ceiling}'
        )
    starters = editor.get('conversation_starters')
    if not valid_conversation_starters_shape(starters):
        errors.append('Exactly four non-empty conversation starters are required')
    elif any(contains_lone_surrogate(value) for value in starters):
        errors.append('Conversation starters must not contain lone UTF-16 surrogate code points')
    elif len(set(starters)) != len(starters):
        errors.append('Conversation starters must be unique')
    output_map = adapter.get('generated_outputs')
    if not isinstance(output_map, dict):
        errors.append('generated_outputs must be an object')
        output_map = {}
    configuration = {
        'schema': 'dcoir.agent_runtime.openai_webui_configuration.v1',
        'target_id': settings.target_id,
        'name': editor.get('name'),
        'description': description,
        'conversation_starters': starters,
        'runtime_model': target.get('runtime_model') if isinstance(target, dict) else None,
        'instructions_file': output_map.get('instructions'),
        'capabilities': capabilities,
        'knowledge_files': knowledge_files,
    }
    source_hashes: dict[str, dict[str, Any]] = {}
    keys = tuple(required_paths) if settings.source_hash_keys is None else settings.source_hash_keys
    for key in keys:
        path = required_paths.get(key)
        if path is None:
            errors.append(f'Missing {key} contract source path')
            continue
        content = read_source_bytes(path, f'{key} contract source', errors)
        source_hashes[key] = {
            'path': path.relative_to(repo_root).as_posix(),
            'sha256': sha256_bytes(content),
        }
    for key, expected in settings.expected_outputs.items():
        if output_map.get(key) != expected:
            errors.append(f'generated {key} must remain bound to {expected}')
    validate_source_output_binding(
        target, settings.target_id, settings.expected_outputs, errors,
        settings.output_label,
    )
    output_paths: dict[str, Path] = {}
    for key in ('instructions', 'configuration', 'package_manifest'):
        path = resolve_repo_path(
            repo_root, output_map.get(key), f'generated {key}', errors,
            generated_root,
        )
        if path is not None:
            output_paths[key] = path
    expected_files: dict[Path, bytes] = {}
    if 'instructions' in output_paths:
        expected_files[output_paths['instructions']] = instructions
    configuration_bytes = _json_bytes(configuration)
    if 'configuration' in output_paths:
        expected_files[output_paths['configuration']] = configuration_bytes
    package_manifest = {
        'schema': settings.package_schema,
        'adapter_contract_version': adapter.get('adapter_contract_version'),
        'target_id': settings.target_id,
        'source_base_commit': adapter.get('source_base_commit'),
        'source_contracts': source_hashes,
        'source_contract_sha256': source_contract_sha,
        'behavior_source_snapshot_sha256': snapshot_sha,
        'behavior_coverage_count': len(behavior_snapshot),
        'behavior_coverage': behavior_snapshot,
        'behavioral_case_count': len(case_ids),
        'behavioral_case_ids': case_ids,
        'instruction_character_count': webui_character_count(
            instructions.decode('utf-8', errors='ignore')
        ),
        'instruction_character_ceiling': settings.instruction_ceiling,
        'description_character_count': description_character_count,
        'description_character_ceiling': settings.description_ceiling,
        'knowledge_file_count': len(knowledge_files),
        'strict_knowledge_file_ceiling': knowledge_target.get('strict_file_count_ceiling'),
        'knowledge_files': knowledge_files,
        'generated_files': [
            {
                'path': output_map.get('instructions'),
                'sha256': sha256_bytes(instructions),
                'bytes': len(instructions),
            },
            {
                'path': output_map.get('configuration'),
                'sha256': sha256_bytes(configuration_bytes),
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
        check=check, staging_prefix=settings.staging_prefix,
    )
    return expected_files
