#!/usr/bin/env python3
"""Collector and harness assembly builders for PowerShell parity validation."""
from __future__ import annotations

from powershell_assembly_parity_common import *
from powershell_assembly_parity_parsing import parse_powershell_text

def build_collector_output(
    repo_root: Path,
    manifest: dict[str, Any],
    errors: list[str],
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    manifest_path_error_count = sum(
        "must be a repo-relative path without traversal" in error
        or "must resolve inside the repository root" in error
        for error in errors
    )
    wrapper_rel = require_non_empty_string(manifest, "collector_wrapper_source", "collector manifest", repo_root, errors)
    part_rels = require_non_empty_string_list(manifest, "collector_part_files", "collector manifest", repo_root, errors)
    if sum(
        "must be a repo-relative path without traversal" in error
        or "must resolve inside the repository root" in error
        for error in errors
    ) > manifest_path_error_count:
        return "", [], {}
    compiled_name = manifest.get("compiled_runtime_name", "DCOIR_Collector.ps1")
    if not isinstance(compiled_name, str) or not compiled_name.strip():
        errors.append("collector manifest: compiled_runtime_name must be a non-empty string")
        compiled_name = "DCOIR_Collector.ps1"

    source_entries: list[dict[str, Any]] = []
    wrapper_path = repo_root / wrapper_rel
    wrapper_entry = part_entry(wrapper_path, repo_root)
    wrapper_entry["role"] = "collector_runtime_wrapper"
    source_entries.append(wrapper_entry)
    if not wrapper_entry["exists"]:
        errors.append(f"{wrapper_rel}: collector wrapper is missing")
        return "", source_entries, {}
    wrapper_text = wrapper_path.read_text(encoding="utf-8")
    if not COLLECTOR_IMPORT_BLOCK.search(wrapper_text):
        errors.append(f"{wrapper_rel}: collector wrapper import block is missing or no longer matches the compiler contract")

    blocks: list[str] = ["# BEGIN COMPILED COLLECTOR PARTS"]
    line_map: list[dict[str, Any]] = []
    generated_line = 2
    for part_rel in part_rels:
        part_path = repo_root / part_rel
        entry = part_entry(part_path, repo_root)
        entry["role"] = "collector_runtime_source_part"
        source_entries.append(entry)
        if not entry["exists"]:
            errors.append(f"{part_rel}: collector source part is missing")
            continue
        if entry["empty"]:
            errors.append(f"{part_rel}: collector source part is empty")
            continue
        text = read_part_text(part_path)
        part_lines = source_line_count(text)
        blocks.append(f"# BEGIN {part_path.name}")
        blocks.append(text.rstrip("\n"))
        blocks.append(f"# END {part_path.name}")
        blocks.append("")
        line_map.append(
            {
                "source_path": part_rel,
                "source_line_start": 1,
                "source_line_end": part_lines,
                "generated_line_start": generated_line + 1,
                "generated_line_end": generated_line + part_lines,
                "mapping_basis": "compiler_begin_end_markers",
            }
        )
        generated_line += part_lines + 3
    blocks.append("# END COMPILED COLLECTOR PARTS")
    inline_block = "\n".join(blocks) + "\n"
    generated_text = COLLECTOR_IMPORT_BLOCK.sub(lambda _m: inline_block, wrapper_text, count=1)
    if not generated_text.endswith("\n"):
        generated_text += "\n"
    output = {
        "id": "collector_compiled_runtime",
        "path": f"compiled_runtime/{compiled_name}",
        "repo_committed_path": None,
        "assembly_model": manifest.get("source_strategy"),
        "source_input_count": len(part_rels),
        "line_mapping_status": "available",
        "line_mapping": line_map,
        "sha256": sha256_text(generated_text),
        "line_count": source_line_count(generated_text),
        "parse": parse_powershell_text(generated_text),
        "parity": {
            "status": "pass",
            "comparison": "deterministic_in_memory_regeneration",
            "checked_in_output_compared": False,
        },
    }
    return generated_text, source_entries, output


def harness_part_paths(repo_root: Path, errors: list[str] | None = None) -> list[Path]:
    root = repo_root / HARNESS_PARTS_ROOT
    if not path_resolves_inside_repo(root, repo_root):
        if errors is not None:
            errors.append(f"{HARNESS_PARTS_ROOT.as_posix()}: harness source parts root must resolve inside the repository root")
        return []
    if not root.is_dir():
        return []
    paths: list[Path] = []
    for path in sorted(root.glob("run_DCOIR_Tests.part-*.ps1.txt")):
        if not path_resolves_inside_repo(path, repo_root):
            if errors is not None:
                errors.append(f"{safe_relpath(path, repo_root)}: harness source part must resolve inside the repository root")
            continue
        if not path.is_file():
            continue
        paths.append(path)
    return paths

def build_harness_output(repo_root: Path, errors: list[str]) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    parts = harness_part_paths(repo_root, errors)
    source_entries: list[dict[str, Any]] = []
    if not parts:
        errors.append(f"{HARNESS_PARTS_ROOT.as_posix()}: no harness source parts found")

    assembled: list[str] = []
    line_map: list[dict[str, Any]] = []
    generated_line = 1
    for part_path in parts:
        part_rel = safe_relpath(part_path, repo_root)
        entry = part_entry(part_path, repo_root)
        entry["role"] = "collector_harness_source_part"
        source_entries.append(entry)
        if entry["empty"]:
            errors.append(f"{part_rel}: harness source part is empty")
            continue
        text = read_part_text(part_path)
        assembled.append(text)
        part_lines = source_line_count(text)
        line_map.append(
            {
                "source_path": part_rel,
                "source_line_start": 1,
                "source_line_end": part_lines,
                "generated_line_start": generated_line,
                "generated_line_end": generated_line + part_lines - 1,
                "mapping_basis": "deterministic_sorted_concatenation",
            }
        )
        generated_line += part_lines
    generated_text = "".join(assembled)
    if generated_text and not generated_text.endswith("\n"):
        generated_text += "\n"

    expected_path = repo_root / HARNESS_GENERATED_OUTPUT
    parity: dict[str, Any] = {
        "status": "pass",
        "comparison": "deterministic_in_memory_regeneration",
        "checked_in_output_compared": False,
        "expected_presence": "optional_when_generated",
    }
    if path_is_file_inside_repo(expected_path, repo_root):
        expected_text = normalize_text(expected_path.read_text(encoding="utf-8"))
        if not expected_text.endswith("\n"):
            expected_text += "\n"
        parity.update(
            {
                "checked_in_output_compared": True,
                "checked_in_path": HARNESS_GENERATED_OUTPUT.as_posix(),
                "checked_in_sha256_normalized": sha256_text(expected_text),
                "generated_sha256": sha256_text(generated_text),
            }
        )
        if sha256_text(expected_text) != sha256_text(generated_text):
            parity["status"] = "fail"
            parity["comparison"] = "checked_in_generated_output_is_stale"
            errors.append(f"{HARNESS_GENERATED_OUTPUT.as_posix()}: checked-in generated harness is stale")
    else:
        if not path_resolves_inside_repo(expected_path, repo_root):
            parity["status"] = "fail"
            parity["comparison"] = "checked_in_generated_output_resolves_outside_repo"
            errors.append(f"{HARNESS_GENERATED_OUTPUT.as_posix()}: checked-in generated harness must resolve inside the repository root")
        else:
            parity["comparison"] = "deterministic_regeneration_only_checked_in_output_absent"
        parity["checked_in_path"] = HARNESS_GENERATED_OUTPUT.as_posix()

    output = {
        "id": "harness_generated_tests",
        "path": HARNESS_GENERATED_OUTPUT.as_posix(),
        "repo_committed_path": HARNESS_GENERATED_OUTPUT.as_posix() if expected_path.exists() else None,
        "assembly_model": "sorted_harness_source_part_concatenation",
        "source_input_count": len(parts),
        "line_mapping_status": "available",
        "line_mapping": line_map,
        "sha256": sha256_text(generated_text),
        "line_count": source_line_count(generated_text),
        "parse": parse_powershell_text(generated_text),
        "parity": parity,
    }
    return generated_text, source_entries, output
