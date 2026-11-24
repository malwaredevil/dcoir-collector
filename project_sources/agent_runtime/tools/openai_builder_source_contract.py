#!/usr/bin/env python3
"""Canonical governed source intake and capability validation for OpenAI GPTs.

Target-specific manifests, labels and historical provider-error policies remain
with the individual builders. This owner validates shared source provenance.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, NamedTuple

from agent_runtime_path_safety import resolve_repo_path
from openai_webui_contract import CAPABILITY_KEYS
from openai_builder_validation_kernel import (
    select_governed_source_target,
    validate_generated_root_no_symlink,
)


class SourceInputs(NamedTuple):
    manifest: dict[str, Any]
    generated_root: Path
    required_paths: dict[str, Path]
    source_contract: dict[str, Any]
    behavior_manifest: dict[str, Any]
    knowledge_projection_manifest: dict[str, Any]
    target_manifest: dict[str, Any]
    cases: dict[str, Any]
    source_contract_sha: str


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise ValueError(f'Missing JSON file: {path}') from exc
    except (OSError, UnicodeError) as exc:
        raise ValueError(f'Unreadable JSON file: {path}: {exc}') from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f'Invalid JSON in {path}: {exc}') from exc
    if not isinstance(value, dict):
        raise ValueError(f'Expected a JSON object in {path}')
    return value


def load_adapter_source_inputs(
    repo_root: Path,
    manifest_path: Path,
    errors: list[str],
    *,
    adapter_schema: str,
    target_id: str,
    expected_paths: dict[str, str],
    source_schema: str,
    behavior_schema: str,
    invalid_generated_root: str,
) -> SourceInputs | None:
    """Check source path bindings, load canonical manifests, and pin source bytes."""
    try:
        manifest = _load_json(manifest_path)
    except ValueError as exc:
        errors.append(str(exc))
        return None
    if manifest.get('schema') != adapter_schema:
        errors.append(f"Unexpected adapter schema: {manifest.get('schema')}")
    if manifest.get('target_id') != target_id:
        errors.append(f"Unexpected adapter target: {manifest.get('target_id')}")
    for key, expected in expected_paths.items():
        if manifest.get(key) != expected:
            errors.append(f'{key} must remain bound to {expected}')
    source_base_commit = manifest.get('source_base_commit')
    if not isinstance(source_base_commit, str) or re.fullmatch(
        r'[0-9a-f]{40}', source_base_commit
    ) is None:
        errors.append('source_base_commit must be a lowercase 40-character Git SHA')
    root_value = manifest.get('generated_root')
    validate_generated_root_no_symlink(repo_root, root_value, errors)
    generated_root = resolve_repo_path(
        repo_root, root_value, 'generated_root', errors,
        repo_root / expected_paths['generated_root'],
    ) or repo_root / invalid_generated_root
    required_paths: dict[str, Path] = {}
    for key in (
        'source_contract', 'behavior_module_manifest',
        'knowledge_projection_manifest', 'knowledge_target_manifest',
        'canonical_instructions_source', 'behavioral_cases',
    ):
        path = resolve_repo_path(repo_root, manifest.get(key), key, errors)
        if path is not None:
            required_paths[key] = path
    try:
        source_contract = _load_json(required_paths['source_contract'])
        behavior_manifest = _load_json(required_paths['behavior_module_manifest'])
        knowledge_projection_manifest = _load_json(required_paths['knowledge_projection_manifest'])
        target_manifest = _load_json(required_paths['knowledge_target_manifest'])
        cases = _load_json(required_paths['behavioral_cases'])
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
        return None
    if source_contract.get('schema') != source_schema:
        errors.append('Unexpected shared source contract schema')
    if behavior_manifest.get('schema') != behavior_schema:
        errors.append('Unexpected behavior module manifest schema')
    digest = hashlib.sha256(required_paths['source_contract'].read_bytes()).hexdigest()
    return SourceInputs(
        manifest, generated_root, required_paths, source_contract,
        behavior_manifest, knowledge_projection_manifest, target_manifest,
        cases, digest,
    )


def validate_source_target_capabilities(
    source_contract: dict[str, Any],
    adapter_manifest: dict[str, Any],
    errors: list[str],
    *,
    target_id: str,
    label: str,
    runtime_model: str,
    capability_keys: tuple[str, ...] = CAPABILITY_KEYS,
    profile_error_policy: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Check the selected governed GPT source target and disabled capabilities."""
    target = select_governed_source_target(source_contract, target_id, errors, label)
    expected_profile = (
        ('provider', 'openai_webui_bedrock_hosted', 'provider'),
        ('runtime_model', runtime_model, 'runtime model'),
        ('instruction_mode', 'static_instructions', 'instruction mode'),
        ('knowledge_mode', 'static_knowledge', 'knowledge mode'),
    )
    if profile_error_policy not in ('dcoir', 'usb'):
        errors.append('Unknown OpenAI source profile policy')
    elif target or profile_error_policy == 'usb':
        for key, expected, dcoir_label in expected_profile:
            if target.get(key) != expected:
                field = dcoir_label if profile_error_policy == 'dcoir' else key
                errors.append(f'{label} {field} drift')
    capabilities = adapter_manifest.get('capabilities')
    if not isinstance(capabilities, dict):
        errors.append('Adapter capabilities must be an object')
        capabilities = {}
    if set(capabilities) != set(capability_keys):
        errors.append('Adapter capabilities must contain exactly the governed keys')
    target_capabilities = target.get('capabilities') if isinstance(target, dict) else {}
    if not isinstance(target_capabilities, dict) or set(target_capabilities) != set(capability_keys):
        errors.append('Source contract capabilities must contain exactly the governed keys')
        target_capabilities = {}
    for capability in capability_keys:
        if capabilities.get(capability) is not False:
            errors.append(f'Unsupported capability must remain false: {capability}')
        if target_capabilities.get(capability) is not False:
            errors.append(f'Source contract target capability drift: {capability}')
    return target, capabilities


def read_source_bytes(path: Path, label: str, errors: list[str]) -> bytes:
    """Preserve the governed source-file missing/unreadable failure semantics."""
    try:
        return path.read_bytes()
    except FileNotFoundError:
        errors.append(f'Missing {label}: {path}')
        return b''
    except OSError as exc:
        errors.append(f'Unreadable {label}: {path} ({type(exc).__name__})')
        return b''


def sha256_bytes(data: bytes) -> str:
    """Stable SHA-256 for source and generated package byte identities."""
    return hashlib.sha256(data).hexdigest()
