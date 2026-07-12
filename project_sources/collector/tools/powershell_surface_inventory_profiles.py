#!/usr/bin/env python3
"""Discovery, classification, and dependency expansion for PowerShell surfaces."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from powershell_surface_inventory_common import HARNESS_PARTS_ROOT, MANIFEST_PATH, REQUIRED_SURFACE_PROFILE_SUPPLEMENTS_PATH, REQUIRED_SURFACE_PROFILES_PATH, has_prefix, path_is_dir_inside_repo, path_is_file_inside_repo, path_resolves_inside_repo



def load_manifest(repo_root: Path) -> dict[str, Any] | None:
    path = repo_root / MANIFEST_PATH
    if not path_is_file_inside_repo(path, repo_root):
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def manifest_error(repo_root: Path) -> str | None:
    path = repo_root / MANIFEST_PATH
    if not path_is_file_inside_repo(path, repo_root):
        return f"Collector runtime manifest is missing: {MANIFEST_PATH.as_posix()}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"Invalid JSON in collector runtime manifest {MANIFEST_PATH.as_posix()}: {exc}"
    if not isinstance(data, dict):
        return f"Collector runtime manifest must be a JSON object: {MANIFEST_PATH.as_posix()}"
    path_errors = collector_manifest_path_errors(repo_root)
    if path_errors:
        return "; ".join(path_errors)
    return None


def normalize_manifest_surface_path(value: str, repo_root: Path, field_name: str) -> tuple[str | None, str | None]:
    raw = value.strip()
    if not raw:
        return None, f"Collector runtime manifest {field_name} must not be blank"
    slash_path = raw.replace("\\", "/")
    if Path(slash_path).is_absolute():
        return None, f"Collector runtime manifest {field_name} must be repo-relative, not absolute: {value}"
    if re.match(r"^[A-Za-z]:", slash_path) is not None:
        return None, f"Collector runtime manifest {field_name} must not be drive-qualified: {value}"
    path = Path(slash_path)
    if ".." in path.parts:
        return None, f"Collector runtime manifest {field_name} must not traverse parents: {value}"
    normalized = slash_path
    while normalized.startswith("./"):
        normalized = normalized[2:]
    path = Path(normalized)
    if not normalized or normalized == ".":
        return None, f"Collector runtime manifest {field_name} must name a file under repo root: {value}"
    if ".." in path.parts:
        return None, f"Collector runtime manifest {field_name} must not traverse parents: {value}"
    root = repo_root.resolve()
    try:
        rel = (root / path).resolve().relative_to(root).as_posix()
    except (OSError, RuntimeError, ValueError):
        return None, f"Collector runtime manifest {field_name} resolves outside repo root: {value}"
    if not rel or rel == ".":
        return None, f"Collector runtime manifest {field_name} must name a file under repo root: {value}"
    return rel, None


def collector_manifest_path_entries(repo_root: Path) -> tuple[list[str], list[str]]:
    manifest = load_manifest(repo_root)
    if not manifest:
        return [], []
    paths: list[str] = []
    errors: list[str] = []

    def append_path(value: str, field_name: str) -> None:
        rel, error = normalize_manifest_surface_path(value, repo_root, field_name)
        if error is not None:
            errors.append(error)
        elif rel is not None:
            paths.append(rel)

    wrapper = manifest.get("collector_wrapper_source")
    if isinstance(wrapper, str):
        append_path(wrapper, "collector_wrapper_source")
    part_files = manifest.get("collector_part_files", [])
    if isinstance(part_files, list):
        for index, path in enumerate(part_files):
            if isinstance(path, str):
                append_path(path, f"collector_part_files[{index}]")
    return sorted(dict.fromkeys(paths)), errors


def collector_manifest_path_errors(repo_root: Path) -> list[str]:
    _paths, errors = collector_manifest_path_entries(repo_root)
    return errors


def collector_manifest_paths(repo_root: Path) -> list[str]:
    paths, _errors = collector_manifest_path_entries(repo_root)
    return paths


def harness_source_part_paths(repo_root: Path) -> list[str]:
    root = repo_root / HARNESS_PARTS_ROOT
    if not path_is_dir_inside_repo(root, repo_root):
        return []
    paths: list[str] = []
    for path in root.glob("*.ps1.txt"):
        if not path_resolves_inside_repo(path, repo_root):
            continue
        if not path.is_file():
            continue
        try:
            paths.append(path.relative_to(repo_root).as_posix())
        except (OSError, ValueError):
            continue
    return sorted(paths)


def required_profile_control_path(rel: str) -> bool:
    if rel in {
        REQUIRED_SURFACE_PROFILES_PATH.as_posix(),
        REQUIRED_SURFACE_PROFILE_SUPPLEMENTS_PATH.as_posix(),
    }:
        return True
    return has_prefix(
        rel,
        REQUIRED_SURFACE_PROFILE_SUPPLEMENTS_PATH.parent.as_posix(),
    ) and rel.endswith(".json")


def validate_required_profile_map(data: object, label: str) -> tuple[dict[str, list[str]], str | None]:
    if not isinstance(data, dict):
        return {}, f"Required surface profile must be a JSON object: {label}"
    profiles: dict[str, list[str]] = {}
    for profile_name, paths in data.items():
        if not isinstance(paths, list):
            return {}, f"Required surface profile {profile_name!r} must be a JSON list"
        normalized: list[str] = []
        for index, candidate in enumerate(paths):
            if not isinstance(candidate, str):
                return {}, f"Required surface profile {profile_name!r}[{index}] must be a string"
            normalized.append(candidate)
        profiles[str(profile_name)] = normalized
    return profiles, None


def merge_required_profile_paths(profiles: dict[str, list[str]], additions: dict[str, list[str]]) -> None:
    for profile_name, paths in additions.items():
        merged = profiles.setdefault(profile_name, [])
        seen = set(merged)
        for path in paths:
            if path not in seen:
                merged.append(path)
                seen.add(path)


def load_required_profile_json(repo_root: Path, rel: str, label: str) -> tuple[object | None, str | None]:
    path = repo_root / rel
    if not path_is_file_inside_repo(path, repo_root):
        return None, f"Required surface profile file missing: {rel}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON in {label}: {exc}"


def load_required_profile_supplements(repo_root: Path) -> tuple[dict[str, list[str]], str | None]:
    manifest_rel = REQUIRED_SURFACE_PROFILE_SUPPLEMENTS_PATH.as_posix()
    manifest_path = repo_root / manifest_rel
    if not path_is_file_inside_repo(manifest_path, repo_root):
        return {}, None
    manifest, error = load_required_profile_json(
        repo_root,
        manifest_rel,
        f"required surface profile supplement manifest {manifest_rel}",
    )
    if error is not None:
        return {}, error
    if not isinstance(manifest, dict):
        return {}, f"Required surface profile supplement manifest must be a JSON object: {manifest_rel}"
    supplements = manifest.get("supplements")
    if not isinstance(supplements, list) or not all(isinstance(path, str) for path in supplements):
        return {}, f"Required surface profile supplement manifest must define a list of supplement paths: {manifest_rel}"

    profiles: dict[str, list[str]] = {}
    for rel in supplements:
        path = Path(rel)
        if path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", rel.replace("\\", "/")):
            return {}, f"Required surface profile supplement path must be repo-relative: {rel}"
        data, error = load_required_profile_json(
            repo_root,
            rel,
            f"required surface profile supplement {rel}",
        )
        if error is not None:
            return {}, error
        supplement_profiles, error = validate_required_profile_map(data, rel)
        if error is not None:
            return {}, error
        merge_required_profile_paths(profiles, supplement_profiles)
    return profiles, None


def read_required_profiles(repo_root: Path) -> tuple[dict[str, list[str]], str | None]:
    base_rel = REQUIRED_SURFACE_PROFILES_PATH.as_posix()
    base_path = repo_root / base_rel
    if not path_is_file_inside_repo(base_path, repo_root):
        return {}, None
    try:
        data = json.loads(base_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"Invalid JSON in required surface profile {base_rel}: {exc}"
    profiles, error = validate_required_profile_map(data, base_rel)
    if error is not None:
        return {}, error
    supplements, error = load_required_profile_supplements(repo_root)
    if error is not None:
        return {}, error
    merge_required_profile_paths(profiles, supplements)
    return profiles, None


def read_required_profile_harness_paths(repo_root: Path) -> tuple[list[str], str | None]:
    profiles, error = read_required_profiles(repo_root)
    if error is not None:
        return [], error
    expected: set[str] = set()
    for paths in profiles.values():
        for candidate in paths:
            if has_prefix(candidate, HARNESS_PARTS_ROOT.as_posix()) and candidate.endswith(".ps1.txt"):
                expected.add(candidate)
    return sorted(expected), None


def required_profile_harness_paths(repo_root: Path) -> list[str]:
    paths, _ = read_required_profile_harness_paths(repo_root)
    return paths
