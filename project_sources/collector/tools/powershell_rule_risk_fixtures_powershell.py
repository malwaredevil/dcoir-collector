#!/usr/bin/env python3
"""PowerShell lexical helpers for rule-risk fixture detection."""
from __future__ import annotations

import re

def line_number_for(text: str, pattern: str) -> int | None:
    compiled = re.compile(pattern, re.IGNORECASE)
    for line_number, line in enumerate(text.splitlines(), start=1):
        if compiled.search(line):
            return line_number
    return None

def line_without_powershell_comments_or_strings(line: str) -> str:
    chars: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(line):
        char = line[index]
        if quote is not None:
            chars.append(" ")
            if quote == "'" and char == "'" and index + 1 < len(line) and line[index + 1] == "'":
                chars.append(" ")
                index += 2
                continue
            if quote == '"' and char == "`" and index + 1 < len(line):
                chars.append(" ")
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char == "#":
            break
        if char in {"'", '"'}:
            quote = char
            chars.append(" ")
            index += 1
            continue
        chars.append(char)
        index += 1
    return "".join(chars)

def line_without_powershell_line_comment(line: str) -> str:
    quote: str | None = None
    index = 0
    while index < len(line):
        char = line[index]
        if quote is not None:
            if quote == "'" and char == "'" and index + 1 < len(line) and line[index + 1] == "'":
                index += 2
                continue
            if quote == '"' and char == "`" and index + 1 < len(line):
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char == "#" and not (index > 0 and line[index - 1] == "<"):
            return line[:index]
        if char in {"'", '"'}:
            quote = char
        index += 1
    return line

def unquoted_token_index(line: str, token: str, start: int = 0) -> int:
    spans = string_spans(line)
    position = line.find(token, start)
    while position != -1:
        if not position_in_spans(position, spans):
            return position
        position = line.find(token, position + len(token))
    return -1

def executable_here_string_start(line: str) -> re.Match[str] | None:
    code = line_without_powershell_line_comment(line)
    here_start = re.search(r"@(['\"])\s*$", code)
    if here_start and not position_in_spans(here_start.start(), string_spans(code)):
        return here_start
    return None

def powershell_code_lines_preserving_positions(lines: list[str]) -> list[str]:
    code_lines: list[str] = []
    in_block_comment = False
    here_string_quote: str | None = None
    for raw_line in lines:
        line = raw_line
        if here_string_quote is not None:
            if re.match(rf"^\s*{re.escape(here_string_quote)}@\s*$", line):
                here_string_quote = None
            code_lines.append("")
            continue
        if in_block_comment:
            end = line.find("#>")
            if end == -1:
                code_lines.append("")
                continue
            line = " " * (end + 2) + line[end + 2 :]
            in_block_comment = False
        while True:
            comment_ready_line = line_without_powershell_line_comment(line)
            start = unquoted_token_index(comment_ready_line, "<#")
            if start == -1:
                break
            end = line.find("#>", start + 2)
            if end == -1:
                line = line[:start]
                in_block_comment = True
                break
            line = line[:start] + " " * (end + 2 - start) + line[end + 2 :]
        here_start = executable_here_string_start(line)
        if here_start:
            here_string_quote = here_start.group(1)
            line = line[: here_start.start()]
        code_lines.append(line_without_powershell_line_comment(line))
    return code_lines

def powershell_code_lines(context: str) -> list[str]:
    code_lines: list[str] = []
    in_block_comment = False
    here_string_quote: str | None = None
    for raw_line in context.splitlines():
        line = raw_line
        if here_string_quote is not None:
            if re.match(rf"^\s*{re.escape(here_string_quote)}@\s*$", line):
                here_string_quote = None
            continue
        if in_block_comment:
            end = line.find("#>")
            if end == -1:
                continue
            line = line[end + 2 :]
            in_block_comment = False
        while True:
            comment_ready_line = line_without_powershell_line_comment(line)
            start = unquoted_token_index(comment_ready_line, "<#")
            if start == -1:
                break
            end = line.find("#>", start + 2)
            if end == -1:
                line = line[:start]
                in_block_comment = True
                break
            line = line[:start] + " " * (end + 2 - start) + line[end + 2 :]
        here_start = executable_here_string_start(line)
        if here_start:
            here_string_quote = here_start.group(1)
            line = line[: here_start.start()]
        code_lines.append(line_without_powershell_line_comment(line))
    return code_lines

def string_spans(line: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    quote: str | None = None
    start = 0
    index = 0
    while index < len(line):
        char = line[index]
        if quote is None:
            if char in {"'", '"'}:
                quote = char
                start = index
            index += 1
            continue
        if quote == "'" and char == "'" and index + 1 < len(line) and line[index + 1] == "'":
            index += 2
            continue
        if quote == '"' and char == "`" and index + 1 < len(line):
            index += 2
            continue
        if char == quote:
            spans.append((start, index + 1))
            quote = None
        index += 1
    if quote is not None:
        spans.append((start, len(line)))
    return spans

def position_in_spans(position: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in spans)

def parse_powershell_scalar_value(line: str, start: int) -> tuple[str, int] | None:
    index = start
    while index < len(line) and line[index].isspace():
        index += 1
    if index >= len(line):
        return None
    quote = line[index] if line[index] in {"'", '"'} else None
    if quote is None:
        end = index
        while end < len(line) and not line[end].isspace() and line[end] not in ";|})]":
            end += 1
        return line[index:end], end
    index += 1
    value_chars: list[str] = []
    while index < len(line):
        char = line[index]
        if quote == "'" and char == "'" and index + 1 < len(line) and line[index + 1] == "'":
            value_chars.append("'")
            index += 2
            continue
        if quote == '"' and char == "`" and index + 1 < len(line):
            value_chars.append(line[index + 1])
            index += 2
            continue
        if char == quote:
            return "".join(value_chars), index + 1
        value_chars.append(char)
        index += 1
    return "".join(value_chars), index

def line_assignment_value(line: str, names: set[str]) -> tuple[str, str] | None:
    spans = string_spans(line)
    name_re = re.compile(r"\b(" + "|".join(re.escape(name) for name in sorted(names)) + r")\b", re.IGNORECASE)
    for match in name_re.finditer(line):
        if position_in_spans(match.start(), spans):
            continue
        cursor = match.end()
        while cursor < len(line) and line[cursor].isspace():
            cursor += 1
        if cursor >= len(line) or line[cursor] != "=":
            continue
        parsed = parse_powershell_scalar_value(line, cursor + 1)
        if parsed is not None:
            return match.group(1).casefold(), parsed[0]
    return None

def line_has_assignment_value(line: str, expected: dict[str, set[str]]) -> bool:
    assignment = line_assignment_value(line, set(expected))
    if assignment is None:
        return False
    name, value = assignment
    return value.casefold() in {candidate.casefold() for candidate in expected[name]}

def line_has_executable_exit_zero(line: str) -> bool:
    code = line_without_powershell_comments_or_strings(line)
    return re.search(r"(?:^\s*|[;{}]\s*)exit\s+0\b", code, re.IGNORECASE) is not None

def pscustomobject_start_column(line: str) -> int | None:
    code = line_without_powershell_comments_or_strings(line)
    match = re.search(r"\[pscustomobject\]\s*@\s*\{", code, re.IGNORECASE)
    return match.start() if match else None

def pscustomobject_end_index(code_lines: list[str], start_index: int) -> int | None:
    start_column = pscustomobject_start_column(code_lines[start_index])
    if start_column is None:
        return None
    depth = 0
    for cursor in range(start_index, len(code_lines)):
        code = line_without_powershell_comments_or_strings(code_lines[cursor])
        scan = code[start_column:] if cursor == start_index else code
        for char in scan:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return cursor
    return None

def result_object_bounds_for_index(code_lines: list[str], index: int) -> tuple[int, int] | None:
    for cursor in range(index, -1, -1):
        if pscustomobject_start_column(code_lines[cursor]) is None:
            continue
        object_end = pscustomobject_end_index(code_lines, cursor)
        if object_end is None:
            return cursor, index
        if index <= object_end:
            return cursor, object_end
    return None

def line_in_result_object(code_lines: list[str], index: int) -> bool:
    return result_object_bounds_for_index(code_lines, index) is not None

def local_result_context_bounds(lines: list[str], index: int, after: int = 4) -> tuple[int, int]:
    code_lines = powershell_code_lines_preserving_positions(lines)
    result_bounds = result_object_bounds_for_index(code_lines, index)
    start, end = result_bounds if result_bounds is not None else (index, index)

    for cursor in range(end + 1, min(len(lines), end + after + 1)):
        stripped = line_without_powershell_comments_or_strings(code_lines[cursor]).strip()
        if not stripped:
            break
        if re.search(r"\[pscustomobject\]\s*@\s*\{|^\s*(?:function|if|elseif|else|switch|foreach|for|while)\b", stripped, re.IGNORECASE):
            break
        end = cursor
    return start, end

def local_result_context(lines: list[str], index: int, after: int = 4) -> str:
    start, end = local_result_context_bounds(lines, index, after=after)
    return "\n".join(lines[start : end + 1])

def local_failure_action(context: str) -> bool:
    action_re = re.compile(r"(?:^\s*|[;{}]\s*)(?:throw\b|exit\s+[1-9]\d*\b|return\s+\$false\b)", re.IGNORECASE)
    return any(action_re.search(line_without_powershell_comments_or_strings(line)) for line in powershell_code_lines(context))

def context_has_skip_success_trigger(context: str) -> bool:
    code_lines = powershell_code_lines_preserving_positions(context.splitlines())
    return any(
        line_has_assignment_value(line, {"validation": {"success", "pass", "passed", "ok"}, "status": {"success", "pass", "passed", "ok"}})
        or line_has_executable_exit_zero(line)
        for line in code_lines
    )
