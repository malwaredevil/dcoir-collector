#!/usr/bin/env python3
"""Shared fail-closed generated-file reconciliation for static OpenAI GPTs.

The target-specific builders own manifests, content, output names, and reports.
This module owns identical file inventory, check, staging, write and readback
behavior; it never decides what a package should contain.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from agent_runtime_path_safety import resolve_repo_path


def _relative(repo_root: Path, path: Path, errors: list[str]) -> str | None:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        errors.append('Generated package file must remain inside repository')
        return None


def _inventory(repo_root: Path, generated_root: Path, errors: list[str]) -> set[Path]:
    """List generated files without following symlinked directories."""
    files: set[Path] = set()
    try:
        if generated_root.is_symlink():
            errors.append(f'Generated package must not contain symlinks: {generated_root}')
            return files
        if not generated_root.exists():
            return files
        stack = [generated_root]
        while stack:
            directory = stack.pop()
            for entry in directory.iterdir():
                if entry.is_symlink():
                    errors.append(f'Generated package must not contain symlinks: {entry}')
                elif entry.is_dir():
                    stack.append(entry)
                elif entry.is_file():
                    files.add(entry.resolve())
    except (OSError, RuntimeError) as exc:
        errors.append(
            f'Generated package inventory could not be read: {type(exc).__name__}'
        )
    return files


def _check_files(
    repo_root: Path, expected_files: dict[Path, bytes], errors: list[str],
) -> None:
    for path, expected in expected_files.items():
        label = _relative(repo_root, path, errors)
        if label is None:
            continue
        try:
            linked = next(
                (part for part in (path, *path.parents)
                 if part.is_relative_to(repo_root) and part.is_symlink()),
                None,
            )
        except (OSError, RuntimeError) as exc:
            errors.append(f"Generated package path could not be checked: {type(exc).__name__}")
            continue
        if linked is not None:
            errors.append(f"Generated package must not contain symlinks: {linked}")
            continue
        try:
            actual = path.read_bytes()
        except FileNotFoundError:
            errors.append(f'Missing generated package file: {label}')
            continue
        except (OSError, RuntimeError) as exc:
            errors.append(
                f'Unreadable generated package file: {label} ({type(exc).__name__})'
            )
            continue
        if actual != expected:
            errors.append(f'Generated package drift: {label}')


def _materialize(
    repo_root: Path,
    generated_root: Path,
    expected_files: dict[Path, bytes],
    errors: list[str],
    staging_prefix: str,
) -> None:
    """Stage and verify every file before writing any output.

    Revalidate every destination against the generated root before copy.
    Write/readback failures cause a non-success report; never claim success
    from a partial or unreadable file.
    """
    try:
        with tempfile.TemporaryDirectory(prefix=staging_prefix, dir=repo_root) as temp:
            temp_root = Path(temp).resolve()
            staged_files: list[tuple[Path, bytes, Path]] = []
            for path, expected in expected_files.items():
                label = _relative(repo_root, path, errors)
                if label is None:
                    continue
                try:
                    with tempfile.NamedTemporaryFile(
                        dir=temp_root, delete=False
                    ) as staged:
                        staged.write(expected)
                        staged_path = Path(staged.name).resolve()
                    if not staged_path.is_relative_to(temp_root):
                        errors.append('Generated package staging path escaped its root')
                        continue
                    if staged_path.read_bytes() != expected:
                        errors.append('Generated package staging readback failed')
                        continue
                    destination = resolve_repo_path(
                        repo_root, label, 'generated package output',
                        errors, generated_root,
                    )
                    if destination is not None:
                        staged_files.append((destination, expected, staged_path))
                except (OSError, RuntimeError) as exc:
                    errors.append(
                        f'Generated package staging failed: {type(exc).__name__}'
                    )
            if errors:
                return
            for destination, expected, staged_path in staged_files:
                try:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(staged_path, destination)
                    if destination.read_bytes() != expected:
                        errors.append(
                            f'Generated package write readback failed: {destination}'
                        )
                        break
                except (OSError, RuntimeError) as exc:
                    errors.append(
                        f'Generated package write/readback failed: '
                        f'{_relative(repo_root, destination, errors)} '
                        f'({type(exc).__name__})'
                    )
                    break
    except (OSError, RuntimeError) as exc:
        errors.append(
            f'Generated package staging root failed: {type(exc).__name__}'
        )


def reconcile_generated_package(
    repo_root: Path,
    generated_root: Path,
    expected_files: dict[Path, bytes],
    errors: list[str],
    *,
    check: bool,
    staging_prefix: str,
) -> None:
    """Enforce the same generated-package contract for both OpenAI builders."""
    # An already-invalid adapter/source must never inspect or write package files.
    if errors:
        return
    expected: set[Path] = set()
    for path in expected_files:
        if _relative(repo_root, path, errors) is not None:
            expected.add(path)
    if errors:
        return
    found = _inventory(repo_root, generated_root, errors)
    stale = sorted(
        label for path in found - expected
        if (label := _relative(repo_root, path, errors)) is not None
    )
    if stale:
        errors.append(f'Stale generated package files: {stale}')
    if check:
        _check_files(repo_root, expected_files, errors)
    elif not errors:
        _materialize(repo_root, generated_root, expected_files, errors, staging_prefix)
