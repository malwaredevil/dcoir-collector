"""Stable exact-head validation and application helpers for coordinated repair sets."""

from __future__ import annotations

import ast
import json
from pathlib import Path, PurePosixPath
from typing import Any

MAX_EDITS_PER_REPAIR = 6
MAX_EDIT_RANGE_LINES = 80
MAX_EDIT_TEXT_CHARS = 12000
MAX_TOTAL_REPLACEMENT_CHARS = 24000


def file_block(file_text: str, start_line: int, end_line: int) -> str:
    lines = file_text.splitlines()
    if start_line <= 0 or end_line < start_line or end_line > len(lines):
        return ""
    return "\n".join(lines[start_line - 1 : end_line])


def normalized_newlines(text: str) -> str:
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n")


def validate_edit_shape(edit: dict[str, Any]) -> str:
    path = str(edit.get("path", "") or "").strip()
    start = edit.get("start_line", 0)
    end = edit.get("end_line", 0)
    if type(start) is not int or type(end) is not int:
        return "edit line range was not integer typed"
    original = normalized_newlines(str(edit.get("original", "") or ""))
    replacement = normalized_newlines(str(edit.get("replacement", "") or ""))
    if not path:
        return "edit path was empty"
    posix_path = PurePosixPath(path)
    parts = posix_path.parts
    if (
        not parts
        or path.startswith("/")
        or "\\" in path
        or ":" in parts[0]
        or ".." in parts
    ):
        return "edit path was not repository-relative"
    if start <= 0 or end < start:
        return "edit line range was invalid"
    if end - start + 1 > MAX_EDIT_RANGE_LINES:
        return f"edit range exceeded {MAX_EDIT_RANGE_LINES} lines"
    if len(original) > MAX_EDIT_TEXT_CHARS or len(replacement) > MAX_EDIT_TEXT_CHARS:
        return "edit text exceeded the bounded repair-set limit"
    if any(token in original or token in replacement for token in ("```", "~~~", "\x00")):
        return "edit contained an unsafe suggestion-fence or NUL token"
    if len(original.splitlines()) != end - start + 1:
        return "edit original block line count did not match its declared range"
    if replacement == original:
        return "edit did not materially change the selected block"
    if not str(edit.get("purpose", "") or "").strip():
        return "edit purpose was empty"
    return ""


def apply_edits_to_files(file_cache: dict[str, str], edits: list[dict[str, Any]]) -> tuple[dict[str, str], str]:
    if len(edits) > MAX_EDITS_PER_REPAIR:
        return {}, f"repair set exceeded the {MAX_EDITS_PER_REPAIR}-edit limit"
    by_path: dict[str, list[dict[str, Any]]] = {}
    total_replacement = 0
    for edit in edits:
        reason = validate_edit_shape(edit)
        if reason:
            return {}, reason
        total_replacement += len(edit["replacement"])
        by_path.setdefault(edit["path"], []).append(edit)
    if total_replacement > MAX_TOTAL_REPLACEMENT_CHARS:
        return {}, "repair set exceeded the total replacement-character budget"

    updated_files: dict[str, str] = {}
    for path, path_edits in by_path.items():
        if path not in file_cache:
            return {}, f"repair target file was not fetched: {path}"
        original_text = file_cache[path]
        lines = original_text.splitlines()
        ordered = sorted(path_edits, key=lambda item: (item["start_line"], item["end_line"]))
        previous_end = 0
        for edit in ordered:
            start = edit["start_line"]
            end = edit["end_line"]
            if start <= previous_end:
                return {}, f"repair set contains overlapping ranges in {path}"
            previous_end = end
            actual = file_block(original_text, start, end)
            if actual != edit["original"]:
                return {}, f"repair original block did not match exact head text at {path}:{start}-{end}"

        mutated = list(lines)
        for edit in sorted(path_edits, key=lambda item: item["start_line"], reverse=True):
            mutated[edit["start_line"] - 1 : edit["end_line"]] = edit["replacement"].splitlines()
        candidate = "\n".join(mutated)
        if original_text.endswith("\n"):
            candidate += "\n"
        suffix = Path(path).suffix.lower()
        if suffix == ".py":
            try:
                ast.parse(candidate, filename=path)
            except SyntaxError as exc:
                return {}, f"repair set made Python syntax invalid in {path} at line {exc.lineno or 0}"
        elif suffix == ".json":
            try:
                json.loads(candidate)
            except json.JSONDecodeError as exc:
                return {}, f"repair set made JSON invalid in {path} at line {exc.lineno}"
        updated_files[path] = candidate
    return updated_files, ""


def annotate_native_eligibility(
    edits: list[dict[str, Any]], right_line_index: dict[tuple[str, int], int]
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for ordinal, raw in enumerate(edits, start=1):
        edit = dict(raw)
        native = all(
            (edit["path"], line) in right_line_index
            for line in range(edit["start_line"], edit["end_line"] + 1)
        )
        edit["edit_ordinal"] = ordinal
        edit["native_suggestion"] = native
        if not native:
            edit["native_reason"] = "one or more selected lines are not commentable on the PR right-side diff"
        annotated.append(edit)
    return annotated
