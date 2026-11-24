#!/usr/bin/env python3
"""Shared source-only safety checks for both static OpenAI GPT package builders.

Each builder retains its provider-specific instruction, Knowledge and behavior
rules. This kernel centralizes strict cross-target gates that must not drift.
"""
from __future__ import annotations

from pathlib import Path

MAX_KNOWLEDGE_FILES = 20


def validate_knowledge_file_ceiling(
    target_manifest: dict,
    projection_count: int,
    errors: list[str],
) -> None:
    """Require an actual integer ceiling within policy and enough capacity."""
    ceiling = target_manifest.get('strict_file_count_ceiling')
    if type(ceiling) is not int or not 1 <= ceiling <= MAX_KNOWLEDGE_FILES or projection_count > ceiling:
        errors.append('Knowledge projection count or ceiling is invalid')


def validate_repo_path_no_symlink(
    repo_root: Path,
    path_value: object,
    errors: list[str],
    label: str,
) -> bool:
    """Reject symlinks in a repository-relative path before resolving it.

    Path syntax and containment are checked independently by resolve_repo_path.
    Do not resolve components first: resolution would conceal symlink indirection.
    """
    if not isinstance(path_value, str):
        return True
    if any(ord(char) < 32 or ord(char) == 127 for char in path_value):
        errors.append(f'{label} path could not be checked: control characters')
        return False
    relative_path = Path(path_value)
    if relative_path.is_absolute() or '..' in relative_path.parts:
        return True
    current = repo_root
    for part in relative_path.parts:
        if part in ('', '.'):
            continue
        current = current / part
        try:
            is_link = current.is_symlink()
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f'{label} path could not be checked: {type(exc).__name__}')
            return False
        if is_link:
            try:
                component = current.relative_to(repo_root).as_posix()
            except ValueError:
                component = str(current)
            errors.append(f'{label} must not be a symlink: {component}')
            return False
    return True


def validate_generated_root_no_symlink(
    repo_root: Path,
    generated_root_value: object,
    errors: list[str],
) -> None:
    """Reject symlinks in the generated root path before any file reads/writes."""
    validate_repo_path_no_symlink(
        repo_root, generated_root_value, errors, 'Generated package root',
    )


def validate_source_output_binding(
    source_target: object,
    target_id: str,
    expected_outputs: dict[str, str],
    errors: list[str],
    target_label: str,
) -> None:
    """Bind source-declared target output owner and ordered files to its builder.

    Target-specific adapter output paths are validated by the existing caller;
    this check prevents silent drift in the shared source contract.
    """
    if not isinstance(source_target, dict):
        return  # Existing callers report missing/non-object targets.
    expected_owner = f'project_sources/agent_runtime/tools/build_{target_id}.py'
    if source_target.get('output_owner') != expected_owner:
        errors.append(f'{target_label} output owner drift')
    if source_target.get('generated_outputs') != list(expected_outputs.values()):
        errors.append('Source contract generated outputs disagree with the adapter')


def validate_behavior_snapshot_pin(
    snapshot_sha: str,
    adapter_manifest: dict,
    errors: list[str],
) -> None:
    """Require a stored adapter snapshot pin that matches the computed SHA."""
    pinned_sha = adapter_manifest.get('behavior_source_snapshot_sha256')
    if not isinstance(pinned_sha, str) or pinned_sha != snapshot_sha:
        errors.append(
            'Behavior source snapshot drift: expected '
            f'{pinned_sha}, got {snapshot_sha}'
        )


def validate_behavior_disposition(
    item: dict,
    target_id: str,
    expected_output: str,
    errors: list[str],
) -> None:
    """Enforce each target's governed static-behavior adaptation contract.

    DCOIR Prime chunks are adapted and specialist sub-agents are flattened.
    USB's eight applicable behavior items must all be adapted.
    """
    item_id = item.get('id', '<missing-id>')
    if not isinstance(item_id, str) or not item_id:
        errors.append(f'{target_id} behavior item id is invalid')
        return
    dispositions = item.get('target_dispositions')
    disposition = dispositions.get(target_id) if isinstance(dispositions, dict) else None
    if not isinstance(disposition, dict):
        errors.append(f'{item_id} lacks a valid {target_id} disposition')
        return

    if target_id == 'openai_dcoir_analyst':
        if item_id.startswith('prime.chunk.'):
            mode = 'adapt'
        elif item_id.startswith('sub_agent.'):
            mode = 'flatten'
        else:
            mode = None
    elif target_id == 'openai_usb_reporting':
        mode = 'adapt'
    else:
        mode = None
    if mode is None:
        errors.append(f'{item_id} has an unsupported {target_id} disposition class')
    elif disposition.get('mode') != mode:
        if target_id == 'openai_usb_reporting':
            errors.append(f'{item_id} must be adapted for {target_id}')
        else:
            errors.append(f'{item_id} {target_id} disposition mode drift: expected {mode}')

    expected_owner = f'project_sources/agent_runtime/tools/build_{target_id}.py'
    if disposition.get('owner') != expected_owner:
        errors.append(f'{item_id} {target_id} disposition owner drift')
    if disposition.get('generated_output') != expected_output:
        errors.append(f'{item_id} {target_id} disposition output drift')


def select_governed_source_target(
    source_contract: dict,
    target_id: str,
    errors: list[str],
    target_label: str,
) -> dict:
    """Require exactly one named source target; never silently pick a duplicate."""
    targets = source_contract.get('targets')
    if not isinstance(targets, list):
        errors.append('Shared source contract targets must be an array')
        return {}
    if any(not isinstance(item, dict) for item in targets):
        errors.append('Shared source contract targets contain a non-object entry')
    matching = [item for item in targets
                if isinstance(item, dict) and item.get('id') == target_id]
    if not matching:
        errors.append(f'Shared source contract lacks the {target_label} target')
        return {}
    if len(matching) != 1:
        errors.append(f'Shared source contract has duplicate {target_label} targets')
        return {}
    return matching[0]


def validate_projection_manifest_binding(
    projection_manifest: dict,
    adapter_manifest: dict,
    target_id: str,
    expected_count: int,
    errors: list[str],
    target_label: str,
    target_manifest: dict,
) -> None:
    """Bind ordered target projections to the governed shared group records."""
    if projection_manifest.get('schema') != 'dcoir.agent_runtime.knowledge_projection.v1':
        errors.append('Unexpected knowledge projection manifest schema')
    targets = projection_manifest.get('targets')
    if not isinstance(targets, dict):
        errors.append('Knowledge projection manifest targets must be an object')
        return
    target = targets.get(target_id)
    if not isinstance(target, dict):
        errors.append(f'Knowledge projection manifest lacks the {target_label} target')
        return
    if target.get('target_manifest_path') != adapter_manifest.get('knowledge_target_manifest'):
        errors.append('Knowledge target manifest path disagrees across contracts')
    count = target.get('expected_projection_count')
    if type(count) is not int or count != expected_count:
        errors.append('Knowledge target projection count disagrees across contracts')
    groups = target.get('projection_groups')
    if not isinstance(groups, list) or len(groups) != expected_count or not all(
        isinstance(group, dict) for group in groups
    ):
        errors.append('Knowledge projection groups must match the expected count')
        return
    ids = [group.get('id') for group in groups]
    if not all(isinstance(value, str) and value.strip() for value in ids):
        errors.append('Knowledge projection group ids must be nonempty strings')
    elif len(set(ids)) != len(ids):
        errors.append('Knowledge projection group ids must be unique')
    if any(type(group.get('order')) is not int for group in groups) or [
        group.get('order') for group in groups
    ] != list(range(expected_count)):
        errors.append('Knowledge projection group order must be contiguous')
    if any(not isinstance(group.get('output_path'), str) or not group['output_path'].strip()
           for group in groups):
        errors.append('Knowledge projection group output paths must be nonempty strings')
    projections = target_manifest.get('projections')
    fields = ('id', 'order', 'output_path')
    if not isinstance(projections, list) or not all(
        isinstance(entry, dict) and type(entry.get('order')) is int
        for entry in projections
    ) or [
        {field: entry.get(field) for field in fields} for entry in projections
    ] != [
        {field: group.get(field) for field in fields} for group in groups
    ]:
        errors.append('Knowledge target projections disagree with governed projection groups')


def index_governed_behavior_modules(modules: list, errors: list[str]) -> dict[str, dict]:
    """Reject non-object, non-string ID and duplicate module records."""
    by_id: dict[str, dict] = {}
    for item in modules:
        if not isinstance(item, dict):
            errors.append('Behavior module inventory contains a non-object entry')
            continue
        module_id = item.get('id')
        if not isinstance(module_id, str) or not module_id:
            errors.append('Behavior module inventory has invalid module id')
            continue
        if module_id in by_id:
            errors.append(f'Duplicate behavior module id: {module_id}')
            continue
        by_id[module_id] = item
    return by_id
