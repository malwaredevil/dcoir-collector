#!/usr/bin/env python3
from __future__ import annotations

import re
from typing import NamedTuple

_ANY_OPEN = re.compile(r'^(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})(?P<info>[^\r\n]*)$')
_LINE = re.compile(r'[^\r\n]*(?:\r\n|\r|\n|$)')


class _Fence(NamedTuple):
    open_start: int
    body_start: int
    close_start: int | None
    end: int
    marker: str
    marker_len: int


def _line_content(raw: str) -> str:
    if raw.endswith('\r\n'):
        return raw[:-2]
    if raw.endswith(('\r', '\n')):
        return raw[:-1]
    return raw


def _closing_line(line: str, marker: str, min_len: int) -> bool:
    char = re.escape(marker)
    return bool(re.fullmatch(rf' {{0,3}}{char}{{{min_len},}}[ \t]*', line))


def _top_level_fences(text: str) -> list[_Fence]:
    """Parse rendered top-level CommonMark-style fences once, including tildes."""
    fences: list[_Fence] = []
    current: tuple[int, int, str, int] | None = None
    for line_match in _LINE.finditer(text):
        if line_match.start() == line_match.end():
            continue
        line = _line_content(line_match.group(0))
        if current is not None:
            open_start, body_start, marker, marker_len = current
            if _closing_line(line, marker, marker_len):
                fences.append(_Fence(open_start, body_start, line_match.start(), line_match.end(), marker, marker_len))
                current = None
            continue
        opener = _ANY_OPEN.fullmatch(line)
        if not opener:
            continue
        raw_fence = opener.group('fence')
        if raw_fence.startswith('`') and '`' in opener.group('info'):
            continue
        current = (line_match.start(), line_match.end(), raw_fence[0], len(raw_fence))
    if current is not None:
        open_start, body_start, marker, marker_len = current
        fences.append(_Fence(open_start, body_start, None, len(text), marker, marker_len))
    return fences


def _inside_fence(position: int, fences: list[_Fence]) -> bool:
    return any(fence.open_start <= position < fence.end for fence in fences)


def extract_label_owned_fence(text: str, label: str) -> tuple[str | None, tuple[int, int] | None, list[str]]:
    """Return one top-level governed backtick fence owned by an exact label."""
    fences = _top_level_fences(text)
    raw_matches = re.finditer(rf'(?m)^{re.escape(label)}:[ \t]*$', text)
    matches = [match for match in raw_matches if not _inside_fence(match.start(), fences)]
    if len(matches) != 1:
        return None, None, [f'expected exactly one top-level {label}: label, found {len(matches)}']
    label_match = matches[0]
    rest_start = label_match.end()
    newline = re.match(r'\r\n|\r|\n', text[rest_start:])
    if not newline:
        return None, None, [f'{label}: is not followed by one fenced block']
    expected_open = rest_start + newline.end()
    owned = next((fence for fence in fences if fence.open_start == expected_open and fence.marker == '`'), None)
    if owned is None:
        return None, None, [f'{label}: is not followed by one fenced block']
    if owned.close_start is None:
        return None, None, [f'{label}: fenced block is not closed with a matching fence']
    body = text[owned.body_start:owned.close_start].rstrip('\r\n')
    return body, (label_match.start(), owned.end), []


def strip_label_owned_fences(text: str, labels: set[str]) -> str:
    """Remove only structurally valid top-level fences owned by governed labels."""
    spans: list[tuple[int, int]] = []
    for label in sorted(labels, key=len, reverse=True):
        value, span, errors = extract_label_owned_fence(text, label)
        if value is not None and span is not None and not errors:
            spans.append(span)
    result = text
    for start, end in sorted(spans, reverse=True):
        result = result[:start] + result[end:]
    return result
