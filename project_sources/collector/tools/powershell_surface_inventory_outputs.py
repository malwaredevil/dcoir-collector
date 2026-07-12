#!/usr/bin/env python3
"""Inventory assembly and report rendering for PowerShell surfaces."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from powershell_surface_inventory_common import (
    DEFAULT_JSON_OUTPUT,
    DEFAULT_MARKDOWN_OUTPUT,
    ISSUE_NUMBER,
    REQUIRED_SOURCE_TYPES,
    SCHEMA_VERSION,
    repo_relative_cli_path,
)
from powershell_surface_inventory_discovery import collect_surfaces
from powershell_surface_inventory_validation import build_controls, summarize, validate_inventory

def build_inventory(
    repo_root: Path,
    changed_files: list[str] | None = None,
    baseline: dict[str, Any] | None = None,
    shrink_exceptions: dict[str, str] | None = None,
    json_output: Path = DEFAULT_JSON_OUTPUT,
    markdown_output: Path = DEFAULT_MARKDOWN_OUTPUT,
) -> dict[str, Any]:
    surfaces, source, dependency_expansion = collect_surfaces(repo_root, changed_files)
    mode = "changed" if changed_files is not None else "full"
    summary = summarize(surfaces)
    controls = build_controls(repo_root, surfaces)
    validation = validate_inventory(surfaces, mode, controls, dependency_expansion, baseline, shrink_exceptions)
    command_parts = [
        "python",
        "project_sources/collector/tools/build_powershell_surface_inventory.py",
        "--repo-root",
        ".",
        "--json-output",
        json_output.as_posix(),
        "--markdown-output",
        markdown_output.as_posix(),
    ]
    if changed_files is not None:
        command_parts.extend(["--changed-file", "<path>"])
    return {
        "schema_version": SCHEMA_VERSION,
        "issue": ISSUE_NUMBER,
        "mode": mode,
        "source_of_truth": source,
        "deterministic_report": True,
        "file_facts_policy": "text_bytes_with_line_endings_normalized_to_lf",
        "discovery_command": " ".join(command_parts),
        "required_source_types": REQUIRED_SOURCE_TYPES,
        "outputs": {
            "json": json_output.as_posix(),
            "markdown": markdown_output.as_posix(),
        },
        "changed_file_dependency_expansion": dependency_expansion,
        "summary": summary,
        "controls": controls,
        "validation": validation,
        "surfaces": surfaces,
    }


def markdown_table(mapping: dict[str, Any], key_name: str, value_name: str = "Count") -> list[str]:
    lines = [f"| {key_name} | {value_name} |", "| --- | ---: |"]
    for key, value in sorted(mapping.items()):
        lines.append(f"| `{key}` | {value} |")
    return lines


def render_markdown(inventory: dict[str, Any]) -> str:
    summary = inventory["summary"]
    validation = inventory["validation"]
    lines = [
        "# PowerShell Surface Inventory",
        "",
        f"- Schema: `{inventory['schema_version']}`",
        f"- Issue: #{inventory['issue']}",
        f"- Mode: `{inventory['mode']}`",
        f"- Source of truth: `{inventory['source_of_truth']}`",
        f"- File facts policy: `{inventory['file_facts_policy']}`",
        f"- Discovery command: `{inventory['discovery_command']}`",
        f"- JSON artifact: `{inventory['outputs']['json']}`",
        f"- Validation: `{'pass' if validation['success'] else 'fail'}`",
        "",
        "## Counts By Category",
        "",
    ]
    lines.extend(markdown_table(summary["by_category"], "Category"))
    lines.extend(["", "## Counts By Source Type", ""])
    lines.extend(markdown_table(summary["by_source_type"], "Source Type"))
    lines.extend(["", "## Counts By Inclusion Decision", ""])
    lines.extend(markdown_table(summary["by_inclusion_decision"], "Decision"))
    lines.extend(["", "## Control Totals", ""])
    controls = inventory["controls"]
    collector = controls["collector_manifest"]
    harness = controls["harness_source_parts"]
    lines.extend(
        [
            f"- Collector manifest expected paths: `{collector['expected_path_count']}`",
            f"- Collector manifest present paths: `{collector['present_path_count']}`",
            f"- Harness source parts: `{harness['part_count']}`",
            f"- Profile-required harness source parts: `{harness['required_profile_part_count']}`",
            f"- Profile-required harness source parts present: `{harness['required_profile_present_count']}`",
            f"- Embedded workflow/action snippets: `{summary['embedded_snippet_count']}`",
        ]
    )
    if inventory.get("changed_file_dependency_expansion"):
        expansion = inventory["changed_file_dependency_expansion"]
        lines.extend(["", "## Changed-File Dependency Expansion", ""])
        lines.append(f"- Boundary: {expansion['boundary']}")
        lines.append(f"- Input paths: `{len(expansion['input_paths'])}`")
        lines.append(f"- Expanded paths: `{len(expansion['expanded_paths'])}`")
    exclusions = [
        entry
        for entry in inventory["surfaces"]
        if entry["inclusion_decision"] in {"exclude", "reference"}
    ]
    lines.extend(["", "## Reference And Excluded Surfaces", ""])
    if exclusions:
        lines.extend(["| Path | Category | Decision | Reason |", "| --- | --- | --- | --- |"])
        for entry in exclusions:
            lines.append(
                f"| `{entry['path']}` | `{entry['category']}` | `{entry['inclusion_decision']}` | {entry['decision_reason']} |"
            )
    else:
        lines.append("No reference or excluded PowerShell surfaces were discovered.")
    lines.extend(["", "## Validation Findings", ""])
    if validation["errors"]:
        lines.append("Errors:")
        lines.extend(f"- {error}" for error in validation["errors"])
    else:
        lines.append("- No validation errors.")
    if validation["warnings"]:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in validation["warnings"])
    lines.append("")
    return "\n".join(lines)


def write_outputs(repo_root: Path, inventory: dict[str, Any], json_output: Path, markdown_output: Path) -> list[str]:
    errors: list[str] = []
    try:
        json_path = repo_relative_cli_path(repo_root, json_output, "PowerShell surface inventory JSON report output path")
        markdown_path = repo_relative_cli_path(
            repo_root,
            markdown_output,
            "PowerShell surface inventory Markdown report output path",
        )
    except ValueError as exc:
        return [str(exc)]
    if json_path == markdown_path:
        return ["PowerShell surface inventory JSON and Markdown report output paths must be different"]
    try:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        errors.append(f"PowerShell surface inventory report write failure: {json_path}: {exc}")
        return errors
    try:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(inventory), encoding="utf-8")
    except OSError as exc:
        errors.append(f"PowerShell surface inventory report write failure: {markdown_path}: {exc}")
    return errors


__all__ = [
    "build_inventory",
    "markdown_table",
    "render_markdown",
    "write_outputs",
]
