#!/usr/bin/env python3
"""Fail-closed containment for manifest-controlled Gemini bundle paths."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class GeminiBundlePathError(ValueError):
    """Raised when a manifest-controlled path is unsafe or cannot be resolved."""


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


def resolve_contained_path(root: Path, value: Any, label: str) -> Path:
    """Resolve a manifest path under root without allowing traversal or escape."""
    if not isinstance(value, str) or not value:
        raise GeminiBundlePathError(
            f'{label} must be a non-empty root-relative path'
        )

    relative = Path(value)
    if relative.is_absolute() or '..' in relative.parts:
        raise GeminiBundlePathError(
            f'{label} must not be absolute or contain traversal: {value}'
        )

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


def _iter_manifest_paths(manifest: dict) -> list[tuple[str, object, str]]:
    values: list[tuple[str, object, str]] = []
    for field in (
        'required_files',
        'source_required_files',
        'runtime_generated_files',
        'source_only_files',
        'source_only_dirs',
    ):
        for value in manifest.get(field, []):
            values.append((field, value, 'source'))
    values.append((
        'generated_knowledge_attachment_dir',
        manifest.get('generated_knowledge_attachment_dir', '02_PRIME_AGENT_ATTACHMENTS'),
        'source',
    ))
    for value in manifest.get('knowledge_attachment_sources', []):
        values.append(('knowledge_attachment_sources', value, 'repo'))

    topology = manifest.get('topology', {})
    if isinstance(topology, dict):
        for field in ('prime_agent_file', 'generated_index_file', 'quick_start_file', 'prime_agent_chunk_manifest'):
            value = topology.get(field)
            if value:
                values.append((f'topology.{field}', value, 'source'))
        for value in topology.get('sub_agent_files', []):
            values.append(('topology.sub_agent_files', value, 'source'))
        for value in topology.get('prime_agent_chunk_sources', []):
            values.append(('topology.prime_agent_chunk_sources', value, 'source'))

    chunk_manifest_rel = manifest.get('prime_agent_chunk_manifest')
    if chunk_manifest_rel:
        values.append(('prime_agent_chunk_manifest', chunk_manifest_rel, 'source'))
    return values


def validate_manifest_paths(
    manifest: dict,
    source_root: Path,
    repo_root: Path,
) -> list[str]:
    """Return path-safety errors for manifest fields before downstream access."""
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for label, value, scope in _iter_manifest_paths(manifest):
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
            except (OSError, json.JSONDecodeError):
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
            for entry in chunk_manifest.get('chunks', []):
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
