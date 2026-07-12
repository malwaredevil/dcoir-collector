#!/usr/bin/env python3
"""Validate required repo surfaces for named workflow profiles."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROFILE_PATH = Path("project_sources/github_actions/workflow_required_surface_profiles.json")
SUPPLEMENT_MANIFEST_PATH = Path("project_sources/github_actions/workflow_required_surface_profile_supplements.json")


def validate_profile_map(data: object, label: str) -> dict[str, list[str]]:
    if not isinstance(data, dict):
        raise ValueError(f"Profile file must be a JSON object: {label}")
    profiles: dict[str, list[str]] = {}
    for name, paths in data.items():
        if not isinstance(name, str) or not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
            raise ValueError(f"Profile {name!r} must map to a list of string paths: {label}")
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
    if not manifest_file.is_file():
        return {}

    manifest = load_json_file(manifest_file, SUPPLEMENT_MANIFEST_PATH.as_posix())
    if not isinstance(manifest, dict):
        raise ValueError(f"Required surface profile supplement manifest must be a JSON object: {SUPPLEMENT_MANIFEST_PATH.as_posix()}")
    supplements = manifest.get("supplements")
    if not isinstance(supplements, list) or not all(isinstance(path, str) for path in supplements):
        raise ValueError(f"Required surface profile supplement manifest must define a list of supplement paths: {SUPPLEMENT_MANIFEST_PATH.as_posix()}")

    merged: dict[str, list[str]] = {}
    for rel in supplements:
        supplement_path = Path(rel)
        if supplement_path.is_absolute() or ".." in supplement_path.parts:
            raise ValueError(f"Required surface profile supplement path must be repo-relative: {rel}")
        supplement_file = repo_root / supplement_path
        if not supplement_file.is_file():
            raise FileNotFoundError(f"Required surface profile supplement file missing: {rel}")
        merge_profile_paths(merged, validate_profile_map(load_json_file(supplement_file, rel), rel))
    return merged


def load_profiles(repo_root: Path) -> dict[str, list[str]]:
    profile_file = repo_root / PROFILE_PATH
    if not profile_file.is_file():
        raise FileNotFoundError(f"Required surface profile file missing: {PROFILE_PATH.as_posix()}")
    profiles = validate_profile_map(load_json_file(profile_file, PROFILE_PATH.as_posix()), PROFILE_PATH.as_posix())
    merge_profile_paths(profiles, load_profile_supplements(repo_root))
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
