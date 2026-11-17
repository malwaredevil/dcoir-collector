"""Canonical line-oriented uses-reference discovery for workflow and action audits.

This is a bounded reader for conventional GitHub Actions mapping/step syntax,
not a general YAML parser. YAML block scalar bodies contain scripts or prose,
not actual uses declarations, and must not contribute audit references.
"""
from __future__ import annotations

import re
from pathlib import Path

ENTRY_RE = re.compile(
    r"^(?P<indent> *)(?P<sequence>-\s+)?(?P<key>[A-Za-z_][\w.-]*):(?:\s*(?P<value>.*))?$"
)
BLOCK_SCALAR_RE = re.compile(
    r"^[ ]*(?:-\s+)?[A-Za-z_][\w.-]*:\s*[|>][-+1-9]*\s*(?:#.*)?$"
)


def _strip_yaml_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(line):
        if quote == '"' and char == "\\" and not escaped:
            escaped = True
            continue
        if char in {"'", '"'} and not escaped:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
        elif char == "#" and quote is None and (index == 0 or line[index - 1].isspace()):
            return line[:index]
        escaped = False
    return line


def iter_uses_references(path: Path) -> list[tuple[int, str]]:
    """Return references from job and executable step uses fields."""
    references: list[tuple[int, str]] = []
    scalar_indent: int | None = None
    section: str | None = None
    job_indent: int | None = None
    job_field_indent: int | None = None
    job_steps_indent: int | None = None
    job_step_indent: int | None = None
    runs_field_indent: int | None = None
    runs_steps_indent: int | None = None
    runs_step_indent: int | None = None

    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if scalar_indent is not None:
            if not raw_line.strip() or indent > scalar_indent:
                continue
            scalar_indent = None
        line = _strip_yaml_comment(raw_line).rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if BLOCK_SCALAR_RE.match(line):
            scalar_indent = indent + (2 if re.match(r"^[ ]*-\s+", line) else 0)
            continue
        match = ENTRY_RE.match(line)
        if match is None:
            continue
        indent = len(match.group("indent"))
        sequence = match.group("sequence") is not None
        key_indent = indent + (2 if sequence else 0)
        key = match.group("key")
        value = (match.group("value") or "").strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        if indent == 0 and not sequence:
            section = key if key in {"jobs", "runs"} else None
            job_indent = None
            job_field_indent = None
            job_steps_indent = None
            job_step_indent = None
            runs_field_indent = None
            runs_steps_indent = None
            runs_step_indent = None
            continue

        if section == "jobs":
            if (
                not sequence
                and not value
                and indent > 0
                and (job_indent is None or indent <= job_indent)
            ):
                job_indent = indent
                job_field_indent = None
                job_steps_indent = None
                job_step_indent = None
                continue
            if job_indent is None:
                continue
            if not sequence and indent > job_indent:
                if job_field_indent is None:
                    job_field_indent = indent
                if indent == job_field_indent:
                    job_step_indent = None
                    if key == "uses" and value:
                        references.append((line_no, value))
                    job_steps_indent = indent if key == "steps" else None
                    continue
            if job_steps_indent is not None and indent >= job_steps_indent:
                if sequence and indent in {job_steps_indent, job_steps_indent + 2}:
                    job_step_indent = indent
                    if key == "uses" and value:
                        references.append((line_no, value))
                elif (
                    not sequence
                    and job_step_indent is not None
                    and key_indent == job_step_indent + 2
                    and key == "uses"
                    and value
                ):
                    references.append((line_no, value))
            continue

        if section == "runs":
            if not sequence and indent > 0:
                if runs_field_indent is None:
                    runs_field_indent = indent
                if indent == runs_field_indent:
                    runs_step_indent = None
                    runs_steps_indent = indent if key == "steps" else None
                    continue
            if runs_steps_indent is not None and indent >= runs_steps_indent:
                if sequence and indent in {runs_steps_indent, runs_steps_indent + 2}:
                    runs_step_indent = indent
                    if key == "uses" and value:
                        references.append((line_no, value))
                elif (
                    not sequence
                    and runs_step_indent is not None
                    and key_indent == runs_step_indent + 2
                    and key == "uses"
                    and value
                ):
                    references.append((line_no, value))
    return references
