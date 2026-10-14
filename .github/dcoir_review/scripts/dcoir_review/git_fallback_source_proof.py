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

KIND = "git-discovery-fallback"
STATE = "source-backed-pending-independent-verification"
VERIFIER = "project_sources/collector/tools/verify_powershell_surface_inventory_ci.py"
ACTION = ".github/actions/run-psscriptanalyzer/action.yml"
OUTPUTS = "project_sources/collector/tools/powershell_surface_inventory_outputs.py"
DISCOVERY = "project_sources/collector/tools/powershell_surface_inventory_discovery.py"
ANALYZER = "project_sources/collector/tools/run_powershell_analyzer.py"
ANALYZER_CLI = "project_sources/collector/tools/powershell_analyzer_cli.py"
ANALYZER_INVENTORY = "project_sources/collector/tools/powershell_analyzer_inventory.py"
ANALYZER_CONTRACT = "project_sources/collector/tools/powershell_analyzer_contract.py"
ANALYZER_EXECUTION = "project_sources/collector/tools/powershell_analyzer_execution.py"
INVENTORY_COMMON = "project_sources/collector/tools/powershell_surface_inventory_common.py"
COLLECTOR_PATH_SAFETY = "project_sources/collector/tools/collector_tool_path_safety.py"
INVENTORY_VALIDATION = "project_sources/collector/tools/powershell_surface_inventory_validation.py"
INVENTORY_CLASSIFICATION = "project_sources/collector/tools/powershell_surface_inventory_classification.py"
INVENTORY_PROFILES = "project_sources/collector/tools/powershell_surface_inventory_profiles.py"
INVENTORY_CONTROLS = "project_sources/collector/tools/powershell_surface_inventory_controls.py"
INVENTORY_WORKFLOW_YAML = "project_sources/collector/tools/powershell_surface_inventory_workflow_yaml.py"
_REQUIRED_SURFACES_ACTION = ".github/actions/verify-required-surfaces/action.yml"
_REQUIRED_SURFACES_CHECK = ".github/github_actions/tools/check_required_surfaces.py"
ROUTES = (
    ".github/workflows/validate-on-pr.yml",
    ".github/workflows/validate-on-push.yml",
    ".github/workflows/reusable-validate-on-pr.yml",
    ".github/workflows/reusable-validate-on-push.yml",
    _REQUIRED_SURFACES_ACTION,
    _REQUIRED_SURFACES_CHECK,
)
# 22 mandatory audited source witnesses. Attachment fetches 21 additional
# sources (the changed verifier is already loaded); independent verification
# re-fetches all 22. The two passes must not share trusted read caches.
PATHS = tuple(sorted((
    VERIFIER, ACTION, OUTPUTS, DISCOVERY, ANALYZER, ANALYZER_CLI,
    ANALYZER_INVENTORY, ANALYZER_CONTRACT, ANALYZER_EXECUTION,
    INVENTORY_COMMON, COLLECTOR_PATH_SAFETY, INVENTORY_VALIDATION,
    INVENTORY_CLASSIFICATION, INVENTORY_PROFILES, INVENTORY_CONTROLS,
    INVENTORY_WORKFLOW_YAML, *ROUTES,
)))
_SHA = re.compile(r"^[0-9a-f]{40}$")
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
# SHA256 of the audited historical verify_inventory source segment. This
# source fingerprint is independent of Python's AST serialization format.
_UNGUARDED_VERIFIER_SOURCE_SHA256 = "33f1ad0f23d65810b6217cf68cfd03bf3d8f3d56e86a7c3d808aeed1da790426"
# Full source pin also covers decorators and module-level verifier bindings.
_UNGUARDED_VERIFIER_FILE_SHA256 = "6133b38fd55f0b42271dec81f638e0acfc19ce76034b58472b5c3c184da65e66"
_FALLBACK_DISCOVERY_SHA = "9aad0c1d5b0c08fa4fd9c7fe206465cbabcfc569da87070ca0693dd7e61a5e91"
# Exact historical caller/analysis sources; unknown gates or helper steps abstain.
_AUDITED_SOURCE_SHA256 = {
    ACTION: "09a62842cb1a33bfdaedefc40360c1df9c4799ec4786e9b473d969440a84eed7",
    OUTPUTS: "1615467f2934487de2bc58e9ff2fe0b53221ad74b407c7e6e69a4a5807b311d8",
    DISCOVERY: _FALLBACK_DISCOVERY_SHA,
    ANALYZER: "3362ae4374d23c66615c9458145ca58b9b0b8031c7b9e980bc17ce5f686cb86b",
    ANALYZER_CLI: "37af5f839ad84e963f140ad338b56df7a72fe07cdf051f366ccad05385bae49e",
    ANALYZER_INVENTORY: "fb0d604a3a7631714437a53bb1425755d9387037f381ee27e8c0143d5f33a058",
    ANALYZER_CONTRACT: "1dca2587eee48fba0c0bc476254189004bf75cf7cdb4e5d2ac356504cdaff9cf",
    ANALYZER_EXECUTION: "88d5872d528ce363d90e2e34cba74061a03f65755c61a501c12d25c197681854",
    INVENTORY_COMMON: "d9fe1fdfbf87002d2a437f491eb8602a2f7889237da3213739a858f3e2778562",
    COLLECTOR_PATH_SAFETY: "5aebb6011407968c74ffe5ea0ebd40d38be7ee01772ae9a83c4fad452cb41b76",
    INVENTORY_VALIDATION: "7c70a7dc8cdb583717871db66adf61399a77a0c4b176f96a74821643924ad0d0",
    INVENTORY_CLASSIFICATION: "f41c097e63852bd7a6b5d11b0abd55a2c390d0df70bec73a12e46fd992ae8f3b",
    INVENTORY_PROFILES: "a92f77806aebf5f4209a77e5e40cfdb99d89991e5fff6d99b24f17f96fd57cbd",
    INVENTORY_CONTROLS: "1456d8a83b60e56d5e467384dd7dae63a52d89e6bf9c1be7bb4dab61698c0a68",
    INVENTORY_WORKFLOW_YAML: "af540a1b8d973bd73768fd347c17d53b4a388484f132614c8420740f74ccd5e3",
    _REQUIRED_SURFACES_ACTION: "57b4fb5fe5ee197b31c95d7dc0cff7425bb9a18f1739a21f2afb3871cb270db6",
    _REQUIRED_SURFACES_CHECK: "7bae51c61a42635a35e1b2c7119af2e3546f46d2486eec77b961d8c425ab08bc",
    ".github/workflows/validate-on-pr.yml": "2fe1df3acb85d218c754e8e771603cead9cad2664282b6f54a22e1c3ba277330",
    ".github/workflows/validate-on-push.yml": "212c059b4609ed73defc8f20c0a1806e3b5f72eac36cd75f2bb2a7147be2ddb1",
    ".github/workflows/reusable-validate-on-pr.yml": "c08ebc8fa2523a33707b305f39c11fac73dd544499b791c9df4fb1563d4e0833",
    ".github/workflows/reusable-validate-on-push.yml": "36d9562023641a65f5e0b28b8fd92ad4b63379b5e48c059b810bb45f92ef2448",
}
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
    if not anchor or set(_AUDITED_SOURCE_SHA256) != set(PATHS) - {VERIFIER}:
        return 0
    for path, expected_hash in _AUDITED_SOURCE_SHA256.items():
        normalized = sources[path].replace("\r\n", "\n").replace("\r", "\n")
        if hashlib.sha256(normalized.encode("utf-8")).hexdigest() != expected_hash:
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
