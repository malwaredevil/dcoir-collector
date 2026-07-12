#!/usr/bin/env python3
"""YAML scalar, shell, and block parsing helpers for workflow PowerShell inventory."""
from __future__ import annotations

import re



def line_indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def yaml_item_text(line: str) -> str:
    stripped = line.strip()
    return stripped[2:].strip() if stripped.startswith("- ") else stripped


def strip_yaml_node_prefixes(item: str) -> str:
    candidate = item.strip()
    while candidate:
        if candidate.startswith("&"):
            match = re.match(r"&[^\s\[\]\{\},]+(?:\s+|$)", candidate)
            if not match:
                return candidate
            candidate = candidate[match.end():].lstrip()
            continue
        if candidate.startswith("!<"):
            end = candidate.find(">")
            if end == -1:
                return candidate
            following = candidate[end + 1:]
            if following and not following[0].isspace():
                return candidate
            candidate = following.lstrip()
            continue
        if candidate.startswith("!"):
            match = re.match(r"![^\s\[\]\{\},]+(?:\s+|$)", candidate)
            if not match:
                return candidate
            candidate = candidate[match.end():].lstrip()
            continue
        return candidate
    return candidate


def normalize_block_scalar_command(command_lines: list[str], marker: str) -> str:
    if not marker.strip().startswith(">"):
        return "\n".join(command_lines).rstrip()

    folded_lines: list[str] = []
    paragraph: list[str] = []
    for line in command_lines:
        if line == "":
            if paragraph:
                folded_lines.append(" ".join(paragraph))
                paragraph = []
            folded_lines.append("")
        else:
            paragraph.append(line)
    if paragraph:
        folded_lines.append(" ".join(paragraph))
    return "\n".join(folded_lines).rstrip()


def yaml_quote_can_start(value: str, index: int) -> bool:
    prefix = value[:index]
    if not prefix.strip():
        return True
    previous_non_space = prefix.rstrip()[-1]
    return previous_non_space in {"[", "{", ",", ":"}


def is_yaml_block_scalar_marker(value: str) -> bool:
    marker = value.strip()
    if not marker or marker[0] not in {"|", ">"}:
        return False
    chomping = False
    indentation = False
    for character in marker[1:]:
        if character in "+-":
            if chomping:
                return False
            chomping = True
        elif character in "123456789":
            if indentation:
                return False
            indentation = True
        else:
            return False
    return True


def clean_shell_value(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        inner = cleaned[1:-1]
        if cleaned[0] == "'":
            return inner.replace("''", "'")
        return inner
    return cleaned


def shell_line_without_comment(line: str) -> str:
    quote: str | None = None
    index = 0
    while index < len(line):
        character = line[index]
        if quote:
            if character == "\\" and index + 1 < len(line):
                index += 2
                continue
            if character == quote:
                quote = None
            index += 1
            continue
        if character in {"'", '"'}:
            quote = character
        elif character == "#" and (index == 0 or line[index - 1].isspace()):
            return line[:index].rstrip()
        index += 1
    return line


def yaml_mapping_key_indent(line: str) -> int:
    indent = line_indent(line)
    return indent + 2 if line.strip().startswith("- ") else indent


def yaml_key_name(item: str) -> str:
    if ":" not in item:
        return ""
    return clean_shell_value(item.split(":", 1)[0]).casefold()


def previous_parent_index(lines: list[str], index: int) -> int | None:
    current_indent = line_indent(lines[index])
    for candidate in range(index - 1, -1, -1):
        stripped = lines[candidate].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line_indent(lines[candidate]) < current_indent:
            return candidate
    return None


def block_end_line(lines: list[str], start_index: int, block_indent: int, max_end: int | None = None) -> int:
    limit = max_end if max_end is not None else len(lines)
    end_line = start_index + 1
    for index in range(start_index + 1, limit):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            end_line = index + 1
            continue
        indent = line_indent(line)
        if indent <= block_indent:
            break
        end_line = index + 1
    return end_line


def strip_yaml_inline_comment_with_quote(value: str) -> tuple[str, str | None]:
    quote: str | None = None
    index = 0
    while index < len(value):
        character = value[index]
        if quote:
            if quote == "'" and character == "'" and index + 1 < len(value) and value[index + 1] == "'":
                index += 2
                continue
            if quote == '"' and character == "\\" and index + 1 < len(value):
                index += 2
                continue
            if character == quote:
                quote = None
            index += 1
            continue
        if character in {"'", '"'} and yaml_quote_can_start(value, index):
            quote = character
        elif character == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip(), None
        index += 1
    return value.strip(), quote


def yaml_block_scalar_indent_indicator(value: str) -> int | None:
    marker = value.strip()
    if not is_yaml_block_scalar_marker(marker):
        return None
    for character in marker[1:]:
        if character in "123456789":
            return int(character)
    return None


def is_invalid_block_scalar_like_value(value: str) -> bool:
    marker = strip_yaml_node_prefixes(value).strip()
    if not marker or is_yaml_block_scalar_marker(marker):
        return False
    if marker[0] in {"|", ">"}:
        return True
    if len(marker) >= 2 and marker[0] in {"'", '"'} and marker[-1] == marker[0]:
        inner = marker[1:-1].strip()
        return bool(inner) and inner[0] in {"|", ">"}
    return False


def parent_block_start(lines: list[str], index: int) -> int:
    current_indent = line_indent(lines[index])
    for candidate in range(index - 1, -1, -1):
        stripped = lines[candidate].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line_indent(lines[candidate]) < current_indent:
            return candidate
    return 0


def command_text_for_marker_scan(command: str) -> str:
    command_lines: list[str] = []
    for line in command.splitlines():
        if line.strip().startswith("#"):
            continue
        stripped = shell_line_without_comment(line).strip()
        if stripped:
            command_lines.append(stripped)
    return "\n".join(command_lines)


def nested_content_index(lines: list[str], index: int) -> int | None:
    parent_indent = yaml_mapping_key_indent(lines[index])
    for candidate in range(index + 1, len(lines)):
        stripped = lines[candidate].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line_indent(lines[candidate]) <= parent_indent:
            return None
        return candidate
    return None


def strip_yaml_inline_comment(value: str) -> str:
    stripped, _quote = strip_yaml_inline_comment_with_quote(value)
    return stripped


def yaml_unclosed_quote(value: str) -> str | None:
    _stripped, quote = strip_yaml_inline_comment_with_quote(value)
    return quote


def yaml_block_scalar_content_indent(
    lines: list[str],
    start_index: int,
    end_index: int,
    header_indent: int,
    marker: str,
) -> int:
    indicator = yaml_block_scalar_indent_indicator(marker)
    if indicator is not None:
        return header_indent + indicator
    for line in lines[start_index:end_index]:
        if line.strip():
            return line_indent(line)
    return header_indent + 2


def yaml_item_text_without_comment(line: str) -> str:
    return strip_yaml_inline_comment(yaml_item_text(line))


def normalize_workflow_scalar(value: str) -> str:
    return clean_shell_value(strip_yaml_node_prefixes(strip_yaml_inline_comment(value))).strip()


def workflow_scalar_is_alias(value: str) -> bool:
    return strip_yaml_node_prefixes(strip_yaml_inline_comment(value)).startswith("*")


def unquoted_flow_collection_value(value: str) -> bool:
    stripped = strip_yaml_node_prefixes(strip_yaml_inline_comment(value))
    if len(stripped) < 2 or stripped[0] in {"'", '"'}:
        return False
    return (stripped[0] == "[" and stripped[-1] == "]") or (stripped[0] == "{" and stripped[-1] == "}")


def flow_mapping_pieces(item: str) -> list[str] | None:
    stripped = strip_yaml_node_prefixes(strip_yaml_inline_comment(item))
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return None
    content = stripped[1:-1]
    pieces: list[str] = []
    current: list[str] = []
    quote: str | None = None
    depth = 0
    index = 0
    while index < len(content):
        character = content[index]
        if quote:
            current.append(character)
            if quote == "'" and character == "'" and index + 1 < len(content) and content[index + 1] == "'":
                current.append(content[index + 1])
                index += 2
                continue
            if quote == '"' and character == "\\" and index + 1 < len(content):
                current.append(content[index + 1])
                index += 2
                continue
            if character == quote:
                quote = None
            index += 1
            continue
        if character in {"'", '"'} and yaml_quote_can_start(content, index):
            quote = character
            current.append(character)
        elif character in "[{":
            depth += 1
            current.append(character)
        elif character in "]}":
            depth = max(0, depth - 1)
            current.append(character)
        elif character == "," and depth == 0:
            pieces.append("".join(current).strip())
            current = []
        else:
            current.append(character)
        index += 1
    if current:
        pieces.append("".join(current).strip())
    return pieces


def flow_collection_shape_error(rel: str, line_number: int, item: str, value_without_comment: str) -> str | None:
    candidate = strip_yaml_node_prefixes(strip_yaml_inline_comment(item))
    if not candidate.startswith(("{", "[")):
        candidate = strip_yaml_node_prefixes(value_without_comment).strip()
    if not candidate or candidate[0] not in {"{", "["} or candidate[0] in {"'", '"'}:
        return None

    pairs = {"[": "]", "{": "}"}
    closing = {"]", "}"}
    stack: list[tuple[str, int]] = []
    quote: str | None = None
    index = 0
    while index < len(candidate):
        character = candidate[index]
        if quote:
            if quote == "'" and character == "'" and index + 1 < len(candidate) and candidate[index + 1] == "'":
                index += 2
                continue
            if quote == '"' and character == "\\" and index + 1 < len(candidate):
                index += 2
                continue
            if character == quote:
                quote = None
            index += 1
            continue
        if character in {"'", '"'} and yaml_quote_can_start(candidate, index):
            quote = character
        elif character in pairs:
            stack.append((character, line_number))
        elif character in closing:
            if not stack or pairs[stack[-1][0]] != character:
                return f"{rel}: line {line_number} has an unmatched {character!r}"
            stack.pop()
        index += 1
    if stack:
        opener, opener_line = stack[-1]
        return f"{rel}: line {opener_line} has an unclosed {opener!r}"
    return None
