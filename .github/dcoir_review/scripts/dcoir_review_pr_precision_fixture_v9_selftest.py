#!/usr/bin/env python3
"""Deterministic semantic guards for the current clean-precision v9 corpus."""
from __future__ import annotations

import os
import re

import dcoir_review_pr_precision_eval as base
import dcoir_review_pr_precision_eval_v8 as v8
import dcoir_review_pr_precision_eval_v9 as current


def _current_patch_text(patch: str) -> str:
    current_lines: list[str] = []
    for line in patch.splitlines():
        if line.startswith(("diff --git ", "index ", "--- ", "+++ ", "@@", "new file mode ")):
            continue
        if line.startswith("-"):
            continue
        if line.startswith("+") or line.startswith(" "):
            current_lines.append(line[1:])
    return "\n".join(current_lines)


def right_side_file(case: dict, filename: str) -> str:
    matches = [item for item in case["files"] if str(item.get("filename", "")) == filename]
    assert len(matches) == 1, f"expected exactly one fixture file {filename!r}"
    return _current_patch_text(str(matches[0].get("patch", "")))


SECRET_CONTEXT_RE = re.compile(r"(?<![A-Za-z0-9_])secrets(?![A-Za-z0-9_])", re.IGNORECASE)


def _github_expression_bodies(text: str) -> list[str]:
    bodies: list[str] = []
    cursor = 0
    while True:
        start = text.find("${{", cursor)
        if start < 0:
            return bodies
        index = start + 3
        quote: str | None = None
        escaped = False
        while index < len(text) - 1:
            char = text[index]
            if quote is not None:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                index += 1
                continue
            if char in ("'", '"'):
                quote = char
                index += 1
                continue
            if text.startswith("}}", index):
                bodies.append(text[start + 3:index])
                cursor = index + 2
                break
            index += 1
        else:
            raise AssertionError("unterminated GitHub expression")


def _strip_quoted_literals(expression: str) -> str:
    output: list[str] = []
    quote: str | None = None
    escaped = False
    for char in expression:
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            output.append(" ")
            continue
        if char in ("'", '"'):
            quote = char
            output.append(" ")
        else:
            output.append(char)
    return "".join(output)


def _references_secret_context(text: str) -> bool:
    return any(
        SECRET_CONTEXT_RE.search(_strip_quoted_literals(expression)) is not None
        for expression in _github_expression_bodies(text)
    )


def _checkout_blocks(lines: list[str]) -> list[str]:
    blocks: list[str] = []
    for index, line in enumerate(lines):
        if not line.strip().startswith("- uses: actions/checkout@"):
            continue
        indent = len(line) - len(line.lstrip())
        block = [line]
        for following in lines[index + 1:]:
            following_indent = len(following) - len(following.lstrip())
            if following.strip().startswith("- ") and following_indent == indent:
                break
            if following and following_indent < indent:
                break
            block.append(following)
        blocks.append("\n".join(block))
    return blocks


def _assert_fork_guard(text: str) -> None:
    lines = text.splitlines()
    assert "pull_request_target" not in text
    assert not _references_secret_context(text)
    assert "write-all" not in text
    permission_key_lines = [line for line in lines if "permissions" in line]
    assert permission_key_lines == ["permissions:"]
    permission_index = lines.index("permissions:")
    assert lines[permission_index + 1] == "  contents: read"
    assert lines[permission_index + 2] == "jobs:"
    checkout_blocks = _checkout_blocks(lines)
    assert checkout_blocks
    assert all("persist-credentials: false" in block for block in checkout_blocks)


def _expect_rejected(text: str) -> None:
    try:
        _assert_fork_guard(text)
    except AssertionError:
        return
    raise AssertionError("unsafe fork workflow unexpectedly passed the v9 guard")


def main() -> None:
    v8_cases = {str(case["id"]): case for case in v8.load_v8_cases()}
    v9_cases = {str(case["id"]): case for case in current.load_v9_cases()}
    assert len(v8_cases) == len(v9_cases) == 10
    assert all(case["expected_findings"] == [] for case in v9_cases.values())

    old_id = "precision-gha-fork-single-permissions-key-approved-tested"
    new_id = "precision-gha-fork-semantic-secret-context-approved-tested"
    assert old_id in v8_cases and old_id not in v9_cases
    assert new_id not in v8_cases and new_id in v9_cases
    assert {key: value for key, value in v8_cases.items() if key != old_id} == {
        key: value for key, value in v9_cases.items() if key != new_id
    }

    fork_case = v9_cases[new_id]
    workflow = right_side_file(fork_case, ".github/workflows/pr-diagnostics.yml")
    fork_test = right_side_file(fork_case, "tests/test_pr_diagnostics_workflow.py")
    _assert_fork_guard(workflow)

    rejected_mutations = (
        workflow.replace("    runs-on: ubuntu-latest", "    permissions:\n      pull-requests: write\n    runs-on: ubuntu-latest"),
        workflow.replace("    runs-on: ubuntu-latest", "    permissions: {pull-requests: write}\n    runs-on: ubuntu-latest"),
        workflow.replace("    runs-on: ubuntu-latest", "    permissions:  # job override\n      pull-requests: write  # temporary\n    runs-on: ubuntu-latest"),
        workflow + "\n      - uses: actions/checkout@v7\n",
        workflow + '\n      - run: echo "${{ secrets.DEPLOY_KEY }}"\n',
        workflow + '\n      - run: echo "${{ secrets[\'DEPLOY_KEY\'] }}"\n',
        workflow + '\n      - run: echo "${{ secrets }}"\n',
        workflow + '\n      - run: echo "${{ toJSON(secrets) }}"\n',
        workflow + '\n      - run: echo "${{ format(\'}}\', secrets.DEPLOY_KEY) }}"\n',
    )
    for mutation in rejected_mutations:
        _expect_rejected(mutation)
    _assert_fork_guard(workflow + '\n      - run: echo "${{ \'secrets }}\' }}"\n')

    for needle in (
        "_github_expression_bodies",
        "SECRET_CONTEXT_RE",
        "permission_key_lines = [line for line in lines if 'permissions' in line]",
        "test_guard_rejects_dot_secret_context",
        "test_guard_rejects_bracket_secret_context",
        "test_guard_rejects_whole_secret_context",
        "test_guard_rejects_function_wrapped_secret_context",
        "test_guard_rejects_secret_context_after_quoted_closing_braces",
        "test_secret_word_inside_expression_string_is_not_a_context_reference",
    ):
        assert needle in fork_test, f"missing v9 fork invariant: {needle!r}"
    assert "actions/checkout@v7" in workflow
    assert "successfully executed actions/checkout@v7" in str(fork_case.get("trusted_context", ""))

    workflow_cases = [
        case for case in v9_cases.values()
        if any(str(item["filename"]).startswith(".github/workflows/") for item in case["files"])
    ]
    assert len(workflow_cases) == 2
    assert all(str(case.get("trusted_context", "")).strip() for case in workflow_cases)

    old = os.environ.get("DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT")
    try:
        os.environ["DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT"] = "1"
        for case in v9_cases.values():
            prompt = base.build_pr_prompt(case)
            assert str(case["ground_truth_rationale"]) not in prompt
            assert "expected_findings" not in prompt
            assert str(case["id"]) not in prompt
            assert "ground_truth_rationale" not in prompt
            if case.get("trusted_context"):
                assert "Trusted evaluation context:" in prompt
                assert str(case["trusted_context"]) in prompt
        os.environ["DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT"] = "0"
        for case in workflow_cases:
            prompt = base.build_pr_prompt(case)
            assert "Trusted evaluation context:" not in prompt
            assert str(case["trusted_context"]) not in prompt
    finally:
        if old is None:
            os.environ.pop("DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT", None)
        else:
            os.environ["DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT"] = old

    print("dcoir_review_pr_precision_fixture_v9_selftest passed: v8 history is preserved; the fork guard uses quote-aware expression parsing, rejects semantic secrets-context references, preserves v8 permission coverage, and keeps quoted literals benign; ground truth stays hidden")


if __name__ == "__main__":
    main()
