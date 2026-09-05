#!/usr/bin/env python3
"""Semantic fixture guards for the audited clean-precision v3 corpus.

These checks intentionally validate benchmark construction, not model output.
They prevent known dirty-control patterns from being reintroduced silently.
"""
from __future__ import annotations

import dcoir_review_pr_precision_eval as precision


def joined(case: dict) -> str:
    return "\n".join(str(item.get("patch", "")) for item in case["files"])


def require(text: str, *needles: str) -> None:
    for needle in needles:
        assert needle in text, f"missing fixture invariant: {needle!r}"


def forbid(text: str, *needles: str) -> None:
    for needle in needles:
        assert needle not in text, f"forbidden dirty-control pattern present: {needle!r}"


def main() -> None:
    cases = {str(case["id"]): case for case in precision.load_cases()}
    assert len(cases) == 10

    ps_exit = joined(cases["precision-ps-native-exit-snapshot-verbose-tested"])
    require(ps_exit, "$copyExit = $LASTEXITCODE", "Write-Verbose", "if ($copyExit -le 7)")
    forbid(ps_exit, "& where.exe")
    assert ps_exit.index("$copyExit = $LASTEXITCODE") < ps_exit.index("Write-Verbose")

    ps_remote = joined(cases["precision-ps-remoting-argumentlist-tested"])
    require(ps_remote, "param($RemoteMarker)", "Test-Path -LiteralPath $RemoteMarker", "-ArgumentList $MarkerPath")

    cache = joined(cases["precision-py-cache-key-callers-tested"])
    require(
        cache,
        "def reuse_key(content: bytes, model: str, policy_version: str)",
        "len(field).to_bytes(8, 'big')",
        "reuse_key(content, model, policy_version)",
        "reuse_key(b'x', 'm', 'v1') != reuse_key(b'x', 'm', 'v2')",
        "reuse_key(b'a', 'bc', 'd') != reuse_key(b'a', 'b', 'cd')",
    )

    argv = joined(cases["precision-py-subprocess-argv-tested"])
    require(argv, "argv = [tool, '--source', source, '--case', case_name]", "subprocess.run(argv, shell=False, check=True)", "A && whoami")
    forbid(argv, "shell=True")

    gha_title_case = cases["precision-gha-title-via-env-approved-tested"]
    gha_title = joined(gha_title_case)
    require(gha_title, "PR_TITLE: ${{ github.event.pull_request.title }}", "run: printf '%s\\\\n' \\\"PR: $PR_TITLE\\\"")
    assert str(gha_title_case.get("trusted_context", "")).strip()
    run_lines = [line for line in gha_title.splitlines() if line.startswith("+        run:")]
    assert run_lines and all("${{ github.event.pull_request.title }}" not in line for line in run_lines)

    gha_fork_case = cases["precision-gha-fork-readonly-approved-tested"]
    gha_fork = joined(gha_fork_case)
    require(gha_fork, "+on: pull_request", "+  contents: read", "assert 'secrets.' not in text")
    forbid(gha_fork, "pull_request_target", "secrets.OPENROUTER_API_KEY", "permissions:\n+  contents: write")
    assert str(gha_fork_case.get("trusted_context", "")).strip()

    debug = joined(cases["precision-md-debug-observability-aligned-tested"])
    require(debug, "Debug does not force deep review", "mode = 'deep' if 'deep' in flags else 'incremental'", "debug = 'debug' in flags", "resolve({'debug'}) == ('incremental', True)")

    json_case = joined(cases["precision-json-typed-fallback-tested"])
    require(json_case, '+  "allow_fallbacks": false', "isinstance(value, bool)", "{'allow_fallbacks': 'false'}")
    forbid(json_case, '+  "allow_fallbacks": "false"')

    retry = joined(cases["precision-py-retry-budget-tested"])
    require(retry, "if max_attempts < 1", "range(1, max_attempts + 1)", "if attempt >= max_attempts", "assert len(calls) == 3", "assert len(calls) == 1")
    forbid(retry, "range(max_attempts + 1)")

    bash = joined(cases["precision-bash-spaced-paths-quoted-tested"])
    require(bash, 'cp -R -- \\\"$source_path\\\" \\\"$destination_path\\\"', "mkdir -- -source destination", 'bash \\\"$script\\\" -source destination', "test -f destination/-source/item.txt")

    print("dcoir_review_pr_precision_fixture_v3_selftest passed: all 10 clean controls retain their audited semantic safety invariants")


if __name__ == "__main__":
    main()
