"""Fail-closed exact-head proof for the fixed standard-library unittest runner.

One immutable GitHub commit-root tree read verifies that no repository module
can shadow unittest. No untrusted Python or shell text is ever executed.
"""
from __future__ import annotations

import re
from typing import Any

from dcoir_review.source_inventory_contract import _logical_shell_commands

_HEAD = re.compile(r"^[0-9a-f]{40}$")

# Standard-library unittest discovery is not a repository-local Python module.
# Permit only the static collector suite command already used in CI; any
# additional switch, shell operator, variable, or second module stays fail-closed.
_STDLIB_COLLECTOR_DISCOVERY = re.compile(
    r"""^\s*python\s+-m\s+unittest\s+discover\s+"""
    r"""-s\s+project_sources/collector/tools\s+-p\s+"""
    r"""(?:'test_\*\.py'|"test_\*\.py"|test_\*\.py)\s*$""",
)

def _unittest_origin_verified(root_tree: Any, reviewed_head: str) -> bool:
    """Proof from the immutable GitHub commit-root tree, never 404 guesses.

    A repo-root module/package can shadow the standard-library test runner.
    Missing, stale, truncated, malformed, or shadowed trees all fail closed.
    """
    if (not isinstance(root_tree, dict)
            or root_tree.get("commit_sha") != reviewed_head
            or not isinstance(root_tree.get("expected_tree_sha"), str)
            or not _HEAD.fullmatch(root_tree["expected_tree_sha"])
            or root_tree.get("sha") != root_tree["expected_tree_sha"]
            or root_tree.get("truncated") is not False):
        return False
    entries = root_tree.get("tree")
    if not isinstance(entries, list) or not 2 <= len(entries) <= 2048:
        return False
    roots: dict[str, str] = {}
    for item in entries:
        if not isinstance(item, dict):
            return False
        name = item.get("path")
        kind = item.get("type")
        if (not isinstance(name, str) or not name
                or len(name) > 255 or "/" in name or "\\" in name
                or kind not in {"blob", "tree", "commit"}):
            return False
        folded = name.casefold()
        # Conservative across Python platforms, source/pyc/extension modules,
        # packages, case variants, and any other unittest.* root entry.
        if folded == "unittest" or folded.startswith("unittest."):
            return False
        if folded in roots:
            return False
        roots[folded] = kind
    return roots.get(".github") == "tree" and roots.get("project_sources") == "tree"





# An exemption is only proven in the one known, isolated Windows test step.
# The preceding source must not change Python's module lookup or executable
# path. A later unrelated step may use working-directory safely, but a job/
# workflow-level default or env applies to the test step regardless of order.
_IMPORT_RISK = re.compile(
    r"(?:\b(?:PYTHONPATH|PYTHONHOME|PYTHONUSERBASE|PYTHONSAFEPATH|"
    r"GITHUB_PATH|GITHUB_ENV|PATH)\b|"
    r"\b(?:Set-Location|Push-Location|Pop-Location|Set-Alias|New-Alias|"
    r"Set-Item|New-Item|Remove-Item|Import-Module|cd|pushd|popd|chdir)\b|"
    r"\bfunction\s+python\b|"
    r"^\s*(?:env|defaults|working-directory)\s*:)",
    re.I | re.M,
)
_STEP_HEADER = re.compile(r"^(?P<indent> *)-\s+name:\s+Run collector tool unit tests\s*$")
_ANY_STEP = re.compile(r"^(?P<indent> *)-\s+(?:name|run|uses)\s*:")
_POST_SCOPE = re.compile(r"^(?P<indent> *)(?:env|defaults|working-directory)\s*:", re.I)


def _runner_context_is_safe(source: str, command_start_line: int) -> bool:
    """Whitelist a single isolated CI step; abstain on ambient path state.

    The shell body is intentionally exact, not an incomplete shell parser:
    unsupported conditionals/aliases/commands and altered guards fail closed.
    """
    if not isinstance(source, str) or not isinstance(command_start_line, int):
        return False
    lines = source.splitlines()
    if not 0 < command_start_line <= len(lines):
        return False
    starts = [
        (i, len(m.group("indent")))
        for i, line in enumerate(lines[:command_start_line])
        if (m := _STEP_HEADER.fullmatch(line))
    ]
    if len(starts) != 1:
        return False
    step, depth = starts[0]
    if not (step < command_start_line - 1 and depth >= 2):
        return False
    next_step = next((
        i for i in range(step + 1, len(lines))
        if (m := _ANY_STEP.match(lines[i])) and len(m.group("indent")) <= depth
    ), len(lines))
    expected_step = [
        "- name: Run collector tool unit tests",
        "shell: pwsh",
        "run: |",
        "python -m unittest discover -s project_sources/collector/tools -p 'test_*.py'",
        "if ($LASTEXITCODE -ne 0) {",
        "throw 'Collector tool unit tests failed.'",
        "}",
    ]
    current_step = [line.strip() for line in lines[step:next_step] if line.strip()]
    if current_step != expected_step:
        return False
    # Prior job/step commands could set environment for the test runner.
    before = "\n".join(line for line in lines[:step] if not line.lstrip().startswith("#"))
    if _IMPORT_RISK.search(before):
        return False
    # A YAML job or workflow-level env/defaults property may follow steps.
    # Later unrelated step-local working-directory must remain acceptable.
    for line in lines[next_step:]:
        match = _POST_SCOPE.match(line)
        if match and len(match.group("indent")) < depth:
            return False
    return True

def collector_discovery_is_safe(
    command: str, root_tree: Any, reviewed_head: str,
    workflow_source: str, command_start_line: int,
) -> bool:
    return (isinstance(command, str)
            and bool(_STDLIB_COLLECTOR_DISCOVERY.fullmatch(command))
            and _runner_context_is_safe(workflow_source, command_start_line)
            and _unittest_origin_verified(root_tree, reviewed_head))


def maybe_load_unittest_root_tree(source: str, head: str, fetch_root_tree):
    """Return (immutable_root_tree, checked), fetching at most once per caller.

    The caller memoizes this tuple across selected review contexts. Unavailable
    GitHub evidence is never treated as proof of the standard-library source.
    """
    if (not isinstance(source, str)
            or not any(_STDLIB_COLLECTOR_DISCOVERY.fullmatch(command)
                       for _a, _b, command in _logical_shell_commands(source))):
        return None, False
    if not isinstance(head, str) or not _HEAD.fullmatch(head):
        return None, True
    if fetch_root_tree is None:
        return None, True
    try:
        return fetch_root_tree(head), True
    except Exception:
        return None, True

def fetch_verified_unittest_root_tree(gh: Any, reviewed_head: str) -> dict[str, Any] | None:
    """Resolve commit -> immutable tree and cross-verify both object SHAs.

    GitHub's commit object and its root tree have DISTINCT SHA identifiers.
    Never infer trust from GET /git/trees/{commit_sha}, an implicit alias, a
    missing response, or an unvalidated tree response.
    """
    if not isinstance(reviewed_head, str) or not _HEAD.fullmatch(reviewed_head):
        return None
    commit = gh.request(
        "GET", f"/repos/{gh.repo}/git/commits/{reviewed_head}"
    )
    if not isinstance(commit, dict) or commit.get("sha") != reviewed_head:
        return None
    tree_ref = commit.get("tree")
    if not isinstance(tree_ref, dict):
        return None
    tree_sha = tree_ref.get("sha")
    if not isinstance(tree_sha, str) or not _HEAD.fullmatch(tree_sha):
        return None
    tree = gh.request("GET", f"/repos/{gh.repo}/git/trees/{tree_sha}")
    if not isinstance(tree, dict):
        return None
    return {
        "commit_sha": reviewed_head,
        "expected_tree_sha": tree_sha,
        "sha": tree.get("sha"),
        "truncated": tree.get("truncated"),
        "tree": tree.get("tree"),
    }
