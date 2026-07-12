#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List

EVENT_TEXT_REVIEW_REL = 'project_sources/collector/source/parts/DCOIR_Collector.03B_Enrich_Actions_Review.ps1'
RETRIEVAL_ACTIONS_REL = 'project_sources/collector/source/parts/DCOIR_Collector.03C_Enrich_Actions_Retrieval.ps1'
EVENT_WINDOW_OVERRIDES_REL = 'project_sources/collector/source/parts/DCOIR_Collector.04C_Explicit_Event_Window_Overrides.ps1'
DIAGNOSTIC_CONTEXT_RELS = (
    'project_sources/collector/source/parts/DCOIR_Collector.04E1_Diagnostic_Context_Overrides.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.04E2_Diagnostic_Context_Overrides.ps1',
    'project_sources/collector/source/parts/DCOIR_Collector.04E3_Event_Text.ps1',
)
DIAGNOSTIC_CONTEXT_REL = DIAGNOSTIC_CONTEXT_RELS[0]
PR186_FIXES_REL = 'project_sources/collector/source/parts/DCOIR_Collector.04F2_PR186_Review_Fixes.ps1'
REPORT_NAME = 'validate_event_text_query_bound_policy_report.json'
COUNT_CAP_PARAMETER_NAMES = ('Take', 'MaxEvents')


def read_text(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='ignore') if path.exists() else ''


def read_combined_text(source_dir: Path, relative_paths: Iterable[str]) -> str:
    return '\n'.join(read_text(source_dir / rel_path) for rel_path in relative_paths)


def extract_parenthesized_text(text: str, open_paren_index: int) -> str:
    if open_paren_index < 0 or open_paren_index >= len(text) or text[open_paren_index] != '(':
        return ''
    depth = 0
    for index in range(open_paren_index, len(text)):
        char = text[index]
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                return text[open_paren_index:index + 1]
    return ''


def extract_function_body(text: str, function_name: str) -> str:
    match = re.search(r'^\s*function\s+' + re.escape(function_name) + r'\b', text, re.MULTILINE)
    if not match:
        return ''
    brace_start = text.find('{', match.end())
    if brace_start == -1:
        return ''
    depth = 0
    for index in range(brace_start, len(text)):
        char = text[index]
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[brace_start:index + 1]
    return text[brace_start:]


def extract_function_param_block(function_body: str) -> str:
    match = re.search(r'^\s*param\s*\(', function_body, re.MULTILINE | re.IGNORECASE)
    if not match:
        return ''
    open_paren = function_body.find('(', match.start())
    params = extract_parenthesized_text(function_body, open_paren)
    return function_body[match.start():open_paren] + params if params else ''


def extract_quoted_switch_case_bodies(text: str, case_name: str) -> List[str]:
    pattern = re.compile(r'^\s*"' + re.escape(case_name) + r'"\s*{', re.MULTILINE)
    bodies: List[str] = []
    for match in pattern.finditer(text):
        brace_start = text.find('{', match.start())
        if brace_start == -1:
            continue
        depth = 0
        for index in range(brace_start, len(text)):
            char = text[index]
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    bodies.append(text[brace_start:index + 1])
                    break
    return bodies


def mask_powershell_strings_and_comments(text: str, mask_backtick_escapes: bool = False) -> str:
    chars: List[str] = []
    index = 0
    quote = ''
    while index < len(text):
        char = text[index]
        if quote:
            if char == '`':
                chars.append(' ')
                if index + 1 < len(text):
                    chars.append(text[index + 1] if text[index + 1] in '\r\n' else ' ')
                    index += 2
                else:
                    index += 1
                continue
            if char == quote:
                if index + 1 < len(text) and text[index + 1] == quote:
                    chars.extend('  ')
                    index += 2
                    continue
                quote = ''
            chars.append(char if char in '\r\n' else ' ')
            index += 1
            continue
        if text.startswith('<#', index):
            chars.extend('  ')
            index += 2
            while index < len(text):
                if text.startswith('#>', index):
                    chars.extend('  ')
                    index += 2
                    break
                chars.append(text[index] if text[index] in '\r\n' else ' ')
                index += 1
            continue
        if text.startswith('@"', index) or text.startswith("@'", index):
            closer = '"@' if text[index + 1] == '"' else "'@"
            chars.extend('  ')
            index += 2
            while index < len(text):
                line_start = index == 0 or text[index - 1] in '\r\n'
                if line_start:
                    close_match = re.match(r'[ \t]*' + re.escape(closer), text[index:])
                    if close_match:
                        chars.extend(' ' * close_match.end())
                        index += close_match.end()
                        break
                chars.append(text[index] if text[index] in '\r\n' else ' ')
                index += 1
            continue
        if char in ("'", '"'):
            quote = char
            chars.append(' ')
            index += 1
            continue
        if char == '#':
            while index < len(text) and text[index] not in '\r\n':
                chars.append(' ')
                index += 1
            continue
        if mask_backtick_escapes and char == '`':
            chars.append(' ')
            if index + 1 < len(text):
                chars.append(text[index + 1] if text[index + 1] in '\r\n' else ' ')
                index += 2
            else:
                index += 1
            continue
        chars.append(char)
        index += 1
    return ''.join(chars)


def extract_powershell_command_spans(text: str, command_name: str) -> List[str]:
    masked = mask_powershell_strings_and_comments(text)
    pattern = re.compile(r'\b' + re.escape(command_name) + r'\b', re.IGNORECASE)
    closing_for_open = {'(': ')', '[': ']', '{': '}'}
    spans: List[str] = []
    for match in pattern.finditer(masked):
        cursor = match.end()
        expected_closers: List[str] = []
        while cursor < len(masked):
            char = masked[cursor]
            continuation = re.match(r'`[ \t]*(?:\r\n|\n|\r)[ \t]*', masked[cursor:])
            if continuation:
                cursor += continuation.end()
                continue
            if char == '`':
                cursor += 2 if cursor + 1 < len(masked) else 1
                continue
            if char in closing_for_open:
                expected_closers.append(closing_for_open[char])
                cursor += 1
                continue
            if expected_closers and char == expected_closers[-1]:
                expected_closers.pop()
                cursor += 1
                continue
            if not expected_closers and (char in ';|' or (char == '&' and cursor + 1 < len(masked) and masked[cursor + 1] == '&')):
                break
            if char in '\r\n' and not expected_closers:
                break
            cursor += 1
        spans.append(text[match.start():cursor])
    return spans


def normalize_powershell_command_span(command_span: str) -> str:
    return re.sub(r'`[ \t]*(?:\r\n|\n|\r)[ \t]*', ' ', command_span)


def powershell_command_scan_text(command_span: str) -> str:
    return mask_powershell_strings_and_comments(
        normalize_powershell_command_span(command_span),
        mask_backtick_escapes=True,
    )


def powershell_parameter_is_count_cap(parameter_name: str) -> bool:
    parameter = parameter_name.strip().lstrip('-').lower()
    return bool(parameter) and any(
        canonical.lower().startswith(parameter)
        for canonical in COUNT_CAP_PARAMETER_NAMES
    )


def powershell_command_count_cap_parameters(command_span: str) -> List[str]:
    scan_text = powershell_command_scan_text(command_span)
    parameters = re.findall(r'(?<![\w-])-(?!-)([A-Za-z][\w-]*)', scan_text)
    return [parameter for parameter in parameters if powershell_parameter_is_count_cap(parameter)]


def powershell_command_uses_count_cap_parameter(command_span: str) -> bool:
    return bool(powershell_command_count_cap_parameters(command_span))


def powershell_command_uses_splatting(command_span: str) -> bool:
    scan_text = powershell_command_scan_text(command_span)
    return re.search(r'(?<![\w$])@[A-Za-z_][\w]*', scan_text) is not None


def powershell_command_span_avoids_count_cap_and_splatting(fixture: str, command_name: str) -> bool:
    spans = extract_powershell_command_spans(fixture, command_name)
    return (
        len(spans) == 1
        and not powershell_command_uses_count_cap_parameter(spans[0])
        and not powershell_command_uses_splatting(spans[0])
    )


def powershell_command_span_detects_count_cap(fixture: str, command_name: str) -> bool:
    spans = extract_powershell_command_spans(fixture, command_name)
    return len(spans) == 1 and powershell_command_uses_count_cap_parameter(spans[0])


def add_missing_errors(prefix: str, checks: Dict[str, object], required_keys: List[str], errors: List[str]) -> None:
    for key in required_keys:
        if not checks.get(key):
            errors.append(prefix + key)
