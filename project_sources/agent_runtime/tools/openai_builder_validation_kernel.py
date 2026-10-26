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


def validate_generated_root_no_symlink(
    repo_root: Path,
    generated_root_value: object,
    errors: list[str],
) -> None:
    """Reject a symlink at the lexical generated root before any file reads/writes.

    Repo-root syntax and containment are checked independently by resolve_repo_path.
    Do not resolve this leaf first: resolution would conceal symlink indirection.
    """
    if not isinstance(generated_root_value, str):
        return
    if any(ord(char) < 32 or ord(char) == 127 for char in generated_root_value):
        errors.append('Generated package root path could not be checked: control characters')
        return
    generated_root_path = repo_root / generated_root_value
    try:
        is_link = generated_root_path.is_symlink()
    except (OSError, ValueError, RuntimeError) as exc:
        errors.append(
            f'Generated package root path could not be checked: {type(exc).__name__}'
        )
        return
    if is_link:
        try:
            label = generated_root_path.relative_to(repo_root).as_posix()
        except ValueError:
            label = str(generated_root_path)
        errors.append(f'Generated package root must not be a symlink: {label}')


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
