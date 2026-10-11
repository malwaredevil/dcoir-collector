"""Source-backed, action-local source-inventory completeness evidence.

Source is treated as untrusted data. Structural checks are not proof of
runtime correctness or of the absence of guards outside the examined action.
"""
from __future__ import annotations

import ast
from pathlib import PurePosixPath
import re

MAX_SOURCE_CHARS = 120_000
_COMMAND = re.compile(
    r"(?<![A-Za-z0-9_])(?:python(?:3(?:\.\d+)?)?|py\s+-3(?:\.\d+)?)"
    r"\s+(?P<path>[A-Za-z0-9_./-]+\.py)\b",
    re.IGNORECASE,
)
def _git_freshness_comparator(source: str) -> bool:
    """Require source-code structure, not matching comments or docstrings."""
    if not isinstance(source, str) or len(source) > MAX_SOURCE_CHARS:
        return False
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return False
    nodes = tuple(ast.walk(tree))
    calls_fresh = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name) and node.func.id == "build_inventory"
        for node in nodes
    )
    source_guard = any(
        isinstance(node, ast.Compare)
        and any(isinstance(op, ast.NotEq) for op in node.ops)
        and any(isinstance(term, ast.Constant) and term.value == "git ls-files -z"
                for term in (node.left, *node.comparators))
        for node in nodes
    )
    compares_snapshots = any(
        isinstance(node, ast.Compare)
        and any(isinstance(op, ast.NotEq) for op in node.ops)
        and "expected.get(" in ast.unparse(node)
        and "current.get(" in ast.unparse(node)
        for node in nodes
    )
    fails_closed = any(isinstance(node, ast.Raise) for node in nodes)
    return calls_fresh and source_guard and compares_snapshots and fails_closed


def _coverage_invariant_note(
    action: str,
    invoked: list[str],
    reviewed_head: str,
    selected_paths: list[str],
    source_cache: dict[tuple[str, str], str],
) -> tuple[str, str]:
    """Explain what action-local code proves, never infer a repo-wide absence."""
    if not invoked:
        return "", "not-applicable"
    sources = [source_cache.get((reviewed_head, path), "") for path in selected_paths]
    if not any(
        "inventory = load_inventory(" in source or 'for surface in inventory["surfaces"]'
        in source for source in sources
    ):
        return "", "not-applicable"
    invocations = []
    for number, line in enumerate(action.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        invocations.extend(
            (number, match.group("path"))
            for match in _COMMAND.finditer(line)
            if match.group("path") in invoked
        )
    if not invocations:
        return "", "not-applicable"
    analyzer = next(
        ((number, path) for number, path in invocations
         if "analy" in PurePosixPath(path).name.lower()
         and not PurePosixPath(path).name.startswith("verify_")),
        invocations[0],
    )
    guard = next(
        ((number, path) for number, path in invocations
         if number < analyzer[0]
         and _git_freshness_comparator(source_cache.get((reviewed_head, path), ""))),
        None,
    )
    observed = (
        f"structural preflight in {PurePosixPath(guard[1]).name} (action line {guard[0]})"
        if guard else "not established by directly invoked steps in this action"
    )
    note = (
        "Coverage check (action-local, not a finding): analyzer "
        "exit/validation.success attests listed targets, not every Git-tracked file. "
        f"Git-backed manifest freshness BEFORE analysis: {observed}. "
        "Check new/omitted sources fail closed. Do not infer absent external "
        "guards or invent findings; anchor only supported changed-line defects.\n"
    )
    return note, ("pre-analyzer-structural-check" if guard else "not-evidenced-in-action")
