#!/usr/bin/env python3
"""Gemini bundle manifest path preflight and bundle identity checks.

Path containment itself is owned by
``project_sources/agent_runtime/tools/agent_runtime_path_safety.py``; this module
only knows which Gemini manifest fields hold paths, which root each one uses, and
what makes a bundle name or version safe to use as an archive name.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

_SHARED_MODULE_NAME = 'agent_runtime_path_safety'
_SHARED_MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / 'agent_runtime'
    / 'tools'
    / f'{_SHARED_MODULE_NAME}.py'
)


def _load_shared_path_safety() -> ModuleType:
    """Load the canonical path-safety owner by explicit file path.

    The module is registered under its normal name so agent-runtime code in the
    same process shares one UnsafePathError class, but sys.path is left untouched.
    """
    loaded = sys.modules.get(_SHARED_MODULE_NAME)
    if loaded is not None:
        loaded_file = getattr(loaded, '__file__', None)
        if loaded_file and Path(loaded_file).resolve() == _SHARED_MODULE_PATH:
            return loaded
        raise ImportError(
            f'{_SHARED_MODULE_NAME} is already loaded from {loaded_file!r}, '
            f'not {_SHARED_MODULE_PATH}'
        )
    if not _SHARED_MODULE_PATH.is_file():
        raise ImportError(f'shared path-safety module not found: {_SHARED_MODULE_PATH}')
    spec = importlib.util.spec_from_file_location(_SHARED_MODULE_NAME, _SHARED_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f'cannot load shared path-safety module: {_SHARED_MODULE_PATH}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[_SHARED_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[_SHARED_MODULE_NAME]
        raise
    return module


_shared = _load_shared_path_safety()
UnsafePathError = _shared.UnsafePathError
resolve_contained_path = _shared.resolve_contained_path
validate_relative_path_syntax = _shared.validate_relative_path_syntax

__all__ = (
    'UnsafePathError',
    'resolve_contained_path',
    'validate_bundle_identity',
    'validate_bundle_identity_component',
    'validate_manifest_paths',
)

# Characters Windows rejects in file names, and device names it reserves with or
# without an extension. The bundle name and version name a zip and its top-level
# folder, which operators extract on Windows.
_WINDOWS_FORBIDDEN_CHARS = frozenset('<>:"|?*')
_WINDOWS_RESERVED_NAMES = frozenset(
    {'CON', 'PRN', 'AUX', 'NUL'}
    | {f'COM{index}' for index in range(1, 10)}
    | {f'LPT{index}' for index in range(1, 10)}
)


def validate_bundle_identity_component(value: Any, label: str) -> str:
    """Validate one cross-platform-safe filename component (bundle name or version)."""
    validate_relative_path_syntax(value, label, 'filename-safe value')
    if (
        value == '.'
        or '/' in value
        or '\\' in value
        or any(ch in _WINDOWS_FORBIDDEN_CHARS for ch in value)
        or value[-1] in ' .'
        or value.split('.', 1)[0].rstrip(' ').upper() in _WINDOWS_RESERVED_NAMES
    ):
        raise UnsafePathError(
            f'{label} must be a single filename-safe component: {value}'
        )
    return value


def validate_bundle_identity(bundle_name: Any, bundle_version: Any) -> list[str]:
    """Return errors for the bundle name and the version actually used to name the zip."""
    errors: list[str] = []
    for label, value in (('bundle_name', bundle_name), ('bundle_version', bundle_version)):
        try:
            validate_bundle_identity_component(value, label)
        except UnsafePathError as exc:
            errors.append(str(exc))
    return errors


def _append_list_paths(
    container: dict,
    field: str,
    scope: str,
    values: list[tuple[str, object, str]],
    errors: list[str],
    *,
    label_prefix: str = '',
) -> None:
    if field not in container:
        return
    label = f'{label_prefix}{field}'
    raw = container[field]
    if not isinstance(raw, list):
        errors.append(f'{label} must be a list of root-relative paths')
        return
    for value in raw:
        values.append((label, value, scope))


def _iter_manifest_paths(
    manifest: dict,
    errors: list[str],
) -> list[tuple[str, object, str]]:
    values: list[tuple[str, object, str]] = []
    for field in (
        'required_files',
        'source_required_files',
        'runtime_generated_files',
        'source_only_files',
        'source_only_dirs',
    ):
        _append_list_paths(manifest, field, 'source', values, errors)

    values.append((
        'generated_knowledge_attachment_dir',
        manifest.get('generated_knowledge_attachment_dir', '02_PRIME_AGENT_ATTACHMENTS'),
        'source',
    ))
    _append_list_paths(
        manifest,
        'knowledge_attachment_sources',
        'repo',
        values,
        errors,
    )

    topology = manifest.get('topology', {})
    if not isinstance(topology, dict):
        errors.append('topology must be an object')
    else:
        for field in (
            'prime_agent_file',
            'generated_index_file',
            'quick_start_file',
            'prime_agent_chunk_manifest',
        ):
            value = topology.get(field)
            if value:
                values.append((f'topology.{field}', value, 'source'))
        _append_list_paths(
            topology,
            'sub_agent_files',
            'source',
            values,
            errors,
            label_prefix='topology.',
        )
        _append_list_paths(
            topology,
            'prime_agent_chunk_sources',
            'source',
            values,
            errors,
            label_prefix='topology.',
        )

    chunk_manifest_rel = manifest.get('prime_agent_chunk_manifest')
    if chunk_manifest_rel:
        values.append(('prime_agent_chunk_manifest', chunk_manifest_rel, 'source'))
    return values


def validate_manifest_paths(
    manifest: object,
    source_root: Path,
    repo_root: Path,
) -> list[str]:
    """Return path-safety errors for manifest fields before downstream access.

    Bundle identity is checked separately by validate_bundle_identity, against
    the version that will actually name the archive.
    """
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ['Gemini bundle manifest must be an object']

    seen: set[tuple[str, str]] = set()
    for label, value, scope in _iter_manifest_paths(manifest, errors):
        key = (scope, repr(value))
        if key in seen:
            continue
        seen.add(key)
        root = source_root if scope == 'source' else repo_root
        try:
            resolve_contained_path(root, value, label)
        except UnsafePathError as exc:
            errors.append(str(exc))

    chunk_manifest_rel = manifest.get('prime_agent_chunk_manifest')
    if chunk_manifest_rel:
        try:
            chunk_manifest_path = resolve_contained_path(
                source_root,
                chunk_manifest_rel,
                'prime_agent_chunk_manifest',
            )
        except UnsafePathError:
            return errors
        if chunk_manifest_path.exists():
            try:
                chunk_manifest = json.loads(
                    chunk_manifest_path.read_text(encoding='utf-8')
                )
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append(
                    'prime_agent_chunk_manifest could not be read: '
                    f'{type(exc).__name__}'
                )
                return errors
            if not isinstance(chunk_manifest, dict):
                errors.append('prime_agent_chunk_manifest must contain a JSON object')
                return errors

            target = chunk_manifest.get('generated_prime_agent_file')
            if target is not None:
                try:
                    resolve_contained_path(
                        source_root,
                        target,
                        'generated_prime_agent_file',
                    )
                except UnsafePathError as exc:
                    errors.append(str(exc))

            chunks = chunk_manifest.get('chunks', [])
            if not isinstance(chunks, list):
                errors.append('prime_agent_chunk_manifest.chunks must be a list')
                return errors
            for entry in chunks:
                value = entry.get('path') if isinstance(entry, dict) else None
                try:
                    resolve_contained_path(
                        source_root,
                        value,
                        'prime agent chunk path',
                    )
                except UnsafePathError as exc:
                    errors.append(str(exc))
    return errors
