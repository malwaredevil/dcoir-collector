#!/usr/bin/env python3
"""Discovery, classification, and dependency expansion for PowerShell surfaces."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from powershell_surface_inventory_common import MANIFEST_PATH, is_ignored_discovery_path, is_powershell_file, is_workflow_yaml, make_surface, path_resolves_inside_repo, repo_file_exists
from powershell_surface_inventory_classification import classify_surface
from powershell_surface_inventory_profiles import (
    load_manifest,
    manifest_error,
    normalize_manifest_surface_path,
    collector_manifest_path_entries,
    collector_manifest_path_errors,
    collector_manifest_paths,
    harness_source_part_paths,
    required_profile_control_path,
    validate_required_profile_map,
    merge_required_profile_paths,
    load_required_profile_json,
    load_required_profile_supplements,
    read_required_profiles,
    read_required_profile_harness_paths,
    required_profile_harness_paths,
)



def git_tracked_files(repo_root: Path) -> list[str] | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "-z"],
            capture_output=True,
            text=False,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    paths = [path.decode("utf-8", errors="ignore") for path in completed.stdout.split(b"\0") if path]
    return sorted(path for path in paths if not is_ignored_discovery_path(path))


def filesystem_files(repo_root: Path) -> list[str]:
    files: list[str] = []
    for path in repo_root.rglob("*"):
        if not path_resolves_inside_repo(path, repo_root):
            continue
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(repo_root).as_posix()
        except (OSError, ValueError):
            continue
        if is_ignored_discovery_path(rel):
            continue
        files.append(rel)
    return sorted(files)


def discover_repo_files(repo_root: Path) -> tuple[list[str], str]:
    tracked = git_tracked_files(repo_root)
    if tracked is not None:
        return tracked, "git ls-files -z"
    return filesystem_files(repo_root), "filesystem recursive scan fallback"


def normalize_changed_files(values: list[str], repo_root: Path) -> list[str]:
    normalized: list[str] = []
    root = repo_root.resolve()
    for value in values:
        raw = value.strip()
        if not raw:
            raise ValueError("Changed-file input must not be blank")
        slash_path = raw.replace("\\", "/")
        path_parts = tuple(part for part in slash_path.split("/") if part)
        if slash_path.startswith("/") or Path(raw).is_absolute() or re.match(r"^[A-Za-z]:", slash_path) is not None:
            raise ValueError(f"Changed-file input must be repo-relative: {value}")
        if ".." in path_parts:
            raise ValueError(f"Changed-file input must not traverse parents: {value}")
        candidate = root / Path(slash_path)
        try:
            repo_relative = candidate.resolve().relative_to(root)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValueError(f"Changed-file input resolves outside repo root: {value}") from exc
        rel = repo_relative.as_posix()
        if not rel or rel == ".":
            raise ValueError(f"Changed-file input must name a file under repo root: {value}")
        normalized.append(rel)
    return sorted(dict.fromkeys(normalized))


def load_changed_files_from(path: Path) -> list[str]:
    if not path.is_file():
        raise ValueError(f"Changed-files input is missing: {path}")
    try:
        records = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"Changed-files input could not be read: {path}: {exc}") from exc
    return records if records else [""]
































def expand_changed_files(repo_root: Path, changed_files: list[str]) -> tuple[list[str], dict[str, Any]]:
    normalized = normalize_changed_files(changed_files, repo_root)
    expanded: set[str] = set(normalized)
    rules: list[dict[str, Any]] = []
    for rel in normalized:
        added: list[str] = []
        if rel == MANIFEST_PATH.as_posix():
            added = collector_manifest_paths(repo_root)
        elif rel == "project_sources/collector/harness/assemble_run_DCOIR_Tests.ps1":
            added = harness_source_part_paths(repo_root)
        elif required_profile_control_path(rel):
            added = harness_source_part_paths(repo_root)
        elif is_workflow_yaml(rel):
            added = [rel]
        if added:
            expanded.update(added)
            rules.append({"changed_path": rel, "rule": "dependency_expansion", "added_paths": added})
    return sorted(expanded), {
        "input_paths": normalized,
        "expanded_paths": sorted(expanded),
        "rules": rules,
        "boundary": "Dependency expansion covers collector manifest paths, harness assembler source parts, and PowerShell-bearing workflow/action YAML. Other changed paths are classified directly.",
    }


def append_missing_authoritative_surfaces(repo_root: Path, surfaces: list[dict[str, Any]]) -> None:
    existing = {entry["path"] for entry in surfaces}
    for rel in collector_manifest_paths(repo_root):
        if rel not in existing and not repo_file_exists(repo_root, rel):
            surfaces.append(
                make_surface(
                    repo_root,
                    rel,
                    "missing_authoritative_surface",
                    "missing",
                    "fail",
                    "Collector runtime manifest references this PowerShell surface, but the file is missing.",
                    False,
                )
            )


def collect_surfaces(repo_root: Path, changed_files: list[str] | None = None) -> tuple[list[dict[str, Any]], str, dict[str, Any] | None]:
    discovered, source = discover_repo_files(repo_root)
    dependency_expansion = None
    if changed_files is not None:
        candidates, dependency_expansion = expand_changed_files(repo_root, changed_files)
    else:
        candidates = discovered
    surfaces: list[dict[str, Any]] = []
    for rel in candidates:
        exists = repo_file_exists(repo_root, rel)
        if changed_files is not None and not exists and not (is_powershell_file(rel) or is_workflow_yaml(rel)):
            continue
        surface = classify_surface(repo_root, rel, exists)
        if surface is not None:
            surfaces.append(surface)
    if changed_files is None:
        append_missing_authoritative_surfaces(repo_root, surfaces)
    return sorted(surfaces, key=lambda entry: entry["path"]), source, dependency_expansion


__all__ = [
    "classify_surface",
    "git_tracked_files",
    "filesystem_files",
    "discover_repo_files",
    "normalize_changed_files",
    "load_changed_files_from",
    "load_manifest",
    "manifest_error",
    "normalize_manifest_surface_path",
    "collector_manifest_path_entries",
    "collector_manifest_path_errors",
    "collector_manifest_paths",
    "harness_source_part_paths",
    "required_profile_control_path",
    "validate_required_profile_map",
    "merge_required_profile_paths",
    "load_required_profile_json",
    "load_required_profile_supplements",
    "read_required_profiles",
    "read_required_profile_harness_paths",
    "required_profile_harness_paths",
    "expand_changed_files",
    "append_missing_authoritative_surfaces",
    "collect_surfaces",
]
