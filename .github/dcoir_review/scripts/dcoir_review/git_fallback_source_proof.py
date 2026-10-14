"""Exact-HEAD, narrowly proven Git-discovery fallback P1, independent of model output.

This intentionally recognizes an audited vulnerable verifier AST shape. Unknown
guards, source changes, missing context, hash drift, or other caller routes
abstain rather than publishing a speculative HIGH. Never executes fetched code.
"""
from __future__ import annotations

import ast
import hashlib
import re
from typing import Any, Callable

from dcoir_review.finding_verifier_contract import VERIFIER_MARKER
from dcoir_review.source_inventory_contract import (_logical_shell_commands, _python_command_sources, _potential_pre_analyzer_guard)

KIND = "git-discovery-fallback"
STATE = "source-backed-pending-independent-verification"
VERIFIER = "project_sources/collector/tools/verify_powershell_surface_inventory_ci.py"
ACTION = ".github/actions/run-psscriptanalyzer/action.yml"
OUTPUTS = "project_sources/collector/tools/powershell_surface_inventory_outputs.py"
DISCOVERY = "project_sources/collector/tools/powershell_surface_inventory_discovery.py"
ROUTES = (
    ".github/workflows/validate-on-pr.yml",
    ".github/workflows/validate-on-push.yml",
    ".github/workflows/reusable-validate-on-pr.yml",
    ".github/workflows/reusable-validate-on-push.yml",
    ".github/actions/verify-required-surfaces/action.yml",
    ".github/github_actions/tools/check_required_surfaces.py",
)
PATHS = tuple(sorted((VERIFIER, ACTION, OUTPUTS, DISCOVERY, *ROUTES)))
_SHA = re.compile(r"^[0-9a-f]{40}$")
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
# SHA256 of the audited historical verify_inventory source segment. This
# source fingerprint is independent of Python's AST serialization format.
_UNGUARDED_VERIFIER_SOURCE_SHA256 = "33f1ad0f23d65810b6217cf68cfd03bf3d8f3d56e86a7c3d808aeed1da790426"
# Audited Git-fallback discovery implementation. Unrecognized revisions abstain.
_FALLBACK_DISCOVERY_SHA = "9aad0c1d5b0c08fa4fd9c7fe206465cbabcfc569da87070ca0693dd7e61a5e91"
_MAX_SOURCE = 120_000


def _safe(text: Any) -> bool:
    return isinstance(text, str) and 0 < len(text) <= _MAX_SOURCE and "\x00" not in text


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _function(tree: ast.AST, name: str) -> ast.FunctionDef | None:
    return next((node for node in getattr(tree, "body", ())
                 if isinstance(node, ast.FunctionDef) and node.name == name), None)


def _verifier_source_fingerprint(source: str, fn: ast.FunctionDef | None = None) -> str:
    if fn is None:
        try:
            fn = _function(ast.parse(source), "verify_inventory")
        except (SyntaxError, ValueError, RecursionError):
            return ""
        if fn is None:
            return ""
    segment = ast.get_source_segment(source, fn)
    if segment is None:
        return ""
    normalized = segment.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _verifier_anchor(source: str) -> int:
    if not _safe(source):
        return 0
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return 0
    fn = _function(tree, "verify_inventory")
    if fn is None:
        return 0
    if _verifier_source_fingerprint(source, fn) != _UNGUARDED_VERIFIER_SOURCE_SHA256:
        return 0
    statements = [n for n in ast.walk(fn)
                  if isinstance(n, ast.Assign)
                  and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                  and n.targets[0].id == "current"
                  and isinstance(n.value, ast.Call)
                  and isinstance(n.value.func, ast.Name)
                  and n.value.func.id == "build_inventory"]
    return statements[0].lineno if len(statements) == 1 else 0


def _added_right_line(patch: str, source: str, target: int) -> bool:
    if not isinstance(patch, str) or len(patch) > 160_000 or target <= 0:
        return False
    source_lines = source.splitlines()
    right = None
    count = 0
    for raw in patch.splitlines():
        if raw.startswith("@@"):
            hunk = _HUNK.match(raw)
            right = int(hunk.group(1)) if hunk else None
        elif right is not None and raw.startswith("+") and not raw.startswith("+++"):
            if right == target and right <= len(source_lines) and raw[1:] == source_lines[right - 1]:
                count += 1
            right += 1
        elif right is not None and raw.startswith(" "):
            right += 1
    return count == 1


def _action_contract(action: str) -> bool:
    if not _safe(action):
        return False
    commands = []
    for start, _end, logical in _logical_shell_commands(action):
        paths, unresolved = _python_command_sources(logical)
        if unresolved:
            return False
        commands.extend((start, path) for path in paths)
    verifier = [line for line, path in commands if path == VERIFIER]
    analyzer = [line for line, path in commands if path ==
                "project_sources/collector/tools/run_powershell_analyzer.py"]
    if len(verifier) != 1 or len(analyzer) != 1 or verifier[0] >= analyzer[0]:
        return False
    prior = action.splitlines()[:verifier[0] - 1]
    # Only the original strict-error assignment may precede the verifier in
    # its PowerShell step. An unfamiliar guard is never assumed ineffective.
    run_blocks = [i for i, line in enumerate(prior) if line.strip() == "run: |"]
    if not run_blocks or sum(bool(re.match(r"^\s*-\s*name:", line)) for line in prior) != 1:
        return False
    prelude = [line.strip() for line in prior[run_blocks[-1] + 1:]
               if line.strip() and not line.lstrip().startswith("#")]
    if prelude != ["$ErrorActionPreference = 'Stop'"]:
        return False
    return (all(line >= verifier[0] for line, _ in commands)
            and not _potential_pre_analyzer_guard(prior))


def _outputs_contract(outputs: str) -> bool:
    if not _safe(outputs):
        return False
    try:
        fn = _function(ast.parse(outputs), "build_inventory")
    except (SyntaxError, ValueError, RecursionError):
        return False
    if fn is None:
        return False
    called = any(isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)
                 and node.func.id == "collect_surfaces" for node in ast.walk(fn))
    forwards = any(isinstance(node, ast.Dict)
                   and any(isinstance(key, ast.Constant)
                           and key.value == "source_of_truth"
                           and isinstance(val, ast.Name) and val.id == "source"
                           for key, val in zip(node.keys, node.values))
                   for node in ast.walk(fn))
    return called and forwards


def _exact_proof(sources: dict[str, str], reviewed_head: str) -> int:
    if not _SHA.fullmatch(reviewed_head) or set(sources) != set(PATHS):
        return 0
    if not all(_safe(item) for item in sources.values()):
        return 0
    anchor = _verifier_anchor(sources[VERIFIER])
    if not anchor or hashlib.sha256(sources[DISCOVERY].encode()).hexdigest() != _FALLBACK_DISCOVERY_SHA:
        return 0
    if not _outputs_contract(sources[OUTPUTS]) or not _action_contract(sources[ACTION]):
        return 0
    # Existing independent proof routines validate both active CI entry
    # points and their required-surfaces checks, not only a dormant action.
    from dcoir_review.source_inventory_promotion import _two_ci_routes, _required_surfaces_only
    if not _two_ci_routes(ACTION, sources):
        return 0
    if not _required_surfaces_only(
            sources[".github/actions/verify-required-surfaces/action.yml"],
            sources[".github/github_actions/tools/check_required_surfaces.py"]):
        return 0
    return anchor


def _sources(focus_source: str, head: str,
             fetch: Callable[[str, str], str]) -> dict[str, str] | None:
    if not _SHA.fullmatch(head) or not _safe(focus_source):
        return None
    found = {VERIFIER: focus_source}
    for path in PATHS:
        if path == VERIFIER:
            continue
        try:
            text = fetch(path, head)
        except Exception:
            return None
        if not _safe(text):
            return None
        found[path] = text
    return found


def attach_git_fallback_candidate(context: dict, head: str,
                                  fetch: Callable[[str, str], str]) -> None:
    if context.get("path") != VERIFIER or not isinstance(context.get("item"), dict):
        return
    item = context["item"]
    if item.get("filename") != VERIFIER:
        return
    source = context.get("text", "")
    anchor = _verifier_anchor(source)
    if not anchor or not _added_right_line(str(item.get("patch", "")), source, anchor):
        return
    # All fixed source witnesses are mandatory once a changed unsafe-shaped
    # verifier is identified. Do not silently publish a "clean" review if
    # exact-head GitHub content cannot be obtained.
    sources = _sources(source, head, fetch)
    if sources is None:
        raise RuntimeError("git-fallback-source-proof-unavailable")
    if _exact_proof(sources, head) != anchor:
        return
    item["_dcoir_git_fallback_candidate"] = {
        "path": VERIFIER,
        "line": anchor,
        "severity": "high",
        "_dcoir_candidate_kind": KIND,
        "_dcoir_candidate_state": STATE,
        "_dcoir_evidence": {
            "reviewed_head": head,
            "paths": list(PATHS),
            "hashes": {path: _sha(sources[path]) for path in PATHS},
        },
    }


def verify_git_fallback_candidate(candidate: dict, head: str,
                                  added_lines: dict[tuple[str, int], int],
                                  fetch: Callable[[str, str], str]) -> dict | None:
    if (not isinstance(candidate, dict)
            or candidate.get("_dcoir_candidate_kind") != KIND
            or candidate.get("_dcoir_candidate_state") != STATE
            or candidate.get("path") != VERIFIER
            or type(candidate.get("line")) is not int
            or not isinstance(added_lines, dict)):
        return None
    evidence = candidate.get("_dcoir_evidence")
    if (not isinstance(evidence, dict) or evidence.get("reviewed_head") != head
            or evidence.get("paths") != list(PATHS)
            or not isinstance(evidence.get("hashes"), dict)
            or set(evidence["hashes"]) != set(PATHS)):
        return None
    # Independently re-read every source at the reviewed immutable commit.
    try:
        sources = {path: fetch(path, head) for path in PATHS}
    except Exception:
        return None
    if not all(_safe(value) for value in sources.values()):
        return None
    if any(evidence["hashes"].get(path) != _sha(sources[path]) for path in PATHS):
        return None
    anchor = _exact_proof(sources, head)
    if not anchor or candidate["line"] != anchor or (VERIFIER, anchor) not in added_lines:
        return None
    return {
        "path": VERIFIER,
        "line": anchor,
        "severity": "high",
        "confidence": 0.95,
        "title": "Inventory freshness verification accepts Git-discovery fallback",
        "body": (
            "The added verifier calls build_inventory() and accepts a successful "
            "filesystem-fallback inventory without checking Git-tracked discovery "
            "provenance. The inspected inventory builder reports that provenance, "
            "and the active PR/push CI routes call this verifier before analysis. "
            "When Git discovery fails, tracked but absent files can be omitted "
            "while the stale checked-in inventory still compares equal."
        ),
        "validation": (
            "Simulate missing Git, a nonzero git ls-files exit, and a tracked "
            "PowerShell path absent from the working tree. Require the verifier "
            "to reject fallback before analysis; retain a successful Git control."
        ),
        "suggested_replacement": "",
        "_dcoir_verified_source_inventory": True,
        "_dcoir_verified_head": head,
        VERIFIER_MARKER: {
            "mode": "deterministic-source-inventory",
            "supported": True,
            "head_sha": head,
            "line": anchor,
        },
    }


__all__ = ["attach_git_fallback_candidate", "verify_git_fallback_candidate", "verify_candidate"]


def verify_candidate(candidate: dict, head: str,
                     added_lines: dict[tuple[str, int], int],
                     fetch: Callable[[str, str], str],
                     default: Callable) -> dict | None:
    """Dispatch only locally minted candidate kinds. Unknown kinds abstain."""
    if not isinstance(candidate, dict):
        return None
    kind = candidate.get("_dcoir_candidate_kind")
    if kind == KIND:
        return verify_git_fallback_candidate(candidate, head, added_lines, fetch)
    if kind is None:
        return default(candidate, head, added_lines, fetch)
    return None
