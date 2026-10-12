"""Fail-closed independent evidence gate for inventory candidate publication.

Re-fetches exact-HEAD CI sources; checks both caller routes and changed lines.
Never executes fetched source or invokes a provider.
"""
from __future__ import annotations

import ast
import hashlib
import re
from typing import Any, Callable

from dcoir_review.finding_verifier_contract import VERIFIER_MARKER
from dcoir_review.source_inventory_contract import (
    _python_command_sources, _logical_shell_commands, _potential_pre_analyzer_guard,
)

_SOURCE_CLI = "project_sources/collector/tools/powershell_analyzer_cli.py"
_SOURCE_SELECTOR = "project_sources/collector/tools/powershell_analyzer_inventory.py"
_RUNNER = "project_sources/collector/tools/run_powershell_analyzer.py"
_PR_ENTRY = ".github/workflows/validate-on-pr.yml"
_PUSH_ENTRY = ".github/workflows/validate-on-push.yml"
_PR_CALL = ".github/workflows/reusable-validate-on-pr.yml"
_PUSH_CALL = ".github/workflows/reusable-validate-on-push.yml"
_REQUIRED_ACTION = ".github/actions/verify-required-surfaces/action.yml"
_REQUIRED_CHECK = ".github/github_actions/tools/check_required_surfaces.py"
_EXPECTED_DEPENDENCIES = frozenset((
    _PR_ENTRY, _PUSH_ENTRY, _PR_CALL, _PUSH_CALL, _REQUIRED_ACTION,
    _REQUIRED_CHECK, _SOURCE_CLI, _SOURCE_SELECTOR,
))
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_ACTION_PATH = re.compile(r"^\.github/actions/[A-Za-z0-9_-]+/action\.ya?ml$")
_MAX_SOURCE = 120_000
_MAX_CANDIDATES = 2


def _source(path: str, sha: str, fetch: Callable[[str, str], str]) -> str | None:
    try:
        contents = fetch(path, sha)
    except Exception:
        return None
    if (not isinstance(contents, str) or not contents or
            len(contents) > _MAX_SOURCE or "\x00" in contents):
        return None
    return contents


def _has_import(tree: ast.AST, module: str, symbol: str) -> bool:
    return any(
        isinstance(n, ast.ImportFrom) and n.module == module
        and any(a.name == symbol for a in n.names) for n in ast.walk(tree)
    )


def _python_target_selection(cli: str, inventory: str, runner: str) -> bool:
    try:
        cl = ast.parse(cli)
        inv = ast.parse(inventory)
        run = ast.parse(runner)
    except (SyntaxError, ValueError, RecursionError):
        return False
    if not (_has_import(run, "powershell_analyzer_cli", "main") and
            _has_import(cl, "powershell_analyzer_inventory", "load_inventory") and
            _has_import(cl, "powershell_analyzer_inventory", "build_target_sets")):
        return False
    reporter = next(
        (n for n in cl.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
         and n.name == "build_report"), None
    )
    selector = next(
        (n for n in inv.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
         and n.name == "build_target_sets"), None
    )
    if reporter is None or selector is None:
        return False
    has_manifest_load = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "load_inventory" for n in ast.walk(reporter)
    )
    has_inventory_call = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "build_target_sets"
        and any(k.arg == "inventory" for k in n.keywords)
        for n in ast.walk(reporter)
    )
    enumerates_only_manifest = any(
        isinstance(n, ast.For)
        and isinstance(n.iter, ast.Subscript)
        and isinstance(n.iter.value, ast.Name) and n.iter.value.id == "inventory"
        and isinstance(n.iter.slice, ast.Constant) and n.iter.slice.value == "surfaces"
        for n in ast.walk(selector)
    )
    no_git_discovery = not any(
        isinstance(n, ast.Constant) and isinstance(n.value, str)
        and "ls-files" in n.value for tree in (cl, inv, run) for n in ast.walk(tree)
    )
    return has_manifest_load and has_inventory_call and enumerates_only_manifest and no_git_discovery


def _required_surfaces_only(action: str, checker: str) -> bool:
    if not re.search(
        r"(?m)^\s*python\s+\.github/github_actions/tools/check_required_surfaces\.py\s+--profile\b",
        action,
    ):
        return False
    try:
        script = ast.parse(checker)
    except (SyntaxError, ValueError, RecursionError):
        return False
    main = next(
        (n for n in script.body if isinstance(n, ast.FunctionDef) and n.name == "main"),
        None,
    )
    if main is None:
        return False
    checks_existence = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "exists" for n in ast.walk(main)
    )
    dynamic_inventory = any(
        (isinstance(n, ast.Name) and n.id in {
            "build_inventory", "load_inventory", "subprocess", "check_output",
            "Popen", "run", "ls_files",
        }) or (isinstance(n, ast.Import) and any(
            a.name in {"subprocess", "git"} for a in n.names
        )) or (isinstance(n, ast.ImportFrom) and n.module in {"subprocess", "git"})
        for n in ast.walk(script)
    ) or any(
        isinstance(n, ast.Constant) and isinstance(n.value, str)
        and "ls-files" in n.value for n in ast.walk(script)
    )
    return checks_existence and not dynamic_inventory


def _two_ci_routes(focus_path: str, sources: dict[str, str]) -> bool:
    action_use = "./" + focus_path.rsplit("/action.", 1)[0]
    for entry, caller, event in (
        (_PR_ENTRY, _PR_CALL, "pull_request"),
        (_PUSH_ENTRY, _PUSH_CALL, "push"),
    ):
        source = sources[entry]
        if re.search(r'(?im)^[ \t]*if:[ \t]*["\']?false["\']?[ \t]*$', source):
            return False
        trigger = re.search(r"(?m)^\s*" + event + r":\s*$", source)
        calls_reusable = re.findall(
            r"(?m)^\s*uses:\s+(\./\.github/workflows/[A-Za-z0-9_./-]+)\s*$",
            source,
        )
        if not trigger or calls_reusable.count("./" + caller) != 1:
            return False
        if re.search(r'(?im)^[ \t]*if:[ \t]*["\']?false["\']?[ \t]*$', sources[caller]):
            return False
        lines = sources[caller].splitlines()
        action_lines = [
            i for i, line in enumerate(lines)
            if re.fullmatch(r"\s*uses:\s+" + re.escape(action_use) + r"\s*", line)
        ]
        if len(action_lines) != 1:
            return False
        before = "\n".join(lines[:action_lines[0]])
        if "uses: ./.github/actions/verify-required-surfaces" not in before:
            return False
        if re.search(
            r"(?i)(?:verify[-_ ]+(?:source[-_ ]+)?inventory|"
            r"check[-_ ]+(?:powershell[-_ ]+)?inventory|git\s+ls-files)",
            before,
        ):
            return False
    return True


def verify_source_inventory_for_promotion(
    candidate: dict[str, Any],
    reviewed_head: str,
    added_lines: dict[tuple[str, int], int],
    fetch_text: Callable[[str, str], str],
) -> dict[str, Any] | None:
    """Return whitelisted finding fields only when independent evidence agrees."""
    if (not isinstance(candidate, dict) or not isinstance(reviewed_head, str)
            or not _FULL_SHA.fullmatch(reviewed_head)
            or candidate.get("_dcoir_candidate_state") !=
                "source-backed-pending-independent-verification"):
        return None
    path = candidate.get("path")
    line = candidate.get("line")
    evidence = candidate.get("_dcoir_evidence")
    if (not isinstance(path, str) or not _ACTION_PATH.fullmatch(path)
            or type(line) is not int or line <= 0
            or (path, line) not in added_lines
            or not isinstance(evidence, dict)
            or evidence.get("reviewed_head") != reviewed_head):
        return None
    paths = evidence.get("paths")
    hashes = evidence.get("hashes")
    required = _EXPECTED_DEPENDENCIES | {path}
    if (not isinstance(paths, list) or set(paths) != required
            or len(paths) != len(required) or not isinstance(hashes, dict)
            or set(hashes) != required):
        return None
    sources: dict[str, str] = {}
    for source_path in (*sorted(required), _RUNNER):
        source = _source(source_path, reviewed_head, fetch_text)
        if source is None:
            return None
        sources[source_path] = source
        if source_path != _RUNNER:
            claimed = hashes.get(source_path)
            if (not isinstance(claimed, str) or
                    not re.fullmatch(r"[0-9a-f]{16}", claimed) or
                    hashlib.sha256(source.encode("utf-8")).hexdigest()[:16] != claimed):
                return None
    action = sources[path].splitlines()
    # Verify exact-head Python source even for continued module commands.
    if line > len(action):
        return None
    logical = next((
        command for start, _end, command in _logical_shell_commands(sources[path])
        if start == line
    ), None)
    if logical is None:
        return None
    executed, unresolved = _python_command_sources(logical)
    if unresolved or _RUNNER not in executed:
        return None
    if _potential_pre_analyzer_guard(action[:line-1]):
        return None
    if not _two_ci_routes(path, sources):
        return None
    if not _required_surfaces_only(sources[_REQUIRED_ACTION], sources[_REQUIRED_CHECK]):
        return None
    if not _python_target_selection(
        sources[_SOURCE_CLI], sources[_SOURCE_SELECTOR], sources[_RUNNER]
    ):
        return None
    return {
        "path": path,
        "line": line,
        "severity": "high",
        "confidence": 0.95,
        "title": "Inventory-only PowerShell analysis can skip new tracked sources",
        "body": (
            "This added action runs a Python analyzer that builds its target set "
            "from inventory-listed surfaces, not fresh Git-tracked source discovery. "
            "Both inspected PR and push workflow routes execute this action and "
            "their preceding required-surfaces check only tests path existence. "
            "No fail-closed tracked-source inventory comparison precedes this call "
            "on either inspected route. Newly tracked PowerShell scripts absent "
            "from the inventory can therefore be silently skipped."
        ),
        "validation": (
            "Add a newly tracked PowerShell script missing from the checked-in "
            "inventory and ensure both CI routes fail before analysis. Run the "
            "Git-backed surface inventory freshness verifier before this analyzer."
        ),
        "suggested_replacement": "",
        "_dcoir_verified_source_inventory": True,
        "_dcoir_verified_head": reviewed_head,
        VERIFIER_MARKER: {
            "mode": "deterministic-source-inventory",
            "supported": True,
            "head_sha": reviewed_head,
            "line": line,
        },
    }


def verify_bounded_inventory_candidates(
    candidates: Any, head: str, added_lines: dict[tuple[str, int], int],
    fetch_text: Callable[[str, str], str],
) -> tuple[list[dict[str, Any]], int]:
    """Bound verification fanout. Never trust candidate-originated filenames."""
    if not isinstance(candidates, list):
        return [], 0
    if len(candidates) > _MAX_CANDIDATES:
        return [], len(candidates)
    memo: dict[tuple[str, str], str] = {}

    def cached(path: str, ref: str) -> str:
        key = (path, ref)
        if key not in memo:
            memo[key] = fetch_text(path, ref)
        return memo[key]

    verified = []
    failed = 0
    for candidate in candidates:
        finding = verify_source_inventory_for_promotion(
            candidate, head, added_lines, cached
        )
        if finding is None:
            failed += 1
        elif not any((f["path"], f["line"]) == (finding["path"], finding["line"]) for f in verified):
            verified.append(finding)
    return verified, failed


def integrate_verified_inventory_findings(
    result: dict[str, Any],
    findings: list[dict[str, Any]],
    config: Any,
    line_index: dict[tuple[str, int], int],
    reviewed_head: str,
    fetch_text: Callable[[str, str], str],
    hardened: Any,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Apply validated candidates after model normalizer and fix synthesis."""
    candidates = result.pop("_dcoir_source_inventory_candidates", [])
    if not candidates:
        return findings, {"advisories": 0, "verified": 0, "promoted": 0, "pending": 0}
    verified, failed = verify_bounded_inventory_candidates(
        candidates, reviewed_head, line_index, fetch_text
    )
    final = list(findings)
    promoted = 0
    existing = 0
    pending = failed
    cap = max(0, int(getattr(config, "max_inline_comments", 12)))
    for item in verified:
        try:
            anchored, unanchored = hardened.split_findings(
                {"summary": "", "findings": [dict(item)]}, config, line_index
            )
        except Exception:
            anchored, unanchored = [], []
        if len(anchored) != 1 or unanchored:
            pending += 1
            continue
        proof = anchored[0]
        prior = [
            f for f in final if isinstance(f, dict)
            and str(f.get("path") or "") == proof["path"]
            and str(f.get("line") or "") == str(proof["line"])
        ]
        if prior:
            # Do not overwrite unrelated same-line model findings.
            from dcoir_review.source_inventory_candidate import (
                pending_source_inventory_candidate_count,
            )
            if pending_source_inventory_candidate_count([item], prior) == 0:
                existing += 1
            else:
                pending += 1
            continue
        if len(final) >= cap:
            pending += 1
            continue
        final.append(dict(proof))
        promoted += 1
    if promoted:
        result["summary"] = (
            f"Independent source-backed verification identified {promoted} "
            "HIGH-severity changed-line PowerShell inventory coverage defect(s). "
            "The deterministic proof supersedes any contrary first-pass model "
            "assessment; no extra model or fix-synthesis request was made."
        )
    if pending:
        warning = (
            f"{pending} source-inventory coverage candidate(s) could not pass "
            "independent proof, ordinary finding gates, or publication budget. "
            "These remain UNRESOLVED, not cleared or published."
        )
        result["summary"] = (
            str(result.get("summary", "") or "").strip() + "\n\n" + warning
        ).strip()
    return final, {
        "advisories": len(candidates),
        "verified": len(verified),
        "promoted": promoted,
        "already_found": existing,
        "pending": pending,
    }


__all__ = [
    "verify_source_inventory_for_promotion",
    "verify_bounded_inventory_candidates",
    "integrate_verified_inventory_findings",
]
