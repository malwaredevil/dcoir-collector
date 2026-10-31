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
from dcoir_review.git_fallback_source_contract import (
    ACTION, KIND, PATHS, STATE, VERIFIER,
    _AUDITED_SOURCE_HASH_VERSIONS,
    _REQUIRED_SURFACES_ACTION,
    _REQUIRED_SURFACES_CHECK,
    _UNGUARDED_VERIFIER_FILE_SHA256,
    _UNGUARDED_VERIFIER_SOURCE_SHA256,
)

_SHA = re.compile(r"^[0-9a-f]{40}$")
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
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
    normalized_source = source.replace("\r\n", "\n").replace("\r", "\n")
    if hashlib.sha256(normalized_source.encode("utf-8")).hexdigest() != _UNGUARDED_VERIFIER_FILE_SHA256:
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


def _exact_proof(sources: dict[str, str], reviewed_head: str) -> int:
    if not _SHA.fullmatch(reviewed_head) or set(sources) != set(PATHS):
        return 0
    if not all(_safe(item) for item in sources.values()):
        return 0
    anchor = _verifier_anchor(sources[VERIFIER])
    expected_paths = set(PATHS) - {VERIFIER}
    if (not anchor
            or any(set(version) != expected_paths for version in _AUDITED_SOURCE_HASH_VERSIONS)):
        return 0
    version_matches = any(
        all(
            hashlib.sha256(
                sources[path].replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
            ).hexdigest() == expected_hash
            for path, expected_hash in version.items()
        )
        for version in _AUDITED_SOURCE_HASH_VERSIONS
    )
    if not version_matches:
        return 0
    # Existing independent proof routines validate both active CI entry
    # points and their required-surfaces checks, not only a dormant action.
    from dcoir_review.source_inventory_promotion import _two_ci_routes, _required_surfaces_only
    if not _two_ci_routes(ACTION, sources):
        return 0
    if not _required_surfaces_only(
            sources[_REQUIRED_SURFACES_ACTION], sources[_REQUIRED_SURFACES_CHECK]):
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
    except Exception as exc:
        raise RuntimeError("git-fallback-source-proof-unavailable") from exc
    if not all(_safe(value) for value in sources.values()):
        raise RuntimeError("git-fallback-source-proof-unavailable")
    if any(evidence["hashes"].get(path) != _sha(sources[path]) for path in PATHS):
        raise RuntimeError("git-fallback-source-proof-unavailable")
    anchor = _exact_proof(sources, head)
    if not anchor:
        raise RuntimeError("git-fallback-source-proof-unavailable")
    if candidate["line"] != anchor or (VERIFIER, anchor) not in added_lines:
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
