#!/usr/bin/env python3
"""Semantic fixture guards for the current clean-precision v6 corpus.

V6 changes only the PR-title workflow control. This selftest proves every other
case is byte-for-byte identical to historical v5, then exercises the normalized
title-expression guard against the two concrete v5 bypasses.
"""
from __future__ import annotations

import re

import dcoir_review_pr_precision_eval as precision

TITLE_EXPR = re.compile(r"\$\{\{\s*github\.event\.pull_request\.title\s*\}\}")
ENV_BINDING = re.compile(r"^\s*PR_TITLE:\s*\$\{\{\s*github\.event\.pull_request\.title\s*\}\}\s*$")


def _current_patch_text(patch: str) -> str:
    current: list[str] = []
    for line in patch.splitlines():
        if line.startswith(("diff --git ", "index ", "--- ", "+++ ", "@@")):
            continue
        if line.startswith("-"):
            continue
        if line.startswith("+") or line.startswith(" "):
            current.append(line[1:])
    return "\n".join(current)


def right_side_file(case: dict, filename: str) -> str:
    matches = [item for item in case["files"] if str(item.get("filename", "")) == filename]
    assert len(matches) == 1, f"expected exactly one fixture file {filename!r}"
    return _current_patch_text(str(matches[0].get("patch", "")))


def _run_shell_blocks(text: str) -> list[str]:
    lines = text.splitlines()
    blocks: list[str] = []
    for index, line in enumerate(lines):
        match = re.match(r"^(\s*)run:\s*(.*)$", line)
        if not match:
            continue
        indent = len(match.group(1))
        block = [match.group(2)]
        for following in lines[index + 1:]:
            if not following.strip():
                block.append(following)
                continue
            following_indent = len(following) - len(following.lstrip())
            if following_indent <= indent:
                break
            block.append(following)
        blocks.append("\n".join(block))
    return blocks


def _assert_title_guard(text: str) -> None:
    assert len(TITLE_EXPR.findall(text)) == 1
    expression_lines = [line for line in text.splitlines() if TITLE_EXPR.search(line)]
    assert len(expression_lines) == 1
    assert ENV_BINDING.fullmatch(expression_lines[0])
    run_blocks = _run_shell_blocks(text)
    assert run_blocks
    assert all(not TITLE_EXPR.search(block) for block in run_blocks)
    assert any("$PR_TITLE" in block for block in run_blocks)


def _assert_rejected(text: str) -> None:
    try:
        _assert_title_guard(text)
    except AssertionError:
        return
    raise AssertionError("unsafe title-expression mutation unexpectedly passed v6 guard")


def main() -> None:
    v5_cases = {str(case["id"]): case for case in precision.load_v5_cases()}
    v6_cases = {str(case["id"]): case for case in precision.load_v6_cases()}
    assert len(v5_cases) == len(v6_cases) == 10

    old_id = "precision-gha-title-via-env-all-shell-surfaces-tested"
    new_id = "precision-gha-title-via-env-normalized-expression-tested"
    assert old_id in v5_cases and old_id not in v6_cases
    assert new_id not in v5_cases and new_id in v6_cases

    v5_without_title = {key: value for key, value in v5_cases.items() if key != old_id}
    v6_without_title = {key: value for key, value in v6_cases.items() if key != new_id}
    assert v5_without_title == v6_without_title

    case = v6_cases[new_id]
    workflow = right_side_file(case, ".github/workflows/diagnostic.yml")
    test = right_side_file(case, "tests/test_diagnostic_workflow.py")
    _assert_title_guard(workflow)

    _assert_rejected(
        workflow + '\n      - run: echo "title=${{  github.event.pull_request.title   }}"\n'
    )
    _assert_rejected(
        workflow + '\n      - run: |\n          echo "title=${{ github.event.pull_request.title }}"\n'
    )

    for needle in (
        "TITLE_EXPR = re.compile",
        "ENV_BINDING = re.compile",
        "def _run_shell_blocks(text):",
        "assert len(matches) == 1",
        "assert ENV_BINDING.fullmatch(expression_lines[0])",
        "test_guard_rejects_whitespace_variant_in_inline_run",
        "test_guard_rejects_raw_title_in_multiline_run_body",
    ):
        assert needle in test, f"missing v6 title-guard invariant: {needle!r}"
    assert str(case.get("trusted_context", "")).strip()

    print("dcoir_review_pr_precision_fixture_v6_selftest passed: v5 non-title controls are unchanged and normalized inline/multiline PR-title bypasses are rejected")


if __name__ == "__main__":
    main()
