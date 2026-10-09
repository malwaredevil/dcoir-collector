"""Quote and inline-code context helpers for replay marker scoring."""
from __future__ import annotations

import re

QUOTE_CHARS = {'"', "'", "`"}


def occurrence_is_backtick_wrapped(text: str, start: int, end: int) -> bool:
    if start > 0 and end < len(text) and text[start - 1] == "`" and text[end] == "`":
        return True
    positions = [index for index, char in enumerate(text) if char == "`"]
    for offset in range(0, len(positions) - 1, 2):
        opener, closer = positions[offset], positions[offset + 1]
        if opener < start and end <= closer:
            return True
    return False


def occurrence_is_quoted(text: str, start: int, end: int) -> bool:
    if start <= 0 or end >= len(text):
        return False
    before = text[start - 1]
    after = text[end]
    if before in QUOTE_CHARS and after == before:
        return True

    for quote in ('"', '`'):
        positions = [index for index, char in enumerate(text) if char == quote]
        for offset in range(0, len(positions) - 1, 2):
            opener, closer = positions[offset], positions[offset + 1]
            if opener < start and end <= closer:
                trailing = text[end:closer]
                if len(trailing) <= 4 and all(char in " ,.;:!?" for char in trailing):
                    return True
                if quote == '`' and closer - opener <= 80 and not re.search(r"[.!?]\s", text[opener:closer]):
                    return True

    opener = text.rfind("'", max(0, start - 2), start)
    closer = text.find("'", end, min(len(text), end + 6))
    if opener != -1 and closer != -1:
        prefix = text[opener + 1:start]
        trailing = text[end:closer]
        if not prefix.strip() and len(trailing) <= 4 and all(char in " ,.;:!?" for char in trailing):
            return True
    return False
