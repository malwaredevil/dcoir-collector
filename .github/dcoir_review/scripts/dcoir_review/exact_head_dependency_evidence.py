"""Bounded exact-head code evidence for high-risk cross-file review contracts.

Only same-repository GitHub content at a validated immutable reviewed SHA is
accepted. Text is source evidence, never trusted instructions or proof of a
violation. The caller fetches via the existing authenticated GitHub API.
"""
from __future__ import annotations

import ast
from pathlib import PurePosixPath
import re
from typing import Any, Callable
from dcoir_review.dependency_evidence_budget import render_bounded_source_evidence
from dcoir_review.source_inventory_candidate import attach_source_inventory_candidate
from dcoir_review.source_inventory_contract import (
    MAX_SOURCE_CHARS,
    _python_command_sources,
    _python_module_sources,
    _logical_shell_commands,
    _coverage_invariant_note,
)

MAX_EVIDENCE_CHARS = 2100
MAX_FETCHES = 4
_SOURCE = re.compile(r"^[A-Za-z0-9_./-]+\.py$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_CONTRACT_NAMES = ("inventory", "cli", "manifest", "contract", "analyzer", "policy", "validate", "discovery")


def valid_source_path(path: str) -> bool:
    if not isinstance(path, str) or len(path) > 230 or not _SOURCE.fullmatch(path):
        return False
    if "\\" in path or "//" in path or path.startswith("/") or ":" in path:
        return False
    parts = path.split("/")
    if len(parts) < 2 or any(p in {"", ".", ".."} for p in parts):
        return False
    if not path.startswith(("project_sources/", ".github/")):
        return False
    return str(PurePosixPath(path)) == path


def _priority(path: str) -> tuple[int, str]:
    name = PurePosixPath(path).name.lower()
    for rank, token in enumerate(_CONTRACT_NAMES):
        if token in name:
            return rank, path
    return len(_CONTRACT_NAMES), path


def _direct_scripts(path: str, source: str) -> list[str]:
    if not path.startswith((".github/actions/", ".github/workflows/")):
        return []
    candidates = {
        executable for _start, _end, command in _logical_shell_commands(source)
        for executable in _python_command_sources(command)[0]
        if valid_source_path(executable)
    }
    # Prefer the actual analyzer over optional helpers, even if helpers have
    # higher-priority inventory/contract tokens in their names.
    return sorted(candidates, key=lambda item: (
        PurePosixPath(item).name != "run_powershell_analyzer.py",
        PurePosixPath(item).name != "run_analyzer.py",
        PurePosixPath(item).name.startswith(("verify_", "check_", "test_")),
        _priority(item),
    ))


def _sibling_imports(parent: str, source: str) -> list[str]:
    if len(source) > MAX_SOURCE_CHARS:
        return []
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    parent_dir = str(PurePosixPath(parent).parent)
    result: set[str] = set()
    for node in ast.walk(tree):
        modules = []
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(x.name for x in node.names)
        for module in modules:
            if "." in module:
                continue
            candidate = f"{parent_dir}/{module}.py"
            if candidate != parent and valid_source_path(candidate) and any(
                token in module.lower() for token in _CONTRACT_NAMES
            ):
                result.add(candidate)
    return sorted(result, key=_priority)


def build_exact_head_dependency_evidence(
    focus_path: str,
    focus_text: str,
    reviewed_head: str,
    fetch_text: Callable[[str, str], str],
    *,
    cache: dict[tuple[str, str], str] | None = None,
    max_chars: int = MAX_EVIDENCE_CHARS,
    max_fetches: int = MAX_FETCHES,
) -> dict[str, Any]:
    """Bounded one-hop source-import expansion. No network except fetch_text.

    No source-derived path can escape this repository. Content is never run.
    Returns an auditable result; absent/failing fetches are explicit.
    """
    result: dict[str, Any] = {
        "text": "", "paths": [], "direct_paths": [], "required_paths": [],
        "attempted": [], "errors": [], "truncated": False,
        "coverage_guard": "not-applicable", "omissions": [],
        "omission_count": 0, "used_chars": 0,
    }
    if not isinstance(reviewed_head, str) or not _SHA.fullmatch(reviewed_head):
        result["errors"].append("invalid-reviewed-head")
        return result
    yaml_focus = (
        isinstance(focus_path, str)
        and focus_path.startswith((".github/actions/", ".github/workflows/"))
        and focus_path.endswith((".yml", ".yaml"))
        and valid_source_path(focus_path.rsplit(".", 1)[0] + ".py")
    )
    if not (valid_source_path(focus_path) or yaml_focus) or not isinstance(focus_text, str):
        return result
    is_yaml = focus_path.startswith((".github/actions/", ".github/workflows/"))
    if not is_yaml and not any(
        token in PurePosixPath(focus_path).name.lower() for token in _CONTRACT_NAMES
    ):
        return result
    # Keep the new GitHub reads on source-coverage contracts. Generic CI
    # workflows with unrelated Python executables must not fail closed merely
    # because those scripts contain no inventory-relevant excerpt lines.
    if is_yaml and not re.search(
        r"powershell|psscriptanalyzer|inventory|manifest|source[- _]?coverage|static[- _]?analy",
        focus_path + "\n" + focus_text, re.IGNORECASE
    ):
        return result
    # A truncated shell parse must never masquerade as no executable.
    if is_yaml and len(focus_text) > MAX_SOURCE_CHARS:
        result["errors"].append("oversized-source-coverage-action")
        return result
    # An unresolved -m invocation may hide a repository-local executable.
    # Fail closed only for source-coverage-relevant YAML, never infer "clean".
    if is_yaml and (
        (focus_text.splitlines() and (
            len(focus_text.splitlines()[-1])
            - len(focus_text.splitlines()[-1].rstrip(chr(96)))
        ) % 2)
        or any(
            unresolved or (
                end > start and
                re.search(r"(?<![A-Za-z0-9_.])(?:python|py)\b", command, re.I)
                and not paths
            )
            for start, end, command in _logical_shell_commands(focus_text)
            for paths, unresolved in (_python_command_sources(command),)
        )
    ):
        result["errors"].append("unresolved-python-module-invocation")
        return result
    budget = min(MAX_EVIDENCE_CHARS, max(0, int(max_chars)))
    limit = min(MAX_FETCHES, max(0, int(max_fetches)))
    if budget < 600 or limit == 0:
        return result

    seeds = _direct_scripts(focus_path, focus_text)
    directly_invoked = bool(seeds)
    if not seeds and focus_path.endswith(".py"):
        seeds = _sibling_imports(focus_path, focus_text)
    if not seeds:
        return result
    result["direct_paths"] = list(seeds) if focus_path.startswith((".github/actions/", ".github/workflows/")) else []
    root = seeds[0]
    # Missing selected executables are fatal; unrelated direct helpers are
    # not source-evidence dependencies and must not abort the entire review.
    # An unknown pre-analyzer helper separately blocks HIGH promotion.
    candidates = [root]
    module_sources = {
        path for _start, _end, command in _logical_shell_commands(focus_text)
        for path in _python_module_sources(command)
    }
    candidates.extend(
        path for path in seeds[1:]
        if PurePosixPath(path).name.startswith("verify_") or path in module_sources
    )
    # Only executables directly invoked by YAML are mandatory. Sibling
    # imports from Python source are optional model context: a valid imported
    # module with no relevant excerpt must not abort an unrelated PR review.
    # Exact-head source/caller verification still gates published findings.
    result["required_paths"] = list(candidates) if directly_invoked else []
    if len(candidates) > limit:
        result["errors"].append("direct-script-budget-exceeded")
        result["truncated"] = True
        result["omission_count"] = len(candidates) - limit
        result["omissions"] = [
            {"path": path, "reason": "direct-script-budget-exceeded"}
            for path in candidates[limit:limit + 16]
        ]
        return result
    source_cache = cache if cache is not None else {}
    def read(path: str) -> str | None:
        key = (reviewed_head, path)
        if key in source_cache:
            return source_cache[key]
        result["attempted"].append(path)
        try:
            text = fetch_text(path, reviewed_head)
            if not isinstance(text, str) or len(text) > MAX_SOURCE_CHARS or "\x00" in text:
                raise ValueError("source not safe or bounded")
        except Exception:
            # A dependency read failure is explicit; never silently claim the
            # omitted producer/consumer relationship was validated.
            result["errors"].append(path)
            return None
        source_cache[key] = text
        return text

    root_source = read(root)
    if root_source is None:
        result["text"] = (
            "Exact-head dependency source was unavailable; do not infer the cross-file "
            "contract was validated or that omitted files are safe."
        )
        return result
    candidates.extend(_sibling_imports(root, root_source))
    render_bounded_source_evidence(
        root=root, root_source=root_source, candidates=candidates,
        limit=limit, budget=budget, reviewed_head=reviewed_head,
        focus_text=focus_text, seeds=seeds,
        source_cache=source_cache, result=result, read=read,
    )

    return result


def enrich_first_pass_contexts(contexts, reviewed_head, fetch_text, max_files=6):
    """Attach same-HEAD source evidence to bounded selected file prompts."""
    cache = {}
    enriched = 0
    # The model still reviews all changed files in its original order. Prioritize
    # the exact source-inventory action for the six source-evidence fetch slots:
    # a large PR must not starve the mandatory action behind ordinary imports.
    # Python sibling imports remain best-effort; action executables fail closed.
    action = ".github/actions/run-psscriptanalyzer/action.yml"
    def _evidence_priority(context: Any) -> int:
        if (isinstance(context, dict) and context.get("path") == action
                and isinstance(context.get("item"), dict)
                and context["item"].get("filename") == action):
            return 0
        return 1

    for context in sorted(contexts, key=_evidence_priority):
        if enriched >= max(0, min(6, int(max_files))):
            break
        if not isinstance(context, dict) or not isinstance(context.get("item"), dict):
            continue
        evidence = build_exact_head_dependency_evidence(
            str(context.get("path", "")), str(context.get("text", "")),
            reviewed_head, fetch_text, cache=cache,
        )
        # A directly invoked verifier is as important as the analyzer:
        # missing it could make a genuinely safe repair appear vulnerable.
        # Fail closed on unavailable *selected* source evidence, not unrelated helpers.
        if (any(error in evidence["errors"] for error in (
                    "direct-script-budget-exceeded", "coverage-invariant-exceeds-budget",
                    "unresolved-python-module-invocation",
                    "oversized-source-coverage-action"))
                or any(path not in evidence["paths"]
                       for path in evidence["required_paths"])):
            reason_codes = sorted(
                {err for err in evidence["errors"]
                 if err in {"direct-script-budget-exceeded",
                            "coverage-invariant-exceeds-budget",
                            "unresolved-python-module-invocation",
                            "oversized-source-coverage-action"}}
            )
            if any(path not in evidence["paths"] for path in evidence["required_paths"]):
                reason_codes.append("required-dependency-excerpt-unavailable")
            raise RuntimeError(
                "exact-head executable dependency unavailable for review: "
                + ",".join(reason_codes)
            )
        if not evidence["text"]:
            continue
        context["item"] = dict(context["item"])
        context["item"]["_dcoir_exact_head_dependency_evidence"] = evidence["text"]
        context["item"]["_dcoir_exact_head_dependency_paths"] = evidence["paths"]
        context["item"]["_dcoir_source_coverage_guard"] = evidence["coverage_guard"]
        context["item"]["_dcoir_exact_head_dependency_diagnostics"] = {
            "attempted": list(evidence["attempted"]),
            "omissions": list(evidence["omissions"]),
            "omission_count": evidence["omission_count"],
            "errors": list(evidence["errors"]),
            "truncated": evidence["truncated"],
            "evidence_chars": evidence["used_chars"],
        }
        attach_source_inventory_candidate(context, reviewed_head, fetch_text, cache)
        enriched += 1
    return enriched


__all__ = ["build_exact_head_dependency_evidence", "enrich_first_pass_contexts", "valid_source_path",
           "MAX_EVIDENCE_CHARS", "MAX_FETCHES"]
