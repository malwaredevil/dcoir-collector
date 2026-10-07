#!/usr/bin/env python3
"""Single owner of PowerShell string/comment masking for the collector CI gates.

mask_powershell_non_code() replaces string literal bodies, here-strings and
comments with spaces while preserving every newline and character position,
so callers can regex-scan code and map matches back to source lines. It follows
PowerShell's quoting rules:

- single-quoted strings: a backtick is a literal character and '' is an
  escaped quote;
- double-quoted strings: a backtick escapes the next character (including
  another backtick or a quote) and "" is an escaped quote;
- here-strings (@' ... '@ and @" ... "@) close only at the start of a line;
- <# ... #> block comments and # line comments.

The runtime-policy, event-text-query and function-reachability gates all use
it, so a quoting rule cannot drift between gates again.
"""
from __future__ import annotations


def _blank(char: str) -> str:
    return char if char in '\r\n' else ' '


def mask_powershell_non_code(text: str, *, mask_backtick_escapes: bool = False) -> str:
    """Return text with string bodies and comments blanked, positions unchanged.

    mask_backtick_escapes also blanks a backtick and the character it escapes
    in code (line continuations keep their newline).
    """
    out: list[str] = []
    length = len(text)
    index = 0
    while index < length:
        char = text[index]
        nxt = text[index + 1] if index + 1 < length else ''

        if char == '<' and nxt == '#':
            end = text.find('#>', index + 2)
            stop = length if end < 0 else end + 2
            out.extend(_blank(c) for c in text[index:stop])
            index = stop
            continue

        if char == '#':
            stop = index
            while stop < length and text[stop] not in '\r\n':
                stop += 1
            out.append(' ' * (stop - index))
            index = stop
            continue

        if char == '@' and nxt in ("'", '"'):
            closer = nxt + '@'
            out.append('  ')
            index += 2
            while index < length:
                at_line_start = text[index - 1] in '\r\n'
                if at_line_start and text.startswith(closer, index):
                    out.append('  ')
                    index += 2
                    break
                out.append(_blank(text[index]))
                index += 1
            continue

        if char in ("'", '"'):
            quote = char
            out.append(' ')
            index += 1
            while index < length:
                current = text[index]
                if quote == '"' and current == '`' and index + 1 < length:
                    out.append(' ')
                    out.append(_blank(text[index + 1]))
                    index += 2
                    continue
                if current == quote:
                    if index + 1 < length and text[index + 1] == quote:
                        out.append('  ')
                        index += 2
                        continue
                    out.append(' ')
                    index += 1
                    break
                out.append(_blank(current))
                index += 1
            continue

        if mask_backtick_escapes and char == '`':
            out.append(' ')
            if index + 1 < length:
                out.append(_blank(nxt))
                index += 2
            else:
                index += 1
            continue

        out.append(char)
        index += 1
    return ''.join(out)
