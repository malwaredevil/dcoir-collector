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
            or root_tree.get("sha") != reviewed_head
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




def collector_discovery_is_safe(command: str, root_tree: Any, reviewed_head: str) -> bool:
    return (isinstance(command, str)
            and bool(_STDLIB_COLLECTOR_DISCOVERY.fullmatch(command))
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
