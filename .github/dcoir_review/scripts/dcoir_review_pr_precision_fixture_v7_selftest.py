#!/usr/bin/env python3
"""Semantic fixture guards for the current clean-precision v7 corpus.

V7 changes only the PR-title workflow control. This selftest proves every other
case is byte-for-byte identical to historical v6, then exercises the stronger
shell-boundary invariant against dot, bracket/index, function-wrapped, inline,
literal-block, and folded run-step expression forms.
"""
from __future__ import annotations

import re

import dcoir_review_pr_precision_eval as precision

ENV_BINDING = re.compile(r"^\s*PR_TITLE:\s*\$\{\{\s*github\.event\.pull_request\.title\s*\}\}\s*$")
GITHUB_EXPR_OPEN = "${{"
RUN_KEY = re.compile(r"^(?P<indent>\s*)(?:-\s+)?run\s*:\s*(?P<body>.*)$")


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
        match = RUN_KEY.match(line)
        if not match:
            continue
        indent = len(match.group("indent"))
        block = [match.group("body")]
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
    env_lines = [line for line in text.splitlines() if line.lstrip().startswith("PR_TITLE:")]
    assert len(env_lines) == 1
    assert ENV_BINDING.fullmatch(env_lines[0])
    run_blocks = _run_shell_blocks(text)
    assert run_blocks
    assert all(GITHUB_EXPR_OPEN not in block for block in run_blocks)
    assert any("$PR_TITLE" in block for block in run_blocks)


def _assert_rejected(text: str) -> None:
    try:
        _assert_title_guard(text)
    except AssertionError:
        return
    raise AssertionError("unsafe direct GitHub-expression interpolation unexpectedly passed v7 guard")


def main() -> None:
    v6_cases = {str(case["id"]): case for case in precision.load_v6_cases()}
    v7_cases = {str(case["id"]): case for case in precision.load_v7_cases()}
    assert len(v6_cases) == len(v7_cases) == 10

    old_id = "precision-gha-title-via-env-normalized-expression-tested"
    new_id = "precision-gha-title-via-env-no-shell-expressions-tested"
    assert old_id in v6_cases and old_id not in v7_cases
    assert new_id not in v6_cases and new_id in v7_cases

    v6_without_title = {key: value for key, value in v6_cases.items() if key != old_id}
    v7_without_title = {key: value for key, value in v7_cases.items() if key != new_id}
    assert v6_without_title == v7_without_title

    case = v7_cases[new_id]
    workflow = right_side_file(case, ".github/workflows/diagnostic.yml")
    test = right_side_file(case, "tests/test_diagnostic_workflow.py")
    _assert_title_guard(workflow)

    mutations = (
        workflow + '\n      - run: echo "title=${{  github.event.pull_request.title   }}"\n',
        workflow + '\n      - run: |\n          echo "title=${{ github.event.pull_request.title }}"\n',
        workflow + "\n      - run: echo \"title=${{ github.event.pull_request['title'] }}\"\n",
        workflow + "\n      - run : >\n          echo \"title=${{ github['event']['pull_request']['title'] }}\"\n",
        workflow + "\n      - run: echo \"title=${{ toJSON(github.event.pull_request['title']) }}\"\n",
    )
    for mutation in mutations:
        _assert_rejected(mutation)

    for needle in (
        "ENV_BINDING = re.compile",
        "GITHUB_EXPR_OPEN = '${{'",
        "RUN_KEY = re.compile",
        "assert all(GITHUB_EXPR_OPEN not in block for block in run_blocks)",
        "test_guard_rejects_whitespace_variant_in_inline_run",
        "test_guard_rejects_raw_title_in_multiline_run_body",
        "test_guard_rejects_bracket_accessor_in_inline_run",
        "test_guard_rejects_full_bracket_chain_and_folded_run",
        "test_guard_rejects_function_wrapped_title_expression",
    ):
        assert needle in test, f"missing v7 title-guard invariant: {needle!r}"
    assert str(case.get("trusted_context", "")).strip()

    print("dcoir_review_pr_precision_fixture_v7_selftest passed: v6 non-title controls are unchanged and direct GitHub expressions are rejected across dot/bracket/function and inline/block/folded run forms")


if __name__ == "__main__":
    main()
