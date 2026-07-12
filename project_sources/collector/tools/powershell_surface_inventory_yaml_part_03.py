#!/usr/bin/env python3
"""YAML scalar, shell, and block parsing helpers for workflow PowerShell inventory."""
from __future__ import annotations


from powershell_surface_inventory_common import FLOW_STEP_KEYS

from powershell_surface_inventory_yaml_part_01 import (
    line_indent,
    yaml_item_text_without_comment,
    strip_yaml_node_prefixes,
    normalize_workflow_scalar,
    yaml_key_name,
    nested_content_index,
    block_end_line,
    strip_yaml_inline_comment,
    is_yaml_block_scalar_marker,
    parent_block_start,
)
from powershell_surface_inventory_yaml_part_02 import (
    empty_workflow_string,
    executable_steps_key,
    defaults_run_shell_key,
    defaults_run_mapping_key,
    unsupported_workflow_shell_value,
    unsupported_workflow_run_value,
    block_scalar_has_nonblank_content,
    has_block_collection_child,
    split_flow_mapping,
    inline_shell_value,
    defaults_inline_shell,
    run_inline_shell,
)

def direct_defaults_shell(lines: list[str], defaults_index: int, parent_end: int) -> str | None:
    defaults_item = yaml_item_text_without_comment(lines[defaults_index])
    inline = defaults_inline_shell(defaults_item)
    if inline:
        return inline

    defaults_indent = line_indent(lines[defaults_index])
    defaults_end = block_end_line(lines, defaults_index, defaults_indent, parent_end)
    run_index = None
    run_indent = 0
    for candidate in range(defaults_index + 1, defaults_end):
        if line_indent(lines[candidate]) != defaults_indent + 2:
            continue
        candidate_item = yaml_item_text_without_comment(lines[candidate])
        if candidate_item.startswith("run:"):
            inline_run_shell = run_inline_shell(candidate_item)
            if inline_run_shell:
                return inline_run_shell
            if candidate_item == "run:":
                run_index = candidate
                run_indent = line_indent(lines[candidate])
                break
    if run_index is None:
        return None

    run_end = block_end_line(lines, run_index, run_indent, defaults_end)
    for candidate in range(run_index + 1, run_end):
        if line_indent(lines[candidate]) != run_indent + 2:
            continue
        candidate_item = yaml_item_text_without_comment(lines[candidate])
        if candidate_item.startswith("shell:"):
            return normalize_workflow_scalar(candidate_item.split(":", 1)[1])
    return None


def workflow_default_shell(lines: list[str]) -> str | None:
    for index in range(0, len(lines)):
        item = yaml_item_text_without_comment(lines[index])
        if line_indent(lines[index]) != 0 or not item.startswith("defaults:"):
            continue
        shell = direct_defaults_shell(lines, index, block_end_line(lines, index, 0))
        if shell:
            return shell
    return None


def job_default_shell(lines: list[str], job_start: int, job_end: int) -> str | None:
    job_indent = line_indent(lines[job_start])
    for index in range(job_start + 1, job_end):
        item = yaml_item_text_without_comment(lines[index])
        if line_indent(lines[index]) != job_indent + 2 or not item.startswith("defaults:"):
            continue
        shell = direct_defaults_shell(lines, index, job_end)
        if shell:
            return shell
    return None


def default_shell_for_steps(lines: list[str], steps_index: int) -> str | None:
    job_start = parent_block_start(lines, steps_index)
    job_end = block_end_line(lines, job_start, line_indent(lines[job_start]))
    return job_default_shell(lines, job_start, job_end) or workflow_default_shell(lines)


def step_blocks(lines: list[str]) -> list[tuple[int, int, str | None]]:
    blocks: list[tuple[int, int, str | None]] = []
    for index, line in enumerate(lines):
        if not executable_steps_key(lines, index):
            continue
        steps_indent = line_indent(line)
        steps_end = block_end_line(lines, index, steps_indent)
        inherited_shell = default_shell_for_steps(lines, index)
        cursor = index + 1
        while cursor < steps_end:
            stripped = lines[cursor].strip()
            if not stripped or stripped.startswith("#"):
                cursor += 1
                continue
            if stripped.startswith("- "):
                step_indent = line_indent(lines[cursor])
                end = cursor + 1
                while end < steps_end:
                    end_stripped = lines[end].strip()
                    if end_stripped and line_indent(lines[end]) == step_indent and end_stripped.startswith("- "):
                        break
                    end += 1
                blocks.append((cursor, end, inherited_shell))
                cursor = end
                continue
            cursor += 1
    return blocks


def direct_step_mapping_key(lines: list[str], index: int) -> bool:
    for start, end, _inherited_shell in step_blocks(lines):
        if start <= index < end:
            step_indent = line_indent(lines[start])
            return index == start or line_indent(lines[index]) == step_indent + 2
    return False


def unsupported_flow_step_mapping_key(
    lines: list[str],
    index: int,
    item: str,
) -> str | None:
    if not direct_step_mapping_key(lines, index):
        return None
    candidate = strip_yaml_node_prefixes(strip_yaml_inline_comment(item))
    if not candidate.startswith("{"):
        return None

    for key in split_flow_mapping(candidate):
        if key not in FLOW_STEP_KEYS:
            return key
    return None


def empty_block_scalar_run_key(
    lines: list[str],
    index: int,
    item: str,
    value_without_comment: str,
) -> str | None:
    marker = strip_yaml_node_prefixes(value_without_comment)
    if (
        yaml_key_name(item) == "run"
        and direct_step_mapping_key(lines, index)
        and is_yaml_block_scalar_marker(marker)
        and not block_scalar_has_nonblank_content(lines, index, marker)
    ):
        return "run"
    return None


def unsupported_block_scalar_workflow_string_key(
    lines: list[str],
    index: int,
    item: str,
    value_without_comment: str,
) -> str | None:
    if not is_yaml_block_scalar_marker(strip_yaml_node_prefixes(value_without_comment)):
        return None
    key = yaml_key_name(item)
    if key == "shell" and direct_step_mapping_key(lines, index):
        return "shell"
    if key == "shell" and defaults_run_shell_key(lines, index):
        return "defaults.run.shell"
    return None


def nonscalar_workflow_string_value_key(
    lines: list[str],
    index: int,
    item: str,
    value_without_comment: str,
) -> str | None:
    flow = split_flow_mapping(item)
    if flow and direct_step_mapping_key(lines, index):
        if "run" in flow:
            if empty_workflow_string(flow["run"]) or unsupported_workflow_run_value(flow["run"]):
                return "run"
        if "shell" in flow and unsupported_workflow_shell_value(flow["shell"]):
            return "shell"

    key = yaml_key_name(item)
    if key == "run" and direct_step_mapping_key(lines, index):
        if unsupported_workflow_run_value(value_without_comment):
            return "run"
        if empty_workflow_string(value_without_comment):
            if (
                value_without_comment
                or has_block_collection_child(lines, index)
                or nested_content_index(lines, index) is None
            ):
                return "run"
    if key == "shell" and direct_step_mapping_key(lines, index):
        if unsupported_workflow_shell_value(value_without_comment):
            return "shell"
    if key == "shell" and defaults_run_shell_key(lines, index):
        if unsupported_workflow_shell_value(value_without_comment):
            return "defaults.run.shell"
    if key == "defaults":
        inline_shell = inline_shell_value(value_without_comment)
        if inline_shell is not None:
            if unsupported_workflow_shell_value(inline_shell):
                return "defaults.run.shell"
    if key == "run" and defaults_run_mapping_key(lines, index):
        inline_shell = inline_shell_value(value_without_comment)
        if inline_shell is not None:
            if unsupported_workflow_shell_value(inline_shell):
                return "defaults.run.shell"
    return None
