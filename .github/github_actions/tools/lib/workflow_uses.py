"""Canonical line-oriented uses-reference discovery for workflow and action audits.

This is a bounded reader for conventional GitHub Actions mapping/step syntax,
not a general YAML parser. YAML block scalar bodies contain scripts or prose,
not actual uses declarations, and must not contribute audit references.
"""
from __future__ import annotations

import re
from pathlib import Path

USES_LINE_RE = re.compile(r"^[ ]*(?:-\s+)?uses:\s*(\S.*?)\s*$", re.IGNORECASE)
BLOCK_SCALAR_RE = re.compile(
    r"^[ ]*(?:-\s+)?[A-Za-z_][\w.-]*:\s*[|>][-+1-9]*\s*(?:#.*)?$"
)


def iter_uses_references(path: Path) -> list[tuple[int, str]]:
    """Return (line number, reference) for standard job and step uses fields.

    Leading dashes in steps are optional, comments do not count, and indented
    bodies under YAML block scalars (such as run: | or description: >-) are
    skipped until a nonblank line dedents to the scalar key's indentation.
    """
    references: list[tuple[int, str]] = []
    scalar_indent: int | None = None
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        indent = len(line) - len(line.lstrip(" "))
        if scalar_indent is not None:
            if not line.strip() or indent > scalar_indent:
                continue
            scalar_indent = None
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if BLOCK_SCALAR_RE.match(line):
            scalar_indent = indent
            continue
        match = USES_LINE_RE.match(line)
        if match is None:
            continue
        value = match.group(1).split(" #", 1)[0].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if value:
            references.append((line_no, value))
    return references
