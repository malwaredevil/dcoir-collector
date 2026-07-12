#!/usr/bin/env python3
"""PowerShell parsing helpers for custom check detection."""
from __future__ import annotations

import re

from powershell_rule_risk_fixtures_powershell import (
    context_has_skip_success_trigger,
    executable_here_string_start,
    line_assignment_value,
    line_has_assignment_value,
    line_has_executable_exit_zero,
    line_in_result_object,
    line_without_powershell_comments_or_strings,
    line_without_powershell_line_comment,
    local_failure_action,
    local_result_context,
    local_result_context_bounds,
    parse_powershell_scalar_value,
    position_in_spans,
    powershell_code_lines,
    powershell_code_lines_preserving_positions,
    pscustomobject_end_index,
    pscustomobject_start_column,
    result_object_bounds_for_index,
    string_spans,
    unquoted_token_index,
)

_REEXPORTED_POWERSHELL_HELPERS = (
    context_has_skip_success_trigger,
    executable_here_string_start,
    line_assignment_value,
    line_has_assignment_value,
    line_has_executable_exit_zero,
    line_in_result_object,
    line_without_powershell_comments_or_strings,
    line_without_powershell_line_comment,
    local_failure_action,
    local_result_context,
    local_result_context_bounds,
    parse_powershell_scalar_value,
    position_in_spans,
    powershell_code_lines,
    powershell_code_lines_preserving_positions,
    pscustomobject_end_index,
    pscustomobject_start_column,
    result_object_bounds_for_index,
    string_spans,
    unquoted_token_index,
)


def line_number_for(text: str, pattern: str, flags: int = re.IGNORECASE | re.MULTILINE) -> int | None:
    match = re.search(pattern, text, flags)
    if not match:
        return None
    return text[: match.start()].count("\n") + 1


def line_window(lines: list[str], index: int, before: int = 0, after: int = 4) -> str:
    start = max(0, index - before)
    end = min(len(lines), index + after + 1)
    return "\n".join(lines[start:end])


def code_without_full_line_comments(text: str) -> str:
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            kept.append("")
        else:
            kept.append(line)
    return "\n".join(kept)


__all__ = tuple(helper.__name__ for helper in _REEXPORTED_POWERSHELL_HELPERS) + (
    "line_number_for",
    "line_window",
    "code_without_full_line_comments",
)
