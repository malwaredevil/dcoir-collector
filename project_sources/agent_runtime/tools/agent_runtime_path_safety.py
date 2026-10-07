#!/usr/bin/env python3
"""Shared fail-closed containment for manifest-controlled relative paths.

This module is the single owner of root-relative path containment for the
agent-runtime package builders and the Gemini bundle tooling. Callers keep only
their own error-reporting adapter (exception vs. collected error list).
"""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


class UnsafePathError(ValueError):
    """Raised when a manifest-controlled path is unsafe or cannot be resolved."""


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


def validate_relative_path_syntax(
    value: Any,
    label: str,
    expected: str = 'root-relative path',
) -> Path:
    """Reject path syntax that is unsafe under either POSIX or Windows semantics.

    expected names what value should be (for example 'repository-relative path')
    and only shapes the empty-value error message.
    """
    if not isinstance(value, str) or not value:
        raise UnsafePathError(f'{label} must be a non-empty {expected}')
    if any(ord(ch) < 32 for ch in value):
        raise UnsafePathError(f'{label} must not contain control characters')

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
        raise UnsafePathError(
            f'{label} must not be absolute or contain traversal: {value}'
        )
    return Path(value)


def resolve_contained_path(
    root: Path,
    value: Any,
    label: str,
    *,
    root_kind: str = 'root',
    root_name: str = 'its root',
    allow_root: bool = False,
) -> Path:
    """Resolve value under root without allowing traversal, symlink escape or loops.

    root_kind and root_name only shape error messages. allow_root=False also
    rejects values such as '.' that resolve to the root itself.
    """
    relative = validate_relative_path_syntax(value, label, f'{root_kind}-relative path')
    try:
        resolved_root = root.resolve()
    except (OSError, RuntimeError) as exc:
        raise UnsafePathError(
            f'{label} root could not be resolved: {type(exc).__name__}'
        ) from exc
    try:
        reject_unfollowable_symlinks(resolved_root, relative)
        candidate = (resolved_root / relative).resolve()
    except (OSError, RuntimeError) as exc:
        raise UnsafePathError(
            f'{label} path could not be resolved: {type(exc).__name__}'
        ) from exc
    if not candidate.is_relative_to(resolved_root):
        raise UnsafePathError(f'{label} escapes {root_name}: {value}')
    if not allow_root and candidate == resolved_root:
        raise UnsafePathError(
            f'{label} must name a path inside {root_name}, not the root itself: {value}'
        )
    return candidate


def resolve_repo_path(
    repo_root: Path,
    value: Any,
    label: str,
    errors: list[str],
    required_root: Path | None = None,
) -> Path | None:
    """Resolve a repository-relative path, appending to errors instead of raising."""
    try:
        candidate = resolve_contained_path(
            repo_root,
            value,
            label,
            root_kind='repository',
            root_name='the repository',
            allow_root=True,
        )
    except UnsafePathError as exc:
        errors.append(str(exc))
        return None
    if required_root is not None:
        try:
            resolved_repo = repo_root.resolve()
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
