#!/usr/bin/env python3
"""Workflow/action YAML validation and PowerShell snippet extraction."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from powershell_surface_inventory_common import WORKFLOW_MARKER_RE, read_text
from powershell_surface_inventory_yaml import (
    block_end_line,
    collect_run_block,
    command_text_for_marker_scan,
    empty_block_scalar_run_key,
    executable_steps_key,
    flow_collection_shape_error,
    flow_mapping_fragment_error,
    is_invalid_block_scalar_like_value,
    is_powershell_shell,
    is_yaml_block_scalar_marker,
    line_indent,
    misindented_step_workflow_key,
    nonscalar_workflow_string_value_key,
    normalize_workflow_scalar,
    split_flow_mapping,
    step_blocks,
    strip_yaml_inline_comment,
    strip_yaml_node_prefixes,
    unsupported_block_scalar_workflow_string_key,
    unsupported_flow_step_mapping_key,
    unsupported_inline_executable_steps_key,
    yaml_block_scalar_indent_indicator,
    yaml_item_text,
    yaml_item_text_without_comment,
    yaml_mapping_key_indent,
    yaml_unclosed_quote,
)

def workflow_yaml_shape_error(repo_root: Path, rel: str) -> str | None:
    text = read_text(repo_root / rel)
    if not text.strip():
        return f"{rel}: workflow/action YAML is empty"

    lines = text.splitlines()
    block_scalar_indent: int | None = None
    block_scalar_required_indent: int | None = None
    block_scalar_auto_indent: int | None = None

    for line_number, line in enumerate(lines, start=1):
        indent = line_indent(line)
        if line[:indent].find("\t") != -1:
            return f"{rel}: line {line_number} uses a tab for indentation"

        stripped = line.strip()
        if block_scalar_indent is not None:
            if not stripped:
                continue
            if indent > block_scalar_indent:
                if block_scalar_required_indent is not None and indent < block_scalar_required_indent:
                    return f"{rel}: line {line_number} is less indented than the YAML block scalar requires"
                if block_scalar_required_indent is None:
                    if block_scalar_auto_indent is None:
                        block_scalar_auto_indent = indent
                    elif indent < block_scalar_auto_indent:
                        return f"{rel}: line {line_number} is less indented than the YAML block scalar requires"
                continue
            block_scalar_indent = None
            block_scalar_required_indent = None
            block_scalar_auto_indent = None
        if not stripped or stripped.startswith("#"):
            continue
        if indent % 2 != 0:
            return f"{rel}: line {line_number} uses unsupported odd indentation"

        item = yaml_item_text(line)
        if not stripped.startswith("- ") and ":" not in item:
            return f"{rel}: line {line_number} has no YAML key/value separator"

        value = item.split(":", 1)[1].strip() if ":" in item else ""
        value_without_comment = strip_yaml_inline_comment(value)
        unclosed_quote = yaml_unclosed_quote(value)
        if unclosed_quote:
            return f"{rel}: line {line_number} has an unterminated quoted scalar"
        flow_error = flow_collection_shape_error(rel, line_number, item, value_without_comment)
        if flow_error:
            return flow_error
        flow_fragment_error = flow_mapping_fragment_error(rel, line_number, item, value_without_comment)
        if flow_fragment_error:
            return flow_fragment_error
        flow_step_key = unsupported_flow_step_mapping_key(
            lines,
            line_number - 1,
            item,
        )
        if flow_step_key:
            return f"{rel}: line {line_number} has unsupported flow step key {flow_step_key!r}"
        inline_steps_key = unsupported_inline_executable_steps_key(
            lines,
            line_number - 1,
            item,
            value_without_comment,
        )
        if inline_steps_key:
            return f"{rel}: line {line_number} has an unsupported inline workflow {inline_steps_key} value"
        empty_block_run_key = empty_block_scalar_run_key(lines, line_number - 1, item, value_without_comment)
        if empty_block_run_key:
            return f"{rel}: line {line_number} has an empty workflow {empty_block_run_key} value"
        unsupported_block_scalar_key = unsupported_block_scalar_workflow_string_key(
            lines,
            line_number - 1,
            item,
            value_without_comment,
        )
        if unsupported_block_scalar_key:
            return (
                f"{rel}: line {line_number} has an unsupported block-scalar workflow "
                f"{unsupported_block_scalar_key} value"
            )
        nonscalar_key = nonscalar_workflow_string_value_key(lines, line_number - 1, item, value_without_comment)
        if nonscalar_key:
            return f"{rel}: line {line_number} has a non-scalar workflow {nonscalar_key} value"
        if executable_steps_key(lines, line_number - 1) and value_without_comment:
            return f"{rel}: line {line_number} has an unsupported inline workflow steps value"
        normalized_value_without_comment = strip_yaml_node_prefixes(value_without_comment)
        if is_yaml_block_scalar_marker(normalized_value_without_comment):
            block_scalar_indent = yaml_mapping_key_indent(line)
            indicator = yaml_block_scalar_indent_indicator(normalized_value_without_comment)
            block_scalar_required_indent = block_scalar_indent + indicator if indicator is not None else None
            block_scalar_auto_indent = None
        elif is_invalid_block_scalar_like_value(normalized_value_without_comment):
            return f"{rel}: line {line_number} has an invalid YAML block scalar marker"

    for index, line in enumerate(lines):
        if not executable_steps_key(lines, index):
            continue
        steps_indent = line_indent(line)
        steps_end = block_end_line(lines, index, steps_indent)
        cursor = index + 1
        while cursor < steps_end:
            stripped = lines[cursor].strip()
            if not stripped or stripped.startswith("#"):
                cursor += 1
                continue
            if not stripped.startswith("- "):
                return f"{rel}: line {cursor + 1} has a non-list entry directly under steps"
            item = yaml_item_text_without_comment(lines[cursor])
            normalized_item = strip_yaml_node_prefixes(item)
            if normalized_item.startswith("*"):
                return f"{rel}: line {cursor + 1} has an unsupported alias workflow step value"
            if normalized_item.startswith("["):
                return f"{rel}: line {cursor + 1} has an unsupported inline workflow step value"
            if normalized_item and ":" not in normalized_item and not normalized_item.startswith("{"):
                return f"{rel}: line {cursor + 1} has a non-mapping step entry"
            step_indent = line_indent(lines[cursor])
            step_end = cursor + 1
            while step_end < steps_end:
                step_stripped = lines[step_end].strip()
                if step_stripped and line_indent(lines[step_end]) == step_indent:
                    if step_stripped.startswith("- "):
                        break
                    return f"{rel}: line {step_end + 1} has a non-list entry directly under steps"
                misindented_key = misindented_step_workflow_key(lines, cursor, step_end, step_indent)
                if misindented_key:
                    return (
                        f"{rel}: line {step_end + 1} has a misindented workflow "
                        f"{misindented_key} value"
                    )
                step_end += 1
            cursor = step_end
    return None




def parse_step_snippet(
    lines: list[str],
    start: int,
    end: int,
    inherited_shell: str | None,
    rel: str,
) -> dict[str, Any] | None:
    step_name = ""
    explicit_shell: tuple[int, str] | None = None
    run_line = None
    command = ""
    run_end = start + 1
    step_indent = line_indent(lines[start])
    child_indent = step_indent + 2
    for index in range(start, end):
        direct_key = index == start or line_indent(lines[index]) == child_indent
        if not direct_key:
            continue
        item = strip_yaml_node_prefixes(yaml_item_text(lines[index]))
        flow = split_flow_mapping(item) if index == start else {}
        if flow:
            if "name" in flow:
                step_name = flow["name"]
            if "shell" in flow:
                explicit_shell = (index + 1, flow["shell"])
            if "run" in flow:
                run_line = index
                run_end = index + 1
                command = flow["run"]
        elif item.startswith("name:"):
            step_name = normalize_workflow_scalar(item.split(":", 1)[1])
        elif item.startswith("shell:"):
            shell = normalize_workflow_scalar(item.split(":", 1)[1])
            explicit_shell = (index + 1, shell)
        elif item.startswith("run:"):
            run_line = index
            run_end, command = collect_run_block(lines, index, end)

    if run_line is None:
        return None
    effective_shell = explicit_shell[1] if explicit_shell else (inherited_shell or "unspecified")
    marker_command = command if is_powershell_shell(effective_shell) else command_text_for_marker_scan(command)
    if not is_powershell_shell(effective_shell) and not WORKFLOW_MARKER_RE.search(marker_command):
        return None
    line_start = min(explicit_shell[0], run_line + 1) if explicit_shell else run_line + 1
    line_end = max(run_end, explicit_shell[0]) if explicit_shell else run_end
    return {
        "source_file": rel,
        "step_or_action": step_name or "(unnamed step)",
        "shell": effective_shell,
        "line_start": line_start,
        "line_end": line_end,
        "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest() if command else "",
        "command_preview": command[:240],
    }


def extract_workflow_snippets(repo_root: Path, rel: str) -> list[dict[str, Any]]:
    lines = read_text(repo_root / rel).splitlines()
    snippets: list[dict[str, Any]] = []
    for start, end, inherited_shell in step_blocks(lines):
        snippet = parse_step_snippet(lines, start, end, inherited_shell, rel)
        if snippet is not None:
            snippets.append(snippet)
    return snippets


__all__ = [
    "workflow_yaml_shape_error",
    "parse_step_snippet",
    "extract_workflow_snippets",
]
