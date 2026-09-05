#!/usr/bin/env python3
"""Semantic fixture guards for the audited clean-precision v3 corpus.

These checks intentionally validate benchmark construction, not model output.
They prevent known dirty-control patterns from being reintroduced silently.
For changed-file assertions, inspect the right-side/current representation of
unified patches so removed vulnerable lines do not contaminate clean fixtures.
"""
from __future__ import annotations

import dcoir_review_pr_precision_eval as precision


def right_side(case: dict) -> str:
    current: list[str] = []
    for item in case["files"]:
        patch = str(item.get("patch", ""))
        for line in patch.splitlines():
            if line.startswith(("diff --git ", "index ", "--- ", "+++ ", "@@")):
                continue
            if line.startswith("-"):
                continue
            if line.startswith("+") or line.startswith(" "):
                current.append(line[1:])
    return "\n".join(current)


def require(text: str, *needles: str) -> None:
    for needle in needles:
        assert needle in text, f"missing fixture invariant: {needle!r}"


def forbid(text: str, *needles: str) -> None:
    for needle in needles:
        assert needle not in text, f"forbidden dirty-control pattern present: {needle!r}"


def main() -> None:
    cases = {str(case["id"]): case for case in precision.load_cases()}
    assert len(cases) == 10

    ps_exit = right_side(cases["precision-ps-native-exit-snapshot-verbose-tested"])
    require(ps_exit, "$copyExit = $LASTEXITCODE", "Write-Verbose", "if ($copyExit -le 7)")
    forbid(ps_exit, "& where.exe", "if ($LASTEXITCODE -le 7)")
    assert ps_exit.index("$copyExit = $LASTEXITCODE") < ps_exit.index("Write-Verbose")

    ps_remote = right_side(cases["precision-ps-remoting-argumentlist-tested"])
    require(ps_remote, "param($RemoteMarker)", "Test-Path -LiteralPath $RemoteMarker", "-ArgumentList $MarkerPath")
    forbid(ps_remote, "Test-Path -LiteralPath $MarkerPath")

    cache = right_side(cases["precision-py-cache-key-callers-tested"])
    require(
        cache,
        "def reuse_key(content: bytes, model: str, policy_version: str)",
        "len(field).to_bytes(8, 'big')",
        "reuse_key(content, model, policy_version)",
        "reuse_key(b'x', 'm', 'v1') != reuse_key(b'x', 'm', 'v2')",
        "reuse_key(b'a', 'bc', 'd') != reuse_key(b'a', 'b', 'cd')",
    )
    forbid(cache, "return hashlib.sha256(content).hexdigest()")

    argv = right_side(cases["precision-py-subprocess-argv-tested"])
    require(argv, "argv = [tool, '--source', source, '--case', case_name]", "subprocess.run(argv, shell=False, check=True)", "A && whoami")
    forbid(argv, "shell=True", "subprocess.run(cmd")

    gha_title_case = cases["precision-gha-title-via-env-approved-tested"]
    gha_title = right_side(gha_title_case)
    require(gha_title, "PR_TITLE: ${{ github.event.pull_request.title }}", "run: printf '%s\\n' \"PR: $PR_TITLE\"")
    assert str(gha_title_case.get("trusted_context", "")).strip()
    run_lines = [line for line in gha_title.splitlines() if line.strip().startswith("run:")]
    assert run_lines and all("${{ github.event.pull_request.title }}" not in line for line in run_lines)

    gha_fork_case = cases["precision-gha-fork-readonly-approved-tested"]
    gha_fork = right_side(gha_fork_case)
    require(gha_fork, "on: pull_request", "contents: read", "assert 'secrets.' not in text")
    forbid(gha_fork, "pull_request_target", "secrets.OPENROUTER_API_KEY", "contents: write")
    assert str(gha_fork_case.get("trusted_context", "")).strip()

    debug = right_side(cases["precision-md-debug-observability-aligned-tested"])
    require(debug, "Debug does not force deep review", "mode = 'deep' if 'deep' in flags else 'incremental'", "debug = 'debug' in flags", "resolve({'debug'}) == ('incremental', True)")

    json_case = right_side(cases["precision-json-typed-fallback-tested"])
    require(json_case, '"allow_fallbacks": false', "isinstance(value, bool)", "{'allow_fallbacks': 'false'}")
    forbid(json_case, '"allow_fallbacks": "false"')

    retry = right_side(cases["precision-py-retry-budget-tested"])
    require(retry, "if max_attempts < 1", "range(1, max_attempts + 1)", "if attempt >= max_attempts", "assert len(calls) == 3", "assert len(calls) == 1")
    forbid(retry, "range(max_attempts + 1)")

    bash = right_side(cases["precision-bash-spaced-paths-quoted-tested"])
    require(bash, 'cp -R -- "$source_path" "$destination_path"', "mkdir -- -source destination", 'bash "$script" -source destination', "test -f destination/-source/item.txt")
    forbid(bash, "cp -R $1 $2")

    print("dcoir_review_pr_precision_fixture_v3_selftest passed: all 10 clean controls retain their audited current-side semantic safety invariants")


if __name__ == "__main__":
    main()
