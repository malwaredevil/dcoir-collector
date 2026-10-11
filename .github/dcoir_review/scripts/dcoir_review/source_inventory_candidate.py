"""Conservative, source-backed PowerShell inventory coverage candidates.

This helper is a *candidate* detector, not permission to publish a finding.
It checks actual reviewed-HEAD caller code and changed-line anchors; it does
not execute repository files or infer a missing guard in unseen workflows.
"""
from __future__ import annotations

import ast
import hashlib
import re

from dcoir_review.source_inventory_contract import _COMMAND, _git_freshness_comparator

_HEAD = re.compile(r"^[0-9a-f]{40}$")
_CALLERS = (
    ".github/workflows/reusable-validate-on-pr.yml",
    ".github/workflows/reusable-validate-on-push.yml",
)
_ENTRIES = {
    ".github/workflows/validate-on-pr.yml": _CALLERS[0],
    ".github/workflows/validate-on-push.yml": _CALLERS[1],
}
_SURFACE_ACTION = ".github/actions/verify-required-surfaces/action.yml"
_SURFACE_SCRIPT = ".github/github_actions/tools/check_required_surfaces.py"
_CALL_LINE = re.compile(r"^\s*uses:\s+(\./\.github/actions/[A-Za-z0-9_./-]+)\s*$")
_MAX_TEXT = 120_000


def _structural_inventory_only(cli: str, selector: str) -> bool:
    """Recognize the root consumer contract using Python AST, not comments."""
    try:
        cl = ast.parse(cli)
        inv = ast.parse(selector)
    except (SyntaxError, ValueError):
        return False
    loaded = any(
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "inventory" for target in node.targets)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "load_inventory"
        for node in ast.walk(cl)
    )
    selected = any(
        isinstance(node, (ast.For, ast.AsyncFor))
        and isinstance(node.target, ast.Name) and node.target.id == "surface"
        and isinstance(node.iter, ast.Subscript)
        and isinstance(node.iter.value, ast.Name) and node.iter.value.id == "inventory"
        and isinstance(node.iter.slice, ast.Constant) and node.iter.slice.value == "surfaces"
        for node in ast.walk(inv)
    )
    return loaded and selected


def _existence_only_required_surfaces(action: str, checker: str) -> bool:
    """Recognize checked-path *existence* policy, not semantic file coverage."""
    if "check_required_surfaces.py --profile " not in action:
        return False
    try:
        tree = ast.parse(checker)
    except (SyntaxError, ValueError):
        return False
    path_exists = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute) and node.func.attr == "exists"
        for node in ast.walk(tree)
    )
    content_guard = any(
        isinstance(node, ast.Name) and node.id in {
            "load_inventory", "build_inventory", "check_inventory_freshness",
            "subprocess", "check_output", "check_call", "Popen",
        }
        for node in ast.walk(tree)
    ) or any(
        isinstance(node, ast.Constant) and isinstance(node.value, str)
        and "ls-files" in node.value.lower()
        for node in ast.walk(tree)
    )
    return path_exists and not content_guard and "git ls-files" not in checker


def _anchor_added_python_call(patch: str, source: str, analyzer_path: str) -> int:
    """Anchor only an actually added RIGHT-side command still at the reviewed HEAD."""
    if not patch or len(patch) > 160_000 or not patch.startswith("diff --git "):
        return 0
    lines = source.splitlines()
    hunk = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
    right = None
    anchors = []
    for line in patch.splitlines():
        if line.startswith("@@"):
            match = hunk.match(line)
            right = int(match.group(1)) if match else None
            continue
        if right is None or line.startswith(("diff --git ", "---", "+++")):
            continue
        if line.startswith("+"):
            body = line[1:]
            if (analyzer_path in body
                    and any(hit.group("path") == analyzer_path for hit in _COMMAND.finditer(body))
                    and 1 <= right <= len(lines)
                    and lines[right - 1] == body):
                anchors.append(right)
            right += 1
        elif line.startswith(" "):
            right += 1
        elif line.startswith("-"):
            continue
        elif line.startswith("\\"):
            continue
    return anchors[0] if len(anchors) == 1 else 0


def _callers_directly_use_action(action_path: str, callers: dict[str, str]) -> list[str]:
    expected = "./" + action_path.rsplit("/action.", 1)[0]
    # A reusable workflow alone may be dormant: require active PR/push entry.
    for entry, called in _ENTRIES.items():
        text = callers.get(entry, "")
        uses = re.compile(r"(?m)^\s*uses:\s+\./" + re.escape(called) + r"\s*$")
        if not isinstance(text, str) or len(text) > _MAX_TEXT or not uses.search(text):
            return []
    result = []
    for path in _CALLERS:
        body = callers.get(path, "")
        if not isinstance(body, str) or len(body) > _MAX_TEXT:
            return []
        matching = [
            (index, item.group(1))
            for index, line in enumerate(body.splitlines(), 1)
            if (item := _CALL_LINE.match(line)) and item.group(1) == expected
        ]
        if len(matching) != 1:
            return []
        match_line = matching[0][0]
        # A caller with a separate pre-action inventory verifier is protected.
        previous = "\n".join(body.splitlines()[: match_line - 1])
        if "uses: ./.github/actions/verify-required-surfaces" not in previous:
            return []
        if "verify_powershell_surface_inventory_ci.py" in previous or re.search(
            r"(?i)(?:verify|check|assert)[-_. ]+(?:powershell[-_. ]+)?(?:source[-_. ]+)?inventory",
            previous,
        ):
            return []
        result.append(path)
    return result


def detect_inventory_coverage_candidate(
    *,
    focus_path: str,
    head_source: str,
    patch: str,
    reviewed_head: str,
    dependencies: dict[str, str],
    caller_sources: dict[str, str],
    action_guard_status: str,
) -> dict | None:
    """Return *review-required* candidate only when all proof checks pass."""
    if not isinstance(reviewed_head, str) or not _HEAD.fullmatch(reviewed_head):
        return None
    if (not isinstance(focus_path, str)
            or not re.fullmatch(r"\.github/actions/[A-Za-z0-9_-]+/action\.ya?ml", focus_path)
            or not isinstance(head_source, str) or len(head_source) > _MAX_TEXT
            or not isinstance(patch, str) or not isinstance(dependencies, dict)
            or not isinstance(caller_sources, dict)):
        return None
    if action_guard_status != "not-evidenced-in-action":
        return None
    needed = {
        "project_sources/collector/tools/powershell_analyzer_cli.py",
        "project_sources/collector/tools/powershell_analyzer_inventory.py",
    }
    if not needed.issubset(dependencies):
        return None
    if not all(isinstance(value, str) and len(value) <= _MAX_TEXT for value in dependencies.values()):
        return None
    if not _structural_inventory_only(
        dependencies["project_sources/collector/tools/powershell_analyzer_cli.py"],
        dependencies["project_sources/collector/tools/powershell_analyzer_inventory.py"],
    ):
        return None
    analyzer_cmds = [
        (i, hit.group("path"))
        for i, line in enumerate(head_source.splitlines(), 1)
        if not line.lstrip().startswith("#")
        for hit in _COMMAND.finditer(line)
        if "run_powershell_analyzer" in hit.group("path")
    ]
    if len(analyzer_cmds) != 1:
        return None
    call_line, executable = analyzer_cmds[0]
    anchor = _anchor_added_python_call(patch, head_source, executable)
    if not anchor or anchor != call_line:
        return None
    # A directly invoked structurally supported preflight makes this safe.
    for i, line in enumerate(head_source.splitlines(), 1):
        if i >= anchor:
            break
        for match in _COMMAND.finditer(line):
            if _git_freshness_comparator(dependencies.get(match.group("path"), "")):
                return None
    if not _existence_only_required_surfaces(
        caller_sources.get(_SURFACE_ACTION, ""),
        caller_sources.get(_SURFACE_SCRIPT, ""),
    ):
        return None
    verified_callers = _callers_directly_use_action(focus_path, caller_sources)
    if len(verified_callers) != len(_CALLERS):
        return None
    trace_paths = [
        focus_path, *verified_callers, *sorted(_ENTRIES), _SURFACE_ACTION,
        _SURFACE_SCRIPT, *sorted(needed),
    ]
    hashes = {
        path: hashlib.sha256(
            (head_source if path == focus_path else
             caller_sources[path] if path in caller_sources else dependencies[path]).encode("utf-8")
        ).hexdigest()[:16] for path in trace_paths
    }
    return {
        "path": focus_path,
        "line": anchor,
        "severity": "high",
        "title": "New inventory-only scanner can omit tracked PowerShell sources",
        "body": (
            "This changed action invokes a Python analyzer whose target set comes from "
            "the checked-in inventory. A newly Git-tracked PowerShell file omitted "
            "from that inventory can escape the scan without failing the analyzer. "
            "Both inspected validation callers invoke this action; the preceding "
            "required-surfaces check only tests path existence. No Git-backed "
            "inventory freshness preflight is evidenced on these inspected routes. "
            "Check for any additional effective upstream gate before publication."
        ),
        "validation": (
            "Add a Git-tracked PowerShell script absent from the checked-in inventory "
            "and require the PR and push gates to fail before analysis; verify the "
            "real repaired action invokes a fail-closed inventory verifier first."
        ),
        "suggested_replacement": "",
        "_dcoir_candidate_state": "source-backed-pending-independent-verification",
        "_dcoir_evidence": {"reviewed_head": reviewed_head, "paths": trace_paths, "hashes": hashes},
    }

def attach_source_inventory_candidate(
    context: dict,
    reviewed_head: str,
    fetch_text,
    source_cache: dict[tuple[str, str], str],
) -> dict | None:
    """Attach HEAD-pinned caller-graph candidate to enriched first-pass context.

    Reads at most six additional known caller sources, using the existing
    authenticated GitHub fetch callback. A missing/ambiguous source means no
    candidate; never automatically publish an advisory candidate.
    """
    if not isinstance(context, dict) or not isinstance(context.get("item"), dict):
        return None
    item = context["item"]
    if item.get("_dcoir_source_coverage_guard") != "not-evidenced-in-action":
        return None
    focus_path = str(context.get("path", ""))
    if (not re.fullmatch(r"\.github/actions/[A-Za-z0-9_-]+/action\.ya?ml", focus_path)
            or "run_powershell_analyzer.py" not in str(item.get("patch", ""))):
        return None
    if not isinstance(item.get("patch"), str):
        return None
    if not isinstance(reviewed_head, str) or not _HEAD.fullmatch(reviewed_head):
        return None

    cli = "project_sources/collector/tools/powershell_analyzer_cli.py"
    selector = "project_sources/collector/tools/powershell_analyzer_inventory.py"
    deps = {path: source_cache.get((reviewed_head, path), "") for path in (cli, selector)}
    if not all(deps.values()):
        return None
    graph: dict[str, str] = {}
    for path in (*_CALLERS, *tuple(_ENTRIES), _SURFACE_ACTION, _SURFACE_SCRIPT):
        key = (reviewed_head, path)
        source = source_cache.get(key)
        if source is None:
            try:
                source = fetch_text(path, reviewed_head)
                if not isinstance(source, str) or len(source) > _MAX_TEXT or "\x00" in source:
                    return None
            except Exception:
                return None
            source_cache[key] = source
        graph[path] = source
    result = detect_inventory_coverage_candidate(
        focus_path=str(context.get("path", "")),
        head_source=str(context.get("text", "")),
        patch=item["patch"],
        reviewed_head=reviewed_head,
        dependencies=deps,
        caller_sources=graph,
        action_guard_status=item["_dcoir_source_coverage_guard"],
    )
    if result is not None:
        item["_dcoir_source_inventory_candidate"] = result
    return result


def pending_source_inventory_candidate_count(candidates: list[dict], findings: list[dict]) -> int:
    """Do not misclassify unrelated same-line or low-severity model prose as clearing a risk."""
    remaining = 0
    for candidate in candidates:
        accepted = False
        for found in findings:
            if not isinstance(found, dict):
                continue
            title_and_body = (
                str(found.get("title") or "") + " " + str(found.get("body") or "")
            ).lower()
            body_and_validation = (
                str(found.get("body") or "") + " " + str(found.get("validation") or "")
            ).lower()
            if (
                found.get("path") == candidate.get("path")
                and str(found.get("line") or "") == str(candidate.get("line") or "")
                and str(found.get("severity") or "").lower() in {"high", "critical"}
                and "inventory" in title_and_body
                and any(word in body_and_validation for word in (
                    "tracked", "omitted", "missing", "coverage", "unlisted"
                ))
            ):
                accepted = True
                break
        if not accepted:
            remaining += 1
    return remaining


__all__ = [
    "detect_inventory_coverage_candidate",
    "attach_source_inventory_candidate",
    "pending_source_inventory_candidate_count",
]
