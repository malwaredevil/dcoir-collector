#!/usr/bin/env python3
"""Canonical validation and accounting of OpenAI GPT Knowledge projections.

Both governed builders pass their target-specific identity and expected count.
This module owns the path, ordering, bytes/hash, and strict ceiling behavior.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from agent_runtime_path_safety import resolve_repo_path
from openai_builder_validation_kernel import (
    validate_knowledge_file_ceiling,
    validate_repo_path_no_symlink,
)


def validate_knowledge_projections(
    repo_root: Path,
    target_manifest: dict[str, Any],
    errors: list[str],
    *,
    target_id: str,
    schema: str,
    expected_count: int,
    label: str,
) -> list[dict[str, Any]]:
    """Return ordered, verified Knowledge records or accumulate fail-closed errors."""
    if target_manifest.get('schema') != schema:
        errors.append(f'Unexpected {label} knowledge target manifest schema')
    if target_manifest.get('target_id') != target_id:
        errors.append('Knowledge target manifest has the wrong target_id')
    projections = target_manifest.get('projections')
    if not isinstance(projections, list):
        errors.append('Knowledge target projections must be an array')
        return []
    if len(projections) != expected_count:
        errors.append(f'Expected {expected_count} {label} knowledge files, got {len(projections)}')
    validate_knowledge_file_ceiling(target_manifest, len(projections), errors)

    orders = [entry.get('order') for entry in projections if isinstance(entry, dict)]
    if orders != list(range(len(projections))):
        errors.append('Knowledge projection order must be contiguous')
    knowledge_root = (
        f'project_sources/agent_runtime/generated/knowledge/{target_id}'
    )
    if not validate_repo_path_no_symlink(
        repo_root, knowledge_root, errors, 'Knowledge target root',
    ):
        return []
    knowledge_root = repo_root / knowledge_root
    records: list[dict[str, Any]] = []
    for entry in projections:
        if not isinstance(entry, dict):
            errors.append('Knowledge projections contain a non-object entry')
            continue
        path = resolve_repo_path(
            repo_root, entry.get('output_path'),
            f"knowledge projection {entry.get('id')}", errors, knowledge_root,
        )
        if path is None:
            continue
        if path.is_symlink():
            errors.append(f'Knowledge projection must not be a symlink: {path}')
            continue
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            errors.append(f'Missing knowledge projection: {path}')
            content = b''
        except OSError as exc:
            errors.append(f'Unreadable knowledge projection: {path} ({type(exc).__name__})')
            content = b''
        actual_sha = hashlib.sha256(content).hexdigest()
        if actual_sha != entry.get('sha256') or len(content) != entry.get('bytes'):
            errors.append(f"Knowledge projection drift: {entry.get('id')}")
        records.append({
            'id': entry.get('id'),
            'order': entry.get('order'),
            'path': entry.get('output_path'),
            'sha256': actual_sha,
            'bytes': len(content),
        })
    return records
