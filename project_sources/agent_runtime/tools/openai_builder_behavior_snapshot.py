#!/usr/bin/env python3
"""Canonical OpenAI GPT behavior-source coverage snapshot validation.

Target identity, Instructions owner, section vocabulary and expected count stay
with each builder. This module owns shared manifest ordering, disposition,
source path containment, module hash verification and stable snapshot identity.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from agent_runtime_path_safety import resolve_repo_path
from openai_builder_validation_kernel import (
    index_governed_behavior_modules,
    validate_behavior_disposition,
)


def _snapshot_hash(value: list[dict[str, Any]]) -> str:
    payload = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def validate_behavior_snapshot(
    repo_root: Path,
    source_contract: dict[str, Any],
    behavior_manifest: dict[str, Any],
    coverage: list[dict[str, Any]],
    errors: list[str],
    *,
    target_id: str,
    expected_count: int,
    instructions_path: str,
    section_headings: dict[str, str],
) -> tuple[list[dict[str, Any]], str]:
    """Validate per-target behavior coverage and return ordered pinned records."""
    items = source_contract.get('behavior_items')
    modules = behavior_manifest.get('modules')
    if not isinstance(items, list) or not isinstance(modules, list):
        errors.append('Behavior source inventories must be arrays')
        return [], _snapshot_hash([])
    applicable = [item for item in items if isinstance(item, dict) and target_id in (
        item.get('applies_to') if isinstance(item.get('applies_to'), list) else []
    )]
    if not isinstance(coverage, list):
        errors.append('Adapter coverage must be an array')
        coverage = []
    modules_by_id = index_governed_behavior_modules(modules, errors)
    coverage_ids = [entry.get('id') for entry in coverage if isinstance(entry, dict)]
    expected_ids = [item.get('id') for item in applicable]
    for item in applicable:
        validate_behavior_disposition(item, target_id, instructions_path, errors)
    for value, count in sorted(Counter(v for v in coverage_ids if isinstance(v, str)).items()):
        if count > 1:
            errors.append(f'Duplicate behavior coverage id: {value}')
    if coverage_ids != expected_ids:
        errors.append(f'Behavior coverage must exactly match source-contract order: {coverage_ids} != {expected_ids}')
    if len(expected_ids) != expected_count:
        errors.append(f'Expected {expected_count} applicable behavior items, got {len(expected_ids)}')
    snapshot: list[dict[str, Any]] = []
    for item, coverage_entry in zip(applicable, coverage):
        item_id = item.get('id')
        if not isinstance(item_id, str) or not item_id:
            errors.append('Behavior item id must be a non-empty string')
            continue
        source_value = item.get('source_path')
        path = resolve_repo_path(repo_root, source_value, f'{item_id} source_path', errors)
        if path is None:
            continue
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            errors.append(f'Missing behavior source {item_id}: {path}')
            content = b''
        except OSError as exc:
            errors.append(f'Unreadable behavior source {item_id}: {path} ({type(exc).__name__})')
            content = b''
        digest = hashlib.sha256(content).hexdigest()
        source_module = modules_by_id.get(item_id)
        if source_module is None:
            errors.append(f'Behavior module manifest lacks {item_id}')
        else:
            if source_module.get('source_path') != source_value:
                errors.append(f'Behavior path disagreement for {item_id}')
            if source_module.get('sha256') != digest:
                errors.append(f'Behavior source hash drift for {item_id}')
        sections = coverage_entry.get('sections') if isinstance(coverage_entry, dict) else None
        if not isinstance(sections, list) or not sections or not all(
            isinstance(section, str) and section in section_headings for section in sections
        ):
            errors.append(f'{item_id} has invalid instruction section coverage')
            sections = []
        snapshot.append({
            'id': item_id,
            'source_path': source_value,
            'sha256': digest,
            'sections': sections,
        })
    return snapshot, _snapshot_hash(snapshot)
