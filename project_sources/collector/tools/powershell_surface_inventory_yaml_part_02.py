#!/usr/bin/env python3
"""YAML scalar, shell, and block parsing helpers for workflow PowerShell inventory."""
from __future__ import annotations

import re
import shlex

from powershell_surface_inventory_common import FLOW_STEP_KEYS

from powershell_surface_inventory_yaml_part_01 import (
    line_indent,
    yaml_item_text,
    yaml_item_text_without_comment,
    strip_yaml_node_prefixes,
    normalize_workflow_scalar,
    workflow_scalar_is_alias,
    yaml_mapping_key_indent,
    yaml_key_name,
    previous_parent_index,
    unquoted_flow_collection_value,
    flow_mapping_pieces,
    nested_content_index,
    block_end_line,
    normalize_block_scalar_command,
    strip_yaml_inline_comment,
    is_yaml_block_scalar_marker,
    yaml_block_scalar_content_indent,
    clean_shell_value,
)

def block_scalar_has_nonblank_content(lines: list[str], index: int, marker: str) -> bool:
    indent = yaml_mapping_key_indent(lines[index])
    end_line = block_end_line(lines, index, indent)
    content_indent = yaml_block_scalar_content_indent(lines, index + 1, end_line, indent, marker)
    for follow in lines[index + 1:end_line]:
        if not follow.strip():
            continue
        content = follow[content_indent:] if len(follow) >= content_indent else follow.strip()
        if content.strip():
            return True
    return False


def has_block_collection_child(lines: list[str], index: int) -> bool:
    child = nested_content_index(lines, index)
    if child is None:
        return False
    child_item = yaml_item_text(lines[child])
    child_value = child_item.split(":", 1)[1].strip() if ":" in child_item else ""
    if lines[child].strip().startswith("- "):
        return True
    if child_item.startswith(("{", "[")):
        return True
    if ":" in child_item and not is_yaml_block_scalar_marker(strip_yaml_inline_comment(child_value)):
        return True
    return False


def cleaned_workflow_string(value: str) -> str:
    return normalize_workflow_scalar(value)


def direct_child_key(parent_line: str, child_line: str, key_name: str) -> bool:
    return line_indent(child_line) == line_indent(parent_line) + 2 and yaml_key_name(
        yaml_item_text_without_comment(child_line)
    ) == key_name


def defaults_run_shell_key(lines: list[str], index: int) -> bool:
    parent = previous_parent_index(lines, index)
    if parent is None or not yaml_item_text_without_comment(lines[parent]).startswith("run:"):
        return False
    grandparent = previous_parent_index(lines, parent)
    return grandparent is not None and yaml_item_text_without_comment(lines[grandparent]).startswith("defaults:")


def defaults_run_mapping_key(lines: list[str], index: int) -> bool:
    parent = previous_parent_index(lines, index)
    return parent is not None and yaml_item_text_without_comment(lines[parent]).startswith("defaults:")


def flow_mapping_fragment_error(rel: str, line_number: int, item: str, value_without_comment: str) -> str | None:
    candidate = strip_yaml_node_prefixes(strip_yaml_inline_comment(item))
    if not candidate.startswith("{"):
        candidate = strip_yaml_node_prefixes(value_without_comment).strip()
    if not candidate or candidate[0] != "{" or candidate[0] in {"'", '"'}:
        return None

    pieces = flow_mapping_pieces(candidate)
    if pieces is None:
        return None
    for piece in pieces:
        if piece and ":" not in piece:
            return f"{rel}: line {line_number} has an unsupported flow mapping fragment"
    return None


def unsupported_workflow_run_value(value: str) -> bool:
    return workflow_scalar_is_alias(value) or unquoted_flow_collection_value(value)


def collect_run_block(lines: list[str], run_index: int, max_end: int | None = None) -> tuple[int, str]:
    line = lines[run_index]
    indent = yaml_mapping_key_indent(line)
    after_colon = line.split(":", 1)[1].strip() if ":" in line else ""
    block_marker = strip_yaml_node_prefixes(strip_yaml_inline_comment(after_colon))
    if after_colon and not is_yaml_block_scalar_marker(block_marker):
        return run_index + 1, normalize_workflow_scalar(block_marker)
    end_line = block_end_line(lines, run_index, indent, max_end)
    content_indent = yaml_block_scalar_content_indent(lines, run_index + 1, end_line, indent, block_marker)
    command_lines: list[str] = []
    for follow in lines[run_index + 1:end_line]:
        if not follow.strip():
            command_lines.append("")
        else:
            command_lines.append(follow[content_indent:] if len(follow) >= content_indent else follow.strip())
    return end_line, normalize_block_scalar_command(command_lines, block_marker)


def split_flow_mapping(item: str) -> dict[str, str]:
    pieces = flow_mapping_pieces(item)
    if pieces is None:
        return {}

    mapping: dict[str, str] = {}
    for piece in pieces:
        if ":" not in piece:
            continue
        key, value = piece.split(":", 1)
        key = clean_shell_value(key).casefold()
        if key:
            mapping[key] = normalize_workflow_scalar(value)
    return mapping


def shell_executable(value: str) -> str:
    cleaned = normalize_workflow_scalar(value)
    if not cleaned:
        return ""
    first_token = cleaned.split()[0]
    if first_token[0] not in {"'", '"'} and "\\" in first_token:
        return re.split(r"[\\/]+", first_token)[-1].casefold()
    try:
        parts = shlex.split(cleaned)
    except ValueError:
        parts = cleaned.split()
    if not parts:
        return ""
    return re.split(r"[\\/]+", parts[0])[-1].casefold()


def step_line_has_ancestor_key(
    lines: list[str],
    step_start: int,
    index: int,
    ancestor_key: str,
    ancestor_indent: int,
) -> bool:
    for candidate in range(index - 1, step_start, -1):
        stripped = lines[candidate].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line_indent(lines[candidate]) != ancestor_indent:
            continue
        return yaml_key_name(yaml_item_text_without_comment(lines[candidate])) == ancestor_key
    return False


def step_child_ancestor_key(lines: list[str], step_start: int, index: int, child_indent: int) -> str | None:
    for candidate in range(index - 1, step_start, -1):
        stripped = lines[candidate].strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = line_indent(lines[candidate])
        if indent < child_indent:
            return None
        if indent == child_indent:
            return yaml_key_name(yaml_item_text_without_comment(lines[candidate]))
    return None


def line_is_within_step_run_block_scalar(
    lines: list[str],
    step_start: int,
    index: int,
    child_indent: int,
) -> bool:
    for candidate in range(index - 1, step_start, -1):
        stripped = lines[candidate].strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = line_indent(lines[candidate])
        if indent < child_indent:
            return False
        if indent != child_indent:
            continue
        item = yaml_item_text_without_comment(lines[candidate])
        if yaml_key_name(item) != "run":
            return False
        value = item.split(":", 1)[1].strip() if ":" in item else ""
        return is_yaml_block_scalar_marker(strip_yaml_node_prefixes(strip_yaml_inline_comment(value)))
    return False


def empty_workflow_string(value: str) -> bool:
    return cleaned_workflow_string(value) == ""


def executable_steps_key(lines: list[str], index: int) -> bool:
    item = yaml_item_text_without_comment(lines[index])
    if yaml_key_name(item) != "steps":
        return False

    parent = previous_parent_index(lines, index)
    if parent is None:
        return False
    parent_item = yaml_item_text_without_comment(lines[parent])

    if (
        line_indent(lines[parent]) == 0
        and yaml_key_name(parent_item) == "runs"
        and direct_child_key(lines[parent], lines[index], "steps")
    ):
        return True

    grandparent = previous_parent_index(lines, parent)
    return (
        grandparent is not None
        and line_indent(lines[grandparent]) == 0
        and yaml_key_name(yaml_item_text_without_comment(lines[grandparent])) == "jobs"
        and direct_child_key(lines[parent], lines[index], "steps")
    )


def unsupported_workflow_shell_value(value: str) -> bool:
    cleaned = cleaned_workflow_string(value)
    return (
        cleaned == ""
        or workflow_scalar_is_alias(value)
        or "${{" in cleaned
        or unquoted_flow_collection_value(value)
        or is_yaml_block_scalar_marker(cleaned)
    )


def flow_mapping_has_direct_key(text: str, key: str) -> bool:
    return key in split_flow_mapping(text)


def is_powershell_shell(value: str) -> bool:
    return shell_executable(value) in {"pwsh", "pwsh.exe", "powershell", "powershell.exe"}


def inline_shell_value(text: str) -> str | None:
    mapping = split_flow_mapping(text)
    if not mapping:
        return None
    if "shell" in mapping:
        return mapping["shell"]
    run_value = mapping.get("run")
    if not run_value:
        return None
    return split_flow_mapping(run_value).get("shell")


def misindented_step_workflow_key(
    lines: list[str],
    step_start: int,
    index: int,
    step_indent: int,
) -> str | None:
    if index <= step_start or index >= len(lines):
        return None
    stripped = lines[index].strip()
    if not stripped or stripped.startswith("#"):
        return None
    indent = line_indent(lines[index])
    child_indent = step_indent + 2
    if indent <= child_indent:
        return None
    key = yaml_key_name(yaml_item_text_without_comment(lines[index]))
    if key not in FLOW_STEP_KEYS:
        return None
    ancestor_key = step_child_ancestor_key(lines, step_start, index, child_indent)
    if ancestor_key and ancestor_key not in FLOW_STEP_KEYS:
        return None
    if step_line_has_ancestor_key(lines, step_start, index, "env", child_indent):
        return None
    if step_line_has_ancestor_key(lines, step_start, index, "with", child_indent):
        return None
    if line_is_within_step_run_block_scalar(lines, step_start, index, child_indent):
        return None
    return key


def unsupported_inline_executable_steps_key(
    lines: list[str],
    index: int,
    item: str,
    value_without_comment: str,
) -> str | None:
    normalized_value = strip_yaml_node_prefixes(value_without_comment)
    if not normalized_value.startswith("{"):
        return None

    key = yaml_key_name(item)
    if (
        key == "runs"
        and line_indent(lines[index]) == 0
        and flow_mapping_has_direct_key(normalized_value, "steps")
    ):
        return "runs.steps"

    if key == "jobs" and line_indent(lines[index]) == 0:
        for job_value in split_flow_mapping(normalized_value).values():
            if flow_mapping_has_direct_key(job_value, "steps"):
                return "jobs.steps"

    parent = previous_parent_index(lines, index)
    if parent is None:
        return None
    parent_item = yaml_item_text_without_comment(lines[parent])
    if (
        line_indent(lines[parent]) == 0
        and yaml_key_name(parent_item) == "jobs"
        and line_indent(lines[index]) == line_indent(lines[parent]) + 2
        and flow_mapping_has_direct_key(normalized_value, "steps")
    ):
        return "jobs.steps"
    return None


def defaults_inline_shell(item: str) -> str | None:
    if ":" not in item:
        return None
    value = item.split(":", 1)[1].strip()
    if not value:
        return None
    return inline_shell_value(value)


def run_inline_shell(item: str) -> str | None:
    if ":" not in item:
        return None
    value = item.split(":", 1)[1].strip()
    if not value:
        return None
    return inline_shell_value(value)
