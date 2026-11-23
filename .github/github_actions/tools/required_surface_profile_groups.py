#!/usr/bin/env python3
"""Canonical grouped required-surface profiles and checked flat compatibility output."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path, PureWindowsPath

GROUPS_PATH = Path(".github/github_actions/workflow_required_surface_profile_groups.json")
FLAT_PATH = Path(".github/github_actions/workflow_required_surface_profiles.json")
SCHEMA_VERSION = "dcoir_required_surface_profile_groups_v1"
EXPECTED_PROFILES = (
    "validate_on_push", "validate_on_pr", "manual_full_validation",
    "scheduled_health_check", "manual_gemini_bundle_build",
    "manual_gemini_model_comparison", "manual_collector_runtime_package_build",
    "manual_openai_gpt_deployment_package_build",
)


def validate_repo_relative_path(path: str, label: str) -> None:
    """Accept a normalized repository-relative literal path, never a traversal."""
    if (
        not isinstance(path, str)
        or not path or path != path.strip()
        or any(ord(ch) < 32 for ch in path)
        or chr(92) in path
        or Path(path).is_absolute()
        or bool(PureWindowsPath(path).drive)
        or any(part in {"", ".", ".."} for part in path.split("/"))
    ):
        raise ValueError(f"Required surface must be a normalized repo-relative path in {label}: {path!r}")


def ensure_repo_local_source(repo_root: Path, source: Path, label: str) -> None:
    """Reject source files whose canonical location escapes the checkout."""
    try:
        root = repo_root.resolve()
        resolved = source.resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"Unable to resolve {label}: {exc}") from exc
    if not resolved.is_relative_to(root):
        raise ValueError(f"{label} resolves outside repository: {source}")


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON property: {key}")
        result[key] = value
    return result


def _read_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {label}: {exc}") from exc


def expand_canonical(data: object) -> dict[str, list[str]]:
    """Expand literal groups in declared order with no implicit deduplication."""
    if not isinstance(data, dict) or set(data) != {"schema_version", "groups", "profiles"}:
        raise ValueError("Grouped required-surface source must have three exact schema keys")
    if data["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported grouped required-surface schema version")
    groups = data["groups"]
    profiles = data["profiles"]
    if not isinstance(groups, dict) or not groups:
        raise ValueError("Grouped required-surface groups must be a nonempty mapping")
    if not isinstance(profiles, dict) or tuple(profiles) != EXPECTED_PROFILES:
        raise ValueError("Grouped required-surface profiles must contain exactly eight expected names in order")

    checked_groups: dict[str, list[str]] = {}
    for group, paths in groups.items():
        if not isinstance(group, str) or not group or group != group.strip():
            raise ValueError(f"Invalid group name: {group!r}")
        if not isinstance(paths, list) or not paths:
            raise ValueError(f"Group {group!r} must have a nonempty list of literal paths")
        for path in paths:
            validate_repo_relative_path(path, f"group {group}")
        if len(set(paths)) != len(paths):
            raise ValueError(f"Duplicate path inside group {group}")
        checked_groups[group] = paths

    result: dict[str, list[str]] = {}
    for name, segments in profiles.items():
        if not isinstance(segments, list) or not segments:
            raise ValueError(f"Profile {name} must have a nonempty list of segments")
        found: list[str] = []
        seen: set[str] = set()
        for index, segment in enumerate(segments):
            label = f"profile {name} segment {index}"
            if not isinstance(segment, dict):
                raise ValueError(f"Invalid {label}: a segment must be an object")
            if set(segment) == {"group"}:
                key = segment["group"]
                if not isinstance(key, str) or key not in checked_groups:
                    raise ValueError(f"Unknown group {key!r} in {label}")
                paths = checked_groups[key]
            elif set(segment) == {"paths"}:
                paths = segment["paths"]
                if not isinstance(paths, list) or not paths:
                    raise ValueError(f"Invalid {label}: paths must be a nonempty list")
                for path in paths:
                    validate_repo_relative_path(path, label)
            else:
                raise ValueError(f"Invalid {label}: exactly one group or paths key required")
            for path in paths:
                if path in seen:
                    raise ValueError(f"Duplicate path {path!r} in profile {name}")
                seen.add(path)
                found.append(path)
        result[name] = found
    return result


def _local_file(repo_root: Path, relative: Path, label: str, *, required: bool) -> Path:
    root = repo_root.resolve()
    path = root / relative
    ensure_repo_local_source(root, path, label)
    if required and not path.is_file():
        raise FileNotFoundError(f"{label} missing: {relative.as_posix()}")
    if path.exists() and not path.is_file():
        raise ValueError(f"{label} is not a regular file: {relative.as_posix()}")
    return path


def read_groups(repo_root: Path) -> dict[str, list[str]]:
    path = _local_file(repo_root, GROUPS_PATH, "Required surface grouped profile source", required=True)
    return expand_canonical(_read_json(path, GROUPS_PATH.as_posix()))


def canonical_flat_text(profiles: dict[str, list[str]]) -> str:
    return json.dumps(profiles, indent=2, ensure_ascii=True) + "\n"


def _validate_flat(data: object) -> dict[str, list[str]]:
    if not isinstance(data, dict) or tuple(data) != EXPECTED_PROFILES:
        raise ValueError("Flat required-surface profiles must contain the eight expected profile names in order")
    for name, paths in data.items():
        if not isinstance(paths, list) or not paths:
            raise ValueError(f"Flat required-surface profile {name} must be a nonempty list")
        for path in paths:
            validate_repo_relative_path(path, f"flat profile {name}")
        if len(set(paths)) != len(paths):
            raise ValueError(f"Duplicate path in flat required-surface profile {name}")
    return data


def verify_flat(repo_root: Path, base_profiles: dict[str, list[str]] | None = None) -> None:
    expected = read_groups(repo_root)
    path = _local_file(repo_root, FLAT_PATH, "Required surface flat profile artifact", required=True)
    actual_text = path.read_text(encoding="utf-8")
    actual = _validate_flat(_read_json(path, FLAT_PATH.as_posix()))
    if actual != expected or (base_profiles is not None and base_profiles != expected):
        raise ValueError("Stale required-surface flat profile artifact: ordered paths differ from canonical groups")
    if actual_text != canonical_flat_text(expected):
        raise ValueError("Stale required-surface flat profile artifact: regenerate canonical formatting")


def write_flat(repo_root: Path) -> None:
    expected = read_groups(repo_root)
    root = repo_root.resolve()
    path = root / FLAT_PATH
    ensure_repo_local_source(root, path, "Required surface flat profile artifact")
    if path.is_symlink():
        raise ValueError(f"Required surface flat artifact must not be a symlink: {FLAT_PATH}")
    if path.exists() and not path.is_file():
        raise ValueError(f"Required surface flat artifact is not a regular file: {FLAT_PATH}")
    if not path.parent.is_dir():
        raise FileNotFoundError(f"Required surface flat artifact directory missing: {path.parent}")
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, prefix=".surface-profiles-", suffix=".tmp", delete=False) as stream:
            temporary = stream.name
            stream.write(canonical_flat_text(expected))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    try:
        repo_root = Path(args.repo_root).resolve()
        if args.check:
            verify_flat(repo_root)
        else:
            write_flat(repo_root)
    except (OSError, ValueError, RuntimeError, UnicodeError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
