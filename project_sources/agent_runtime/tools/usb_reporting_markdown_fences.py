#!/usr/bin/env python3
from __future__ import annotations

import re

_OPEN = re.compile(r'(?m)^(?P<indent>[ \t]{0,3})(?P<fence>`{3,})(?P<info>[^\r\n]*)\r?$')


def _matching_close(text: str, start: int, marker: str, min_len: int) -> re.Match[str] | None:
    char = re.escape(marker)
    close = re.compile(rf'(?m)^[ \t]{{0,3}}(?P<fence>{char}{{{min_len},}})[ \t]*\r?$')
    return close.search(text, start)


def extract_label_owned_fence(text: str, label: str) -> tuple[str | None, tuple[int, int] | None, list[str]]:
    """Return one Markdown fence owned by an exact standalone label.

    Opening fences must use backticks with length >=3. The closing fence must
    use backticks and be at least as long as the opener,
    matching CommonMark fence semantics closely enough for fail-closed scoring.
    """
    matches = list(re.finditer(rf'(?m)^{re.escape(label)}:[ \t]*$', text))
    if len(matches) != 1:
        return None, None, [f'expected exactly one {label}: label, found {len(matches)}']
    label_match = matches[0]
    rest_start = label_match.end()
    opener = re.match(r'\r?\n', text[rest_start:])
    if not opener:
        return None, None, [f'{label}: is not followed by one fenced block']
    open_search_start = rest_start + opener.end()
    open_match = _OPEN.match(text, open_search_start)
    if not open_match:
        return None, None, [f'{label}: is not followed by one fenced block']
    if '`' in open_match.group('info'):
        return None, None, [f'{label}: backtick fenced block info string cannot contain backticks']
    marker = open_match.group('fence')[0]
    marker_len = len(open_match.group('fence'))
    body_start = open_match.end()
    if body_start < len(text) and text[body_start:body_start + 2] == '\r\n':
        body_start += 2
    elif body_start < len(text) and text[body_start] == '\n':
        body_start += 1
    else:
        return None, None, [f'{label}: fenced block opener must end with a newline']
    close_match = _matching_close(text, body_start, marker, marker_len)
    if not close_match:
        return None, None, [f'{label}: fenced block is not closed with a matching fence']
    body = text[body_start:close_match.start()].rstrip('\r\n')
    span_end = close_match.end()
    return body, (label_match.start(), span_end), []


def strip_label_owned_fences(text: str, labels: set[str]) -> str:
    """Remove only structurally valid fences owned by exact governed labels."""
    spans: list[tuple[int, int]] = []
    for label in sorted(labels, key=len, reverse=True):
        value, span, errors = extract_label_owned_fence(text, label)
        if value is not None and span is not None and not errors:
            spans.append(span)
    result = text
    for start, end in sorted(spans, reverse=True):
        result = result[:start] + result[end:]
    return result
