#!/usr/bin/env python3
"""Validate required repo surfaces for named workflow profiles."""
from __future__ import annotations

import argparse
import json
import sys
from importlib import util as import_util
from pathlib import Path

# Load this shipped sibling by file path, even when this checker is imported
# through importlib from an unrelated current working directory.
_group_file = Path(__file__).resolve().with_name("required_surface_profile_groups.py")
_group_spec = import_util.spec_from_file_location("dcoir_required_surface_profile_groups", _group_file)
if _group_spec is None or _group_spec.loader is None:
    raise ImportError(f"Unable to load required-surface group helper: {_group_file}")
_group_module = import_util.module_from_spec(_group_spec)
_group_spec.loader.exec_module(_group_module)
validate_repo_relative_path = _group_module.validate_repo_relative_path
ensure_repo_local_source = _group_module.ensure_repo_local_source
verify_flat = _group_module.verify_flat

PROFILE_PATH = Path(".github/github_actions/workflow_required_surface_profiles.json")
SUPPLEMENT_MANIFEST_PATH = Path(".github/github_actions/workflow_required_surface_profile_supplements.json")


def validate_profile_map(data: object, label: str) -> dict[str, list[str]]:
    if not isinstance(data, dict):
        raise ValueError(f"Profile file must be a JSON object: {label}")
    profiles: dict[str, list[str]] = {}
    for name, paths in data.items():
        if not isinstance(name, str) or not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
            raise ValueError(f"Profile {name!r} must map to a list of string paths: {label}")
        for path in paths:
            validate_repo_relative_path(path, label)
        profiles[name] = paths
    return profiles


def load_json_file(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {label}: {exc}") from exc


def merge_profile_paths(profiles: dict[str, list[str]], additions: dict[str, list[str]]) -> None:
    for name, paths in additions.items():
        merged = profiles.setdefault(name, [])
        seen = set(merged)
        for path in paths:
            if path not in seen:
                merged.append(path)
                seen.add(path)


def load_profile_supplements(repo_root: Path) -> dict[str, list[str]]:
    manifest_file = repo_root / SUPPLEMENT_MANIFEST_PATH
    ensure_repo_local_source(repo_root, manifest_file, "Required surface profile supplement manifest")
    if not manifest_file.is_file():
        raise FileNotFoundError(
            f"Required surface profile supplement manifest missing: {SUPPLEMENT_MANIFEST_PATH.as_posix()}"
        )

    manifest = load_json_file(manifest_file, SUPPLEMENT_MANIFEST_PATH.as_posix())
    if not isinstance(manifest, dict):
        raise ValueError(f"Required surface profile supplement manifest must be a JSON object: {SUPPLEMENT_MANIFEST_PATH.as_posix()}")
    supplements = manifest.get("supplements")
    if not isinstance(supplements, list) or not all(isinstance(path, str) for path in supplements):
        raise ValueError(f"Required surface profile supplement manifest must define a list of supplement paths: {SUPPLEMENT_MANIFEST_PATH.as_posix()}")

    merged: dict[str, list[str]] = {}
    for rel in supplements:
        try:
            validate_repo_relative_path(rel, SUPPLEMENT_MANIFEST_PATH.as_posix())
        except ValueError as exc:
            raise ValueError(f"Required surface profile supplement path must be repo-relative: {rel}") from exc
        supplement_file = repo_root / Path(rel)
        ensure_repo_local_source(repo_root, supplement_file, "Required surface profile supplement file")
        if not supplement_file.is_file():
            raise FileNotFoundError(f"Required surface profile supplement file missing: {rel}")
        merge_profile_paths(merged, validate_profile_map(load_json_file(supplement_file, rel), rel))
    return merged


def load_profiles(repo_root: Path) -> dict[str, list[str]]:
    profile_file = repo_root / PROFILE_PATH
    ensure_repo_local_source(repo_root, profile_file, "Required surface profile file")
    if not profile_file.is_file():
        raise FileNotFoundError(f"Required surface profile file missing: {PROFILE_PATH.as_posix()}")
    profiles = validate_profile_map(load_json_file(profile_file, PROFILE_PATH.as_posix()), PROFILE_PATH.as_posix())
    additions = load_profile_supplements(repo_root)
    verify_flat(repo_root, base_profiles=profiles)
    merge_profile_paths(profiles, additions)
    return profiles


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, help="Required surface profile name")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    try:
        profiles = load_profiles(repo_root)
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.profile not in profiles:
        available = ", ".join(sorted(profiles))
        print(
            f"Required surface profile not found: {args.profile}. Available profiles: {available}",
            file=sys.stderr,
        )
        return 1

    required_paths = profiles[args.profile]
    escaped: list[str] = []
    for path in required_paths:
        target = repo_root / path
        if target.is_symlink() and not target.exists():
            print(
                f"Unable to resolve required governed surface for profile {args.profile}: {path}: dangling or circular symlink",
                file=sys.stderr,
            )
            return 1
        try:
            resolved = target.resolve()
        except (OSError, RuntimeError) as exc:
            print(
                f"Unable to resolve required governed surface for profile {args.profile}: {path}: {exc}",
                file=sys.stderr,
            )
            return 1
        if not resolved.is_relative_to(repo_root):
            escaped.append(path)
    if escaped:
        print(
            f"Required governed surfaces resolve outside repository for profile {args.profile}: {', '.join(escaped)}",
            file=sys.stderr,
        )
        return 1
    missing = [path for path in required_paths if not (repo_root / path).exists()]
    if missing:
        print(
            f"Missing required governed surfaces for profile {args.profile}: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    print(f"Required surface profile {args.profile} validated: {len(required_paths)} paths present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
