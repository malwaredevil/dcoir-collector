#!/usr/bin/env python3
"""PowerShell parser helpers for assembly parity validation."""
from __future__ import annotations

from powershell_assembly_parity_common import *

def static_powershell_parse(text: str) -> dict[str, Any]:
    """A deterministic local parse surrogate used when pwsh is unavailable."""
    normalized = normalize_text(text)
    lines = normalized.splitlines()
    errors: list[str] = []
    stack: list[tuple[str, int, int]] = []
    pairs = {"(": ")", "[": "]", "{": "}"}
    closers = {")": "(", "]": "[", "}": "{"}
    quote: str | None = None
    block_comment = False
    here_string_end: str | None = None
    line = 1
    column = 0
    index = 0
    at_line_start = True
    while index < len(normalized):
        char = normalized[index]
        next_char = normalized[index + 1] if index + 1 < len(normalized) else ""
        column += 1

        if char == "\n":
            line += 1
            column = 0
            at_line_start = True
            index += 1
            continue

        if here_string_end is not None:
            if at_line_start and normalized.startswith(here_string_end, index):
                index += len(here_string_end)
                column += len(here_string_end) - 1
                here_string_end = None
                at_line_start = False
                continue
            index += 1
            at_line_start = False
            continue

        if block_comment:
            if char == "#" and next_char == ">":
                block_comment = False
                index += 2
                column += 1
                at_line_start = False
                continue
            index += 1
            at_line_start = False
            continue

        if quote:
            if char == "`":
                index += 2
                column += 1
                at_line_start = False
                continue
            if char == quote:
                if quote == "'" and next_char == "'":
                    index += 2
                    column += 1
                    at_line_start = False
                    continue
                quote = None
            index += 1
            at_line_start = False
            continue

        if char.isspace():
            index += 1
            continue

        if char == "<" and next_char == "#":
            block_comment = True
            index += 2
            column += 1
            at_line_start = False
            continue

        if char == "#":
            newline = normalized.find("\n", index)
            if newline == -1:
                break
            index = newline
            continue

        if char == "@" and next_char in {"'", '"'} and (
            index + 2 >= len(normalized) or normalized[index + 2] == "\n"
        ):
            here_string_end = next_char + "@"
            index += 2
            column += 1
            at_line_start = False
            continue

        if char in {"'", '"'}:
            quote = char
            index += 1
            at_line_start = False
            continue

        if char in pairs:
            stack.append((char, line, column))
        elif char in closers:
            if not stack or stack[-1][0] != closers[char]:
                errors.append(f"line {line}, column {column}: unmatched {char!r}")
            else:
                stack.pop()
        index += 1
        at_line_start = False

    if quote:
        errors.append(f"unterminated {quote!r} string")
    if block_comment:
        errors.append("unterminated block comment")
    if here_string_end:
        errors.append(f"unterminated here-string ending with {here_string_end!r}")
    for opener, opener_line, opener_column in reversed(stack):
        errors.append(f"line {opener_line}, column {opener_column}: unclosed {opener!r}")

    return {
        "method": "static_balance_check",
        "native_parser_available": False,
        "success": not errors,
        "errors": errors,
        "line_count": len(lines),
    }


def parse_powershell_text(text: str) -> dict[str, Any]:
    pwsh = shutil.which("pwsh")
    if pwsh:
        temp_path: Path | None = None
        parser_script_path: Path | None = None
        cleanup_errors: list[str] = []
        result: dict[str, Any] | None = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".ps1", encoding="utf-8", delete=False) as handle:
                handle.write(text)
                temp_path = Path(handle.name)
            with tempfile.NamedTemporaryFile("w", suffix=".ps1", encoding="utf-8", delete=False) as handle:
                handle.write(POWERSHELL_PARSE_SCRIPT)
                parser_script_path = Path(handle.name)
            command = [
                pwsh,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(parser_script_path),
                str(temp_path),
            ]
            completed = subprocess.run(command, text=True, capture_output=True, timeout=30, check=False)
            errors = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
            if completed.returncode != 0 and completed.stderr.strip():
                errors.extend(line.strip() for line in completed.stderr.splitlines() if line.strip())
            result = {
                "method": "powershell_language_parser",
                "native_parser_available": True,
                "success": completed.returncode == 0,
                "errors": errors,
                "line_count": source_line_count(text),
            }
        except (OSError, subprocess.TimeoutExpired) as exc:
            static = static_powershell_parse(text)
            static["method"] = "static_balance_check_after_native_parser_error"
            static["native_parser_available"] = True
            static["native_parser_error"] = str(exc)
            result = static
        finally:
            for label, path in (("target", temp_path), ("parser", parser_script_path)):
                if path is None:
                    continue
                try:
                    path.unlink()
                except OSError as exc:
                    cleanup_errors.append(f"failed to remove temporary PowerShell {label} script: {exc}")
        if result is None:
            result = static_powershell_parse(text)
            result["method"] = "static_balance_check_after_native_parser_error"
            result["native_parser_available"] = True
            result["native_parser_error"] = "native parser did not produce a result"
        if cleanup_errors:
            result["success"] = False
            result["errors"] = list(result.get("errors", [])) + cleanup_errors
        return result
    return static_powershell_parse(text)
