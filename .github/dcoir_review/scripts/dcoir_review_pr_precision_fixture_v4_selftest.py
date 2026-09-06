#!/usr/bin/env python3
"""Semantic fixture guards for the current clean-precision v4 corpus.

These deterministic checks validate benchmark construction, not model output.
They inspect the right-side/current representation of each relevant changed
file so the current clean controls prove the policy invariants they claim.
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


def main() -> None:
    cases = {str(case["id"]): case for case in precision.load_cases()}
    assert len(cases) == 10

    ps_exit = right_side_file(cases["precision-ps-native-exit-snapshot-verbose-tested"], "src/Invoke-Mirror.ps1")
    ps_exit_test = right_side_file(cases["precision-ps-native-exit-snapshot-verbose-tested"], "tests/Invoke-Mirror.Tests.ps1")
    require(ps_exit, "$copyExit = $LASTEXITCODE", "Write-Verbose", "if ($copyExit -le 7)")
    require(ps_exit_test, "$copyExit = $LASTEXITCODE", "Write-Verbose", "(8 -le 7) | Should -BeFalse")
    forbid(ps_exit, "& where.exe", "if ($LASTEXITCODE -le 7)")
    assert ps_exit.index("$copyExit = $LASTEXITCODE") < ps_exit.index("Write-Verbose")

    ps_remote = right_side_file(cases["precision-ps-remoting-argumentlist-tested"], "src/Test-RemoteMarker.ps1")
    require(ps_remote, "param($RemoteMarker)", "Test-Path -LiteralPath $RemoteMarker", "-ArgumentList $MarkerPath")
    forbid(ps_remote, "Test-Path -LiteralPath $MarkerPath")

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

    gha_title_case = cases["precision-gha-title-via-env-approved-tested"]
    gha_title = right_side_file(gha_title_case, ".github/workflows/diagnostic.yml")
    gha_title_test = right_side_file(gha_title_case, "tests/test_diagnostic_workflow.py")
    require(gha_title, "PR_TITLE: ${{ github.event.pull_request.title }}", "run: printf '%s\\n' \"PR: $PR_TITLE\"")
    require(gha_title_test, "assert '${{ github.event.pull_request.title }}' not in run_line", "assert '$PR_TITLE' in run_line")
    assert str(gha_title_case.get("trusted_context", "")).strip()
    run_lines = [line for line in gha_title.splitlines() if line.strip().startswith("run:")]
    assert run_lines and all("${{ github.event.pull_request.title }}" not in line for line in run_lines)

    gha_fork_case = cases["precision-gha-fork-exact-readonly-approved-tested"]
    gha_fork = right_side_file(gha_fork_case, ".github/workflows/pr-diagnostics.yml")
    gha_fork_test = right_side_file(gha_fork_case, "tests/test_pr_diagnostics_workflow.py")
    require(gha_fork, "on: pull_request", "permissions:\n  contents: read\njobs:", "actions/checkout@v7", "persist-credentials: false")
    forbid(gha_fork, "pull_request_target", "secrets.", ": write")
    require(
        gha_fork_test,
        "assert 'pull_request_target' not in text",
        "permissions = text.split('permissions:\\n', 1)[1].split('jobs:\\n', 1)[0]",
        "assert permissions.strip().splitlines() == ['contents: read']",
        "assert ': write' not in permissions",
        "assert 'secrets.' not in text",
        "assert 'persist-credentials: false' in text",
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

    print("dcoir_review_pr_precision_fixture_v4_selftest passed: all 10 current clean controls prove their audited right-side semantic safety invariants")


if __name__ == "__main__":
    main()
