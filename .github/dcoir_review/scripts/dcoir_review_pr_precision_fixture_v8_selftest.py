#!/usr/bin/env python3
"""Deterministic semantic guards for the current clean-precision v8 corpus."""
from __future__ import annotations

import json
import os

import dcoir_review_pr_precision_eval as v7
import dcoir_review_pr_precision_eval_v8 as current


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
    assert "secrets." not in text
    assert "write-all" not in text
    permission_key_lines = [line for line in lines if "permissions" in line]
    assert permission_key_lines == ["permissions:"]
    permission_index = lines.index("permissions:")
    assert lines[permission_index + 1] == "  contents: read"
    assert lines[permission_index + 2] == "jobs:"
    checkout_blocks = _checkout_blocks(lines)
    assert checkout_blocks
    assert all("persist-credentials: false" in block for block in checkout_blocks)


def _expect_fork_rejected(text: str) -> None:
    try:
        _assert_fork_guard(text)
    except AssertionError:
        return
    raise AssertionError("unsafe fork workflow unexpectedly passed the v8 guard")


def main() -> None:
    v7_cases = {str(case["id"]): case for case in v7.load_v7_cases()}
    v8_cases = {str(case["id"]): case for case in current.load_v8_cases()}
    assert len(v7_cases) == len(v8_cases) == 10
    assert all(case["expected_findings"] == [] for case in v8_cases.values())

    replacements = {
        "precision-ps-native-exit-snapshot-verbose-tested": "precision-ps-native-exit-snapshot-behavior-tested",
        "precision-json-typed-fallback-tested": "precision-json-typed-fallback-semantics-preserved-tested",
        "precision-gha-fork-structural-readonly-approved-tested": "precision-gha-fork-single-permissions-key-approved-tested",
    }
    for old_id, new_id in replacements.items():
        assert old_id in v7_cases and old_id not in v8_cases
        assert new_id not in v7_cases and new_id in v8_cases

    v7_unchanged = {key: value for key, value in v7_cases.items() if key not in replacements}
    v8_unchanged = {key: value for key, value in v8_cases.items() if key not in replacements.values()}
    assert v7_unchanged == v8_unchanged

    ps_case = v8_cases["precision-ps-native-exit-snapshot-behavior-tested"]
    ps_source = right_side_file(ps_case, "src/Invoke-Mirror.ps1")
    ps_test = right_side_file(ps_case, "tests/Invoke-Mirror.Tests.ps1")
    assert "function Invoke-RobocopyExit" in ps_source
    assert "& robocopy.exe $Source $Destination /MIR\n    return $LASTEXITCODE" in ps_source
    assert ps_source.index("$copyExit = Invoke-RobocopyExit") < ps_source.index("Write-Verbose") < ps_source.index("if ($copyExit -le 7)")
    for exit_code, assertion in ((0, "Should -BeTrue"), (7, "Should -BeTrue"), (8, "Should -BeFalse")):
        assert f"Mock Invoke-RobocopyExit {{ {exit_code} }}" in ps_test
        block = ps_test.split(f"Mock Invoke-RobocopyExit {{ {exit_code} }}", 1)[1].split("}", 1)[0]
        assert "Invoke-Mirror -Source source -Destination destination" in block
        assert assertion in block
    assert "captures LASTEXITCODE immediately in the native helper" in ps_test

    json_case = v8_cases["precision-json-typed-fallback-semantics-preserved-tested"]
    config = json.loads(right_side_file(json_case, "config/provider.json"))
    assert config["allow_fallbacks"] is False
    provider_test = right_side_file(json_case, "tests/test_provider.py")
    assert "from review.provider import provider_policy" in provider_test
    assert "provider_policy({'allow_fallbacks': False})" in provider_test
    assert "provider_policy({'allow_fallbacks': 'false'})" in provider_test
    assert "pytest.raises(TypeError)" in provider_test

    fork_case = v8_cases["precision-gha-fork-single-permissions-key-approved-tested"]
    workflow = right_side_file(fork_case, ".github/workflows/pr-diagnostics.yml")
    fork_test = right_side_file(fork_case, "tests/test_pr_diagnostics_workflow.py")
    _assert_fork_guard(workflow)
    mutations = (
        workflow.replace("    runs-on: ubuntu-latest", "    permissions:\n      pull-requests: write\n    runs-on: ubuntu-latest"),
        workflow.replace("    runs-on: ubuntu-latest", "    permissions: {pull-requests: write}\n    runs-on: ubuntu-latest"),
        workflow.replace("    runs-on: ubuntu-latest", "    permissions:  # job override\n      pull-requests: write  # temporary\n    runs-on: ubuntu-latest"),
        workflow + "\n      - uses: actions/checkout@v7\n",
    )
    for mutation in mutations:
        _expect_fork_rejected(mutation)
    for needle in (
        "permission_key_lines = [line for line in lines if 'permissions' in line]",
        "test_guard_rejects_job_level_block_write_permission",
        "test_guard_rejects_job_level_flow_write_permission",
        "test_guard_rejects_commented_job_level_write_permission",
        "test_guard_rejects_any_checkout_without_disabled_credentials",
    ):
        assert needle in fork_test, f"missing v8 fork invariant: {needle!r}"
    assert "actions/checkout@v7" in workflow
    assert "successfully executed actions/checkout@v7" in str(fork_case.get("trusted_context", ""))

    workflow_cases = [
        case for case in v8_cases.values()
        if any(str(item["filename"]).startswith(".github/workflows/") for item in case["files"])
    ]
    assert len(workflow_cases) == 2
    assert all(str(case.get("trusted_context", "")).strip() for case in workflow_cases)

    old = os.environ.get("DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT")
    try:
        os.environ["DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT"] = "1"
        for case in v8_cases.values():
            prompt = v7.build_pr_prompt(case)
            assert str(case["ground_truth_rationale"]) not in prompt
            assert "expected_findings" not in prompt
            assert str(case["id"]) not in prompt
            assert "ground_truth_rationale" not in prompt
            if case.get("trusted_context"):
                assert "Trusted evaluation context:" in prompt
                assert str(case["trusted_context"]) in prompt
        os.environ["DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT"] = "0"
        for case in workflow_cases:
            prompt = v7.build_pr_prompt(case)
            assert "Trusted evaluation context:" not in prompt
            assert str(case["trusted_context"]) not in prompt
    finally:
        if old is None:
            os.environ.pop("DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT", None)
        else:
            os.environ["DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT"] = old

    print("dcoir_review_pr_precision_fixture_v8_selftest passed: v7 history is preserved; three ambiguous controls are replaced; PowerShell behavior, JSON semantics, and fork permissions are hardened; ground truth stays hidden")


if __name__ == "__main__":
    main()
