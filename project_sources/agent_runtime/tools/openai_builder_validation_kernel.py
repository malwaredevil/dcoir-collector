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
