#!/usr/bin/env python3
"""Shared fail-closed repository path resolution for agent-runtime tooling."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def reject_unfollowable_symlinks(root: Path, relative: Path) -> None:
    """Raise OSError when a symlink along root/relative cannot be followed.

    Path.resolve() raises RuntimeError on symlink loops only before Python 3.13;
    newer versions return the unresolved path, so each link is followed explicitly.
    A file below a looping directory stats as missing on Windows, so every link on
    the path is checked, not just the final component.
    """
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            try:
                os.stat(current)
            except FileNotFoundError:
                return


def resolve_repo_path(
    repo_root: Path,
    value: Any,
    label: str,
    errors: list[str],
    required_root: Path | None = None,
) -> Path | None:
    """Resolve a repository-relative path without allowing traversal or escape."""
    if not isinstance(value, str) or not value:
        errors.append(f'{label} must be a non-empty repository-relative path')
        return None
    relative = Path(value)
    if relative.is_absolute() or '..' in relative.parts:
        errors.append(f'{label} must not be absolute or contain traversal: {value}')
        return None
    try:
        resolved_repo = repo_root.resolve()
    except (OSError, RuntimeError) as exc:
        errors.append(
            f'{label} repository root could not be resolved: {type(exc).__name__}'
        )
        return None
    try:
        reject_unfollowable_symlinks(resolved_repo, relative)
        candidate = (resolved_repo / relative).resolve()
    except (OSError, RuntimeError) as exc:
        errors.append(f'{label} path could not be resolved: {type(exc).__name__}')
        return None
    if not candidate.is_relative_to(resolved_repo):
        errors.append(f'{label} escapes the repository: {value}')
        return None
    if required_root is not None:
        try:
            resolved_required_root = required_root.resolve()
        except (OSError, RuntimeError) as exc:
            errors.append(
                f'{label} declared root could not be resolved: {type(exc).__name__}'
            )
            return None
        if not resolved_required_root.is_relative_to(resolved_repo):
            errors.append(
                f'{label} declared root escapes the repository: '
                f'{resolved_required_root.as_posix()}'
            )
            return None
        if not candidate.is_relative_to(resolved_required_root):
            errors.append(f'{label} is outside its declared root: {value}')
            return None
    return candidate
