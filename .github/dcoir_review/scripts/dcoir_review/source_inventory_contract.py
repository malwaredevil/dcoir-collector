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
_PYTHON_INTERPRETER = re.compile(
    r"(?<![A-Za-z0-9_.])"
    r"(?:python(?:3(?:\.\d+)?)?(?:\.exe)?|py(?:\.exe)?(?:\s+-3(?:\.\d+)?)?)",
    re.IGNORECASE,
)
_MODULE_RUN = re.compile(
    _PYTHON_INTERPRETER.pattern
    + r"""(?:\s+-(?:B|I|E|s|S|u|O)){0,3}\s+(?:-m|(?P<opt_quote>["'])-m(?P=opt_quote))(?=\s|[A-Za-z_]|["']|$)""",
    re.IGNORECASE,
)
_MODULE_NAME = re.compile(
    r"""^\s*(?P<quote>["']?)(?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)(?P=quote)(?=$|\s|;|\||#)"""
)


def _python_command_sources(line: str) -> tuple[list[str], bool]:
    """Return GitHub-repo Python sources invoked on this line and unknown modules.

    No commands or imported modules are executed. Only syntactically bounded
    repository modules are translated to .py paths. Missing/variable/external
    module targets must fail closed for relevant security Action evidence.
    """
    if not isinstance(line, str) or line.lstrip().startswith("#"):
        return [], False
    executions = [(match.start(), match.group("path")) for match in _COMMAND.finditer(line)]
    unresolved = False
    recognized = list(_MODULE_RUN.finditer(line))
    recognized_starts = {match.start() for match in recognized}
    # Unsupported interpreter switches must not silently hide module execution.
    # Avoid claiming a clean review when a relevant Action has `python -X ...
    # -m` or an equivalent module invocation we cannot resolve safely.
    for interpreter in _PYTHON_INTERPRETER.finditer(line):
        if interpreter.start() in recognized_starts:
            continue
        tail = re.split(r"[;|#]", line[interpreter.end():], maxsplit=1)[0][:180]
        if re.search(r"""(?<![A-Za-z0-9_.-])["']?-m""", tail):
            unresolved = True
    for match in recognized:
        name_match = _MODULE_NAME.match(line[match.end():])
        if name_match is None:
            unresolved = True
            continue
        path = name_match.group("name").replace(".", "/") + ".py"
        if (not path.startswith("project_sources/")
                or len(path) > 230
                or ".." in path):
            unresolved = True
            continue
        executions.append((match.start(), path))
    executions.sort(key=lambda item: item[0])
    return [path for _, path in executions], unresolved


def _python_module_sources(line: str) -> list[str]:
    """Return only statically resolvable module-mode source paths."""
    invoked, _ = _python_command_sources(line)
    explicit = {m.group("path") for m in _COMMAND.finditer(line)}
    return [path for path in invoked if path not in explicit]


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


def _potential_pre_analyzer_guard(prior_lines: list[str]) -> bool:
    """Abstain if earlier commands might supply an unexamined safety gate."""
    before = re.sub(r"\x60\r?\n[ \t]*", "", "\n".join(prior_lines))
    if re.search(
        r"(?im)(?:\bls-files\b|\bCompare-Object\b|"
        r"\bGet-ChildItem\b[^\n]*\.(?:ps1|psm1|psd1)\b|"
        r"(?:Get-Content|ConvertFrom-Json)[^\n]*(?:inventory|surfaces)|"
        r"\b(?:python|py)\s+[^\n]*\.py\b|"
        r"^\s*pwsh\s+[^\n]*(?:verify|check)[^\n]*inventory)",
        before,
    ):
        return True
    return any(any(_python_command_sources(line)) for line in prior_lines)


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
            (number, path)
            for path in _python_command_sources(line)[0]
            if path in invoked
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
