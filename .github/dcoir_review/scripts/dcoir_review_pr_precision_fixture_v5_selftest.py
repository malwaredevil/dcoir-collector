#!/usr/bin/env python3
"""Semantic fixture guards for the current clean-precision v5 corpus.

These deterministic checks validate benchmark construction, not model output.
They preserve all v4-safe controls while proving the three paired-S1 repairs
cover the concrete counterexamples that exposed optimistic clean labels.
"""
from __future__ import annotations

import dcoir_review_pr_precision_eval as precision


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


def right_side(case: dict) -> str:
    return "\n".join(_current_patch_text(str(item.get("patch", ""))) for item in case["files"])


def right_side_file(case: dict, filename: str) -> str:
    matches = [item for item in case["files"] if str(item.get("filename", "")) == filename]
    assert len(matches) == 1, f"expected exactly one fixture file {filename!r}"
    return _current_patch_text(str(matches[0].get("patch", "")))


def require(text: str, *needles: str) -> None:
    for needle in needles:
        assert needle in text, f"missing fixture invariant: {needle!r}"


def forbid(text: str, *needles: str) -> None:
    for needle in needles:
        assert needle not in text, f"forbidden dirty-control pattern present: {needle!r}"


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


def main() -> None:
    cases = {str(case["id"]): case for case in precision.load_cases()}
    assert len(cases) == 10

    ps_exit = right_side_file(cases["precision-ps-native-exit-snapshot-verbose-tested"], "src/Invoke-Mirror.ps1")
    ps_exit_test = right_side_file(cases["precision-ps-native-exit-snapshot-verbose-tested"], "tests/Invoke-Mirror.Tests.ps1")
    require(ps_exit, "$copyExit = $LASTEXITCODE", "Write-Verbose", "if ($copyExit -le 7)")
    require(ps_exit_test, "$copyExit = $LASTEXITCODE", "Write-Verbose", "(8 -le 7) | Should -BeFalse")
    forbid(ps_exit, "& where.exe", "if ($LASTEXITCODE -le 7)")
    assert ps_exit.index("$copyExit = $LASTEXITCODE") < ps_exit.index("Write-Verbose")

    ps_remote_case = cases["precision-ps-remoting-argumentlist-behavior-tested"]
    ps_remote = right_side_file(ps_remote_case, "src/Test-RemoteMarker.ps1")
    ps_remote_test = right_side_file(ps_remote_case, "tests/Test-RemoteMarker.Tests.ps1")
    require(ps_remote, "param($RemoteMarker)", "Test-Path -LiteralPath $RemoteMarker", "-ArgumentList $MarkerPath")
    forbid(ps_remote, "Test-Path -LiteralPath $MarkerPath")
    require(
        ps_remote_test,
        '. "$PSScriptRoot/../src/Test-RemoteMarker.ps1"',
        "Mock Test-Path {",
        "Mock Invoke-Command {",
        "param($ComputerName, $ScriptBlock, $ArgumentList)",
        "$MarkerPath = $null",
        "& $ScriptBlock @ArgumentList",
        "Assert-MockCalled Invoke-Command -Times 1 -ParameterFilter",
        "Assert-MockCalled Test-Path -Times 1 -ParameterFilter",
    )
    forbid(ps_remote_test, "Mock Invoke-Command { $true }")

    cache_case = cases["precision-py-cache-key-callers-invalidation-tested"]
    cache = right_side(cache_case)
    cache_test = right_side_file(cache_case, "tests/test_cache.py")
    require(
        cache,
        "def reuse_key(content: bytes, model: str, policy_version: str)",
        "len(field).to_bytes(8, 'big')",
        "reuse_key(content, model, policy_version)",
    )
    require(
        cache_test,
        "from review.engine import lookup",
        "reuse_key(b'x', 'm', 'v1') != reuse_key(b'x', 'm', 'v2')",
        "reuse_key(b'x', 'm', 'v1') != reuse_key(b'x', 'n', 'v1')",
        "reuse_key(b'a', 'bc', 'd') != reuse_key(b'a', 'b', 'cd')",
        "lookup(cache, content, 'model-a', 'v1') == 'review-v1'",
        "lookup(cache, content, 'model-a', 'v2') is None",
        "lookup(cache, content, 'model-b', 'v1') is None",
        "lookup(cache, b'y', 'model-a', 'v1') is None",
    )
    forbid(right_side_file(cache_case, "review/cache.py"), "return hashlib.sha256(content).hexdigest()")

    argv = right_side_file(cases["precision-py-subprocess-argv-tested"], "review/collector.py")
    argv_test = right_side_file(cases["precision-py-subprocess-argv-tested"], "tests/test_collector.py")
    require(argv, "argv = [tool, '--source', source, '--case', case_name]", "subprocess.run(argv, shell=False, check=True)")
    require(argv_test, "A && whoami", "shell=False, check=True")
    forbid(argv, "shell=True", "subprocess.run(cmd")

    gha_title_case = cases["precision-gha-title-via-env-all-shell-surfaces-tested"]
    gha_title = right_side_file(gha_title_case, ".github/workflows/diagnostic.yml")
    gha_title_test = right_side_file(gha_title_case, "tests/test_diagnostic_workflow.py")
    raw_title = "${{ github.event.pull_request.title }}"
    assert gha_title.count(raw_title) == 1
    require(gha_title, f"PR_TITLE: {raw_title}", "run: printf '%s\\n' \"PR: $PR_TITLE\"")
    run_lines = [line for line in gha_title.splitlines() if line.lstrip().startswith("run:")]
    assert run_lines
    assert all(raw_title not in line for line in run_lines)
    assert any("$PR_TITLE" in line for line in run_lines)
    require(
        gha_title_test,
        "assert text.count(RAW_PR_TITLE) == 1",
        "assert f'PR_TITLE: {RAW_PR_TITLE}' in text",
        "assert all(RAW_PR_TITLE not in line for line in run_lines)",
        "test_guard_rejects_any_second_raw_title_expression",
        "direct PR-title expression unexpectedly passed the shell-boundary guard",
    )
    assert str(gha_title_case.get("trusted_context", "")).strip()

    gha_fork_case = cases["precision-gha-fork-structural-readonly-approved-tested"]
    gha_fork = right_side_file(gha_fork_case, ".github/workflows/pr-diagnostics.yml")
    gha_fork_test = right_side_file(gha_fork_case, "tests/test_pr_diagnostics_workflow.py")
    lines = gha_fork.splitlines()
    require(gha_fork, "on: pull_request", "permissions:\n  contents: read\njobs:", "actions/checkout@v7", "persist-credentials: false")
    forbid(gha_fork, "pull_request_target", "secrets.", ": write", "write-all")
    assert [line for line in lines if line.strip() == "permissions:"] == ["permissions:"]
    permission_index = lines.index("permissions:")
    assert lines[permission_index + 1] == "  contents: read"
    assert lines[permission_index + 2] == "jobs:"
    checkout_blocks = _checkout_blocks(lines)
    assert checkout_blocks and all("persist-credentials: false" in block for block in checkout_blocks)
    require(
        gha_fork_test,
        "permission_headers = [line for line in lines if line.strip() == 'permissions:']",
        "assert permission_headers == ['permissions:']",
        "assert all('persist-credentials: false' in block for block in checkout_blocks)",
        "test_guard_rejects_job_level_write_permission",
        "pull-requests: write",
        "test_guard_rejects_any_checkout_without_disabled_credentials",
    )
    assert str(gha_fork_case.get("trusted_context", "")).strip()

    debug = right_side(cases["precision-md-debug-observability-aligned-tested"])
    require(debug, "Debug does not force deep review", "mode = 'deep' if 'deep' in flags else 'incremental'", "debug = 'debug' in flags", "resolve({'debug'}) == ('incremental', True)")

    json_case = right_side(cases["precision-json-typed-fallback-tested"])
    require(json_case, '"allow_fallbacks": false', "isinstance(value, bool)", "{'allow_fallbacks': 'false'}")
    forbid(right_side_file(cases["precision-json-typed-fallback-tested"], "config/provider.json"), '"allow_fallbacks": "false"')

    retry = right_side(cases["precision-py-retry-budget-tested"])
    require(retry, "if max_attempts < 1", "range(1, max_attempts + 1)", "if attempt >= max_attempts", "assert len(calls) == 3", "assert len(calls) == 1")
    forbid(right_side_file(cases["precision-py-retry-budget-tested"], "review/retry.py"), "range(max_attempts + 1)")

    bash = right_side(cases["precision-bash-spaced-paths-quoted-tested"])
    require(bash, 'cp -R -- "$source_path" "$destination_path"', "mkdir -- -source destination", 'bash "$script" -source destination', "test -f destination/-source/item.txt")
    forbid(right_side_file(cases["precision-bash-spaced-paths-quoted-tested"], ".github/scripts/copy-evidence.sh"), "cp -R $1 $2")

    print("dcoir_review_pr_precision_fixture_v5_selftest passed: all 10 current clean controls preserve prior safety invariants and the three paired-S1 benchmark defects are fenced by concrete counterexample guards")


if __name__ == "__main__":
    main()
