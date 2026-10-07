#!/usr/bin/env python3
"""Fail-closed containment for manifest-controlled Gemini bundle paths."""
from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


class GeminiBundlePathError(ValueError):
    """Raised when a manifest-controlled path is unsafe or cannot be resolved."""


def validate_bundle_identity_component(value: Any, label: str) -> str:
    """Validate a cross-platform-safe single filename/archive component."""
    if not isinstance(value, str) or not value:
        raise GeminiBundlePathError(
            f'{label} must be a non-empty filename-safe value'
        )
    if '\x00' in value or any(ord(ch) < 32 for ch in value):
        raise GeminiBundlePathError(
            f'{label} must not contain control characters'
        )

    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        value in {'.', '..'}
        or posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or len(posix.parts) != 1
        or len(windows.parts) != 1
        or '/' in value
        or '\\' in value
        or any(ch in value for ch in '<>:"|?*')
    ):
        raise GeminiBundlePathError(
            f'{label} must be a single filename-safe component: {value}'
        )
    return value


def _reject_unfollowable_symlinks(root: Path, relative: Path, label: str) -> None:
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            try:
                os.stat(current)
            except FileNotFoundError:
                return
            except OSError as exc:
                raise GeminiBundlePathError(
                    f'{label} path could not be resolved: {type(exc).__name__}'
                ) from exc


def _validate_cross_platform_relative_path(value: Any, label: str) -> Path:
    """Reject path syntax that is unsafe under either POSIX or Windows semantics."""
    if not isinstance(value, str) or not value:
        raise GeminiBundlePathError(
            f'{label} must be a non-empty root-relative path'
        )
    if '\x00' in value or any(ord(ch) < 32 for ch in value):
        raise GeminiBundlePathError(
            f'{label} must not contain control characters'
        )

    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or bool(windows.root)
        or '..' in posix.parts
        or '..' in windows.parts
    ):
        raise GeminiBundlePathError(
            f'{label} must not be absolute or contain traversal: {value}'
        )
    return Path(value)


def resolve_contained_path(root: Path, value: Any, label: str) -> Path:
    """Resolve a manifest path under root without allowing traversal or escape."""
    relative = _validate_cross_platform_relative_path(value, label)

    try:
        resolved_root = root.resolve()
    except (OSError, RuntimeError) as exc:
        raise GeminiBundlePathError(
            f'{label} root could not be resolved: {type(exc).__name__}'
        ) from exc

    try:
        _reject_unfollowable_symlinks(resolved_root, relative, label)
        candidate = (resolved_root / relative).resolve()
    except GeminiBundlePathError:
        raise
    except (OSError, RuntimeError) as exc:
        raise GeminiBundlePathError(
            f'{label} path could not be resolved: {type(exc).__name__}'
        ) from exc

    if not candidate.is_relative_to(resolved_root):
        raise GeminiBundlePathError(f'{label} escapes its root: {value}')

    return candidate


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
    """Return path-safety errors for manifest fields before downstream access."""
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ['Gemini bundle manifest must be an object']

    for field in ('bundle_name', 'bundle_version'):
        if field not in manifest:
            continue
        try:
            validate_bundle_identity_component(manifest[field], field)
        except GeminiBundlePathError as exc:
            errors.append(str(exc))

    seen: set[tuple[str, str]] = set()
    for label, value, scope in _iter_manifest_paths(manifest, errors):
        key = (scope, repr(value))
        if key in seen:
            continue
        seen.add(key)
        root = source_root if scope == 'source' else repo_root
        try:
            resolve_contained_path(root, value, label)
        except GeminiBundlePathError as exc:
            errors.append(str(exc))

    chunk_manifest_rel = manifest.get('prime_agent_chunk_manifest')
    if chunk_manifest_rel:
        try:
            chunk_manifest_path = resolve_contained_path(
                source_root,
                chunk_manifest_rel,
                'prime_agent_chunk_manifest',
            )
        except GeminiBundlePathError:
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
                except GeminiBundlePathError as exc:
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
                except GeminiBundlePathError as exc:
                    errors.append(str(exc))
    return errors
