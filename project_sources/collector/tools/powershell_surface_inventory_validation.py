#!/usr/bin/env python3
"""Summary, control, and validation helpers for PowerShell surface inventory."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from powershell_surface_inventory_common import KNOWN_CATEGORIES, MANIFEST_PATH, PRIMARY_COLLECTOR_CATEGORIES, PRIMARY_HARNESS_CATEGORIES, REQUIRED_FULL_MODE_CATEGORIES, REQUIRED_SOURCE_TYPES, REQUIRED_SURFACE_PROFILES_PATH, load_json_file
from powershell_surface_inventory_discovery import required_profile_control_path
from powershell_surface_inventory_controls import build_controls

def summarize(surfaces: list[dict[str, Any]]) -> dict[str, Any]:
    by_category = Counter(entry["category"] for entry in surfaces)
    by_source_type = Counter(entry["source_type"] for entry in surfaces)
    by_status = Counter(entry["status"] for entry in surfaces)
    by_decision = Counter(entry["inclusion_decision"] for entry in surfaces)
    for source_type in REQUIRED_SOURCE_TYPES:
        by_source_type.setdefault(source_type, 0)
    for category in KNOWN_CATEGORIES:
        by_category.setdefault(category, 0)
    return {
        "total_surfaces": len(surfaces),
        "by_category": dict(sorted(by_category.items())),
        "by_source_type": dict(sorted(by_source_type.items())),
        "by_status": dict(sorted(by_status.items())),
        "by_inclusion_decision": dict(sorted(by_decision.items())),
        "embedded_snippet_count": sum(len(entry.get("embedded_snippets", [])) for entry in surfaces),
    }


def contiguous_harness_part_errors(harness_parts: list[str]) -> list[str]:
    numbers: list[int] = []
    for rel in harness_parts:
        match = re.search(r"run_DCOIR_Tests\.part-(\d{3})\.ps1\.txt$", rel)
        if match:
            numbers.append(int(match.group(1)))
    if not numbers:
        return []
    expected = set(range(min(numbers), max(numbers) + 1))
    missing = sorted(expected - set(numbers))
    if missing:
        return ["Harness source part numbering has gaps: " + ", ".join(f"{number:03d}" for number in missing)]
    return []




def load_shrink_exceptions(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    data = load_json_file(path)
    if not isinstance(data, dict):
        raise ValueError("Shrink exception file must be a JSON object")
    exceptions = data.get("allowed_category_shrink", {})
    if not isinstance(exceptions, dict):
        raise ValueError("allowed_category_shrink must be a JSON object")
    normalized: dict[str, str] = {}
    for category, reason in exceptions.items():
        if not isinstance(category, str) or not isinstance(reason, str) or not reason.strip():
            raise ValueError("Each shrink exception must map a category to a non-empty reason")
        normalized[category] = reason.strip()
    return normalized


def validate_inventory(
    surfaces: list[dict[str, Any]],
    mode: str,
    controls: dict[str, Any],
    dependency_expansion: dict[str, Any] | None = None,
    baseline: dict[str, Any] | None = None,
    shrink_exceptions: dict[str, str] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    shrink_exceptions = shrink_exceptions or {}

    paths = [entry["path"] for entry in surfaces]
    duplicate_paths = sorted(path for path, count in Counter(paths).items() if count > 1)
    if duplicate_paths:
        errors.append("Duplicate PowerShell inventory paths: " + ", ".join(duplicate_paths))

    for entry in surfaces:
        if entry["category"].startswith("unclassified") or entry["inclusion_decision"] == "fail":
            errors.append(f"{entry['path']}: {entry['decision_reason']}")
        if entry["inclusion_decision"] == "exclude" and not entry.get("decision_reason"):
            errors.append(f"{entry['path']}: excluded surface is missing a documented reason")
        if entry["source_type"] not in REQUIRED_SOURCE_TYPES:
            errors.append(f"{entry['path']}: unsupported source type {entry['source_type']}")
        if entry.get("exists") and entry.get("size_bytes") is None:
            errors.append(f"{entry['path']}: file facts could not be collected safely inside the repository root")
        if (
            entry["source_type"] != "workflow_yaml"
            and entry["inclusion_decision"] != "exclude"
            and entry.get("exists")
            and entry.get("size_bytes") == 0
        ):
            errors.append(f"{entry['path']}: included PowerShell surface is empty")
        marker_lines = entry.get("marker_lines")
        if not isinstance(marker_lines, list) or not all(isinstance(line, int) for line in marker_lines):
            errors.append(f"{entry['path']}: marker_lines must be a list of line numbers")
        if not isinstance(entry.get("embedded_snippets"), list):
            errors.append(f"{entry['path']}: embedded_snippets must be a list")
        if entry["category"] == "workflow_embedded_powershell" and not entry.get("embedded_snippets"):
            errors.append(f"{entry['path']}: workflow PowerShell surface has no extracted snippet records")

    category_counts = Counter(entry["category"] for entry in surfaces)
    input_paths = set((dependency_expansion or {}).get("input_paths", []))
    manifest_required = (
        mode == "full"
        or MANIFEST_PATH.as_posix() in input_paths
        or any(entry["category"] in PRIMARY_COLLECTOR_CATEGORIES for entry in surfaces)
    )
    if manifest_required:
        collector_control = controls.get("collector_manifest", {})
        if collector_control.get("error"):
            errors.append(str(collector_control["error"]))
        if collector_control.get("expected_path_count", 0) == 0:
            errors.append("Collector runtime manifest did not provide any expected PowerShell source paths")
        if collector_control.get("present_path_count") != collector_control.get("expected_path_count"):
            errors.append("Collector runtime manifest references missing PowerShell source paths")
        for entry in collector_control.get("paths", []):
            if mode == "full" and entry.get("exists") and not entry.get("in_inventory"):
                errors.append(f"{entry['path']}: manifest-listed collector path is missing from inventory")
            if entry.get("exists") and not entry.get("expected_category"):
                errors.append(f"{entry['path']}: manifest-listed collector path has no inventory category")
            if entry.get("exists") and entry.get("size_bytes") == 0:
                errors.append(f"{entry['path']}: manifest-listed collector path is empty")
        manifest_paths = {entry.get("path") for entry in collector_control.get("paths", [])}
        for entry in surfaces:
            if entry["category"] in PRIMARY_COLLECTOR_CATEGORIES and entry["path"] not in manifest_paths:
                errors.append(f"{entry['path']}: primary collector runtime source is not listed in {MANIFEST_PATH.as_posix()}")

    profile_control_required = any(required_profile_control_path(path) for path in input_paths)
    harness_required = (
        mode == "full"
        or profile_control_required
        or any(entry["category"] in PRIMARY_HARNESS_CATEGORIES for entry in surfaces)
    )
    if harness_required:
        harness_control = controls.get("harness_source_parts", {})
        harness_parts = [entry["path"] for entry in harness_control.get("parts", [])]
        if profile_control_required and not harness_control.get("required_profile_exists"):
            errors.append(f"Required surface profile is missing: {REQUIRED_SURFACE_PROFILES_PATH.as_posix()}")
        if harness_control.get("required_profile_error"):
            errors.append(str(harness_control["required_profile_error"]))
        if profile_control_required and harness_control.get("required_profile_part_count", 0) == 0:
            errors.append(f"Required surface profile did not provide any harness source parts: {REQUIRED_SURFACE_PROFILES_PATH.as_posix()}")
        if harness_control.get("part_count", 0) == 0:
            errors.append("Harness source parts inventory is empty")
        if harness_control.get("required_profile_part_count", 0) > 0:
            if harness_control.get("required_profile_present_count") != harness_control.get("required_profile_part_count"):
                errors.append(
                    f"Harness source parts required by {REQUIRED_SURFACE_PROFILES_PATH.as_posix()} are missing"
                )
            for entry in harness_control.get("required_profile_parts", []):
                if mode == "full" and entry.get("exists") and not entry.get("in_inventory"):
                    errors.append(f"{entry['path']}: profile-required harness source part is missing from inventory")
                if entry.get("exists") and entry.get("size_bytes") == 0:
                    errors.append(f"{entry['path']}: profile-required harness source part is empty")
        required_profile_paths = {part.get("path") for part in harness_control.get("required_profile_parts", [])}
        for entry in harness_control.get("parts", []):
            path_in_current_inventory = entry.get("path") in paths
            if mode == "full" and entry.get("exists") and not entry.get("category"):
                errors.append(f"{entry['path']}: harness source part is missing from inventory")
            if entry.get("exists") and entry.get("size_bytes") == 0:
                errors.append(f"{entry['path']}: harness source part is empty")
            if (
                harness_control.get("required_profile_part_count", 0) > 0
                and (mode == "full" or path_in_current_inventory)
                and entry.get("path") not in required_profile_paths
            ):
                errors.append(f"{entry['path']}: harness source part is not listed in {REQUIRED_SURFACE_PROFILES_PATH.as_posix()}")
        errors.extend(contiguous_harness_part_errors(harness_parts))

    if mode == "full":
        if not surfaces:
            errors.append("PowerShell inventory is empty")
        missing_categories = sorted(category for category in REQUIRED_FULL_MODE_CATEGORIES if category_counts[category] == 0)
        if missing_categories:
            errors.append("Full inventory is missing required collector/harness categories: " + ", ".join(missing_categories))
        if not any(entry["category"] in PRIMARY_COLLECTOR_CATEGORIES for entry in surfaces):
            errors.append("Full inventory has empty collector surface coverage")
        if not any(entry["category"] in PRIMARY_HARNESS_CATEGORIES for entry in surfaces):
            errors.append("Full inventory has empty harness surface coverage")

    if baseline is not None and mode != "full":
        errors.append("Baseline shrink checks require full inventory mode; changed-file mode is a subset.")
    elif baseline is not None:
        baseline_counts = baseline.get("summary", {}).get("by_category", {})
        if not isinstance(baseline_counts, dict):
            errors.append("Baseline inventory is missing summary.by_category")
        else:
            for category, old_count in sorted(baseline_counts.items()):
                if not isinstance(old_count, int):
                    errors.append(f"Baseline category {category} count is not an integer")
                    continue
                new_count = category_counts.get(category, 0)
                if new_count < old_count and category not in shrink_exceptions:
                    errors.append(
                        f"Category {category} unexpectedly shrank from {old_count} to {new_count} without an approved exception"
                    )
                elif new_count < old_count:
                    warnings.append(
                        f"Category {category} shrink allowed by exception: {shrink_exceptions[category]}"
                    )

    return {
        "success": not errors,
        "errors": errors,
        "warnings": warnings,
    }


__all__ = [
    "summarize",
    "contiguous_harness_part_errors",
    "build_controls",
    "load_shrink_exceptions",
    "validate_inventory",
]
