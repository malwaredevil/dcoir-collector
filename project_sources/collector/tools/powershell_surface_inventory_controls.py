#!/usr/bin/env python3
"""Summary, control, and validation helpers for PowerShell surface inventory."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from powershell_surface_inventory_common import MANIFEST_PATH, REQUIRED_SURFACE_PROFILE_SUPPLEMENTS_PATH, REQUIRED_SURFACE_PROFILES_PATH, HARNESS_GENERATED_OUTPUT, HARNESS_PARTS_ROOT, file_facts, repo_file_exists
from powershell_surface_inventory_discovery import classify_surface, collector_manifest_paths, harness_source_part_paths, manifest_error, read_required_profile_harness_paths

def build_controls(repo_root: Path, surfaces: list[dict[str, Any]]) -> dict[str, Any]:
    manifest_paths = collector_manifest_paths(repo_root)
    harness_parts = harness_source_part_paths(repo_root)
    profile_harness_paths, profile_error = read_required_profile_harness_paths(repo_root)
    by_path = {entry["path"]: entry for entry in surfaces}
    expected_generated = HARNESS_GENERATED_OUTPUT.as_posix()
    manifest_entries: list[dict[str, Any]] = []
    for rel in manifest_paths:
        exists = repo_file_exists(repo_root, rel)
        discovered_surface = by_path.get(rel)
        classified_surface = classify_surface(repo_root, rel, exists) if exists else None
        facts = file_facts(repo_root, rel, exists)
        manifest_entries.append(
            {
                "path": rel,
                "exists": exists,
                "in_inventory": rel in by_path,
                "category": discovered_surface.get("category") if discovered_surface else None,
                "expected_category": classified_surface.get("category") if classified_surface else None,
                "size_bytes": facts["size_bytes"],
            }
        )
    return {
        "collector_manifest": {
            "path": MANIFEST_PATH.as_posix(),
            "exists": repo_file_exists(repo_root, MANIFEST_PATH.as_posix()),
            "error": manifest_error(repo_root),
            "expected_path_count": len(manifest_paths),
            "present_path_count": sum(1 for rel in manifest_paths if repo_file_exists(repo_root, rel)),
            "paths": manifest_entries,
        },
        "harness_source_parts": {
            "root": HARNESS_PARTS_ROOT.as_posix(),
            "part_count": len(harness_parts),
            "required_profile_path": REQUIRED_SURFACE_PROFILES_PATH.as_posix(),
            "required_profile_exists": repo_file_exists(repo_root, REQUIRED_SURFACE_PROFILES_PATH.as_posix()),
            "required_profile_supplement_manifest_path": REQUIRED_SURFACE_PROFILE_SUPPLEMENTS_PATH.as_posix(),
            "required_profile_supplement_manifest_exists": repo_file_exists(
                repo_root,
                REQUIRED_SURFACE_PROFILE_SUPPLEMENTS_PATH.as_posix(),
            ),
            "required_profile_error": profile_error,
            "required_profile_part_count": len(profile_harness_paths),
            "required_profile_present_count": sum(1 for rel in profile_harness_paths if repo_file_exists(repo_root, rel)),
            "required_profile_parts": [
                {
                    "path": rel,
                    "exists": repo_file_exists(repo_root, rel),
                    "in_inventory": rel in by_path,
                    "category": by_path.get(rel, {}).get("category"),
                    "size_bytes": by_path.get(rel, {}).get("size_bytes"),
                }
                for rel in profile_harness_paths
            ],
            "parts": [
                {
                    "path": rel,
                    "exists": repo_file_exists(repo_root, rel),
                    "category": by_path.get(rel, {}).get("category"),
                    "size_bytes": by_path.get(rel, {}).get("size_bytes"),
                }
                for rel in harness_parts
            ],
        },
        "generated_outputs": [
            {
                "path": expected_generated,
                "expected_presence": "optional_when_generated",
                "exists": repo_file_exists(repo_root, expected_generated),
                "category": by_path.get(expected_generated, {}).get("category"),
            }
        ],
    }
