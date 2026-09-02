"""DCOIR Review v41 Architecture-B incremental review frontier.

Issue #458 / approved #464 Architecture B requires ordinary follow-up reviews to
analyze the last successfully reviewed DCOIR head -> current PR head rather than
replaying the cumulative PR base -> current head surface.  This runtime overlay
implements only that state/frontier slice.  It deliberately leaves the governed
Opus/Sol semantic model stack and downstream detector/challenger/adjudicator/
verifier/repair behavior unchanged for the first architecture benchmark.

Safety contract:
- only a prior DCOIR context review carrying the same architecture contract
  marker is eligible for incremental reuse;
- the prior review commit must be an ancestor of the current head according to
  GitHub's compare endpoint (status=ahead and merge-base==prior head);
- deep/first-pass reviews remain cumulative;
- missing, stale, divergent, oversized, malformed, or failed compare evidence
  falls back to the existing cumulative PR scope;
- only the initial semantic-scope diff fetch may be incremental; later diff
  readbacks (for example repair/publication anchoring) remain cumulative PR diff;
- review-scope provenance is added to context/debug evidence;
- no branch write, commit, or autonomous remediation capability is added.
"""

from __future__ import annotations

import copy
import os
import urllib.parse
from typing import Any


VERSION = "v41"
ARCHITECTURE_CONTRACT = "architecture-b-v1"
ARCHITECTURE_CONTRACT_MARKER = f"DCOIR review contract: {ARCHITECTURE_CONTRACT}"
SCOPE_CACHE_ATTR = "_dcoir_v41_review_scope"
INITIAL_DIFF_CONSUMED_KEY = "_initial_semantic_diff_consumed"

_GET_DIFF_STORAGE = "_dcoir_v41_original_get_pr_diff"
_LIST_FILES_STORAGE = "_dcoir_v41_original_list_files"
_PRIOR_STORAGE = "_dcoir_v41_original_has_prior_successful_context_review"
_DEEP_CONTEXT_STORAGE = "_dcoir_v41_original_build_deep_context_block"
_DEBUG_JSON_STORAGE = "_dcoir_v41_original_write_debug_json_artifact_safely"

_LAST_SCOPE: dict[str, Any] = {}


def _review_markers(module: Any) -> tuple[str, ...]:
    return (module.base.MARKER, *getattr(module.base, "LEGACY_MARKERS", ()))


def _latest_compatible_context_review(module: Any, gh: Any, pr_number: int) -> dict[str, Any] | None:
    """Return the newest successful DCOIR context review compatible with v41."""
    markers = _review_markers(module)
    reviews = module.list_pr_reviews(gh, pr_number)
    for review in reversed(reviews):
        body = str(review.get("body", "") or "")
        commit_id = str(review.get("commit_id", "") or "").strip()
        if not commit_id:
            continue
        if not any(marker in body for marker in markers):
            continue
        if module.CONTEXT_REVIEW_MARKER not in body:
            continue
        if ARCHITECTURE_CONTRACT_MARKER not in body:
            continue
        return review
    return None


def _scope_record(
    *,
    source: str,
    prior_head: str,
    current_head: str,
    files: list[dict[str, Any]],
    diff: str,
    review_mode: str,
    fallback_reason: str = "",
    compare_status: str = "",
) -> dict[str, Any]:
    return {
        "source": source,
        "prior_reviewed_head_sha": prior_head,
        "current_head_sha": current_head,
        "review_mode": review_mode,
        "fallback_reason": fallback_reason,
        "compare_status": compare_status,
        "files": files,
        "diff": diff,
    }


def _cumulative_scope(
    module: Any,
    gh: Any,
    pr_number: int,
    current_head: str,
    review_mode: str,
    prior_head: str,
    reason: str,
    original_get_pr_diff: Any,
    original_list_files: Any,
) -> dict[str, Any]:
    diff = original_get_pr_diff(gh, pr_number)
    files = original_list_files(gh, pr_number)
    return _scope_record(
        source="cumulative-full-pr",
        prior_head=prior_head,
        current_head=current_head,
        files=files,
        diff=diff,
        review_mode=review_mode,
        fallback_reason=reason,
    )


def _resolve_review_scope(
    module: Any,
    gh: Any,
    pr_number: int,
    original_get_pr_diff: Any,
    original_list_files: Any,
) -> dict[str, Any]:
    """Resolve incremental scope or conservatively fall back to cumulative PR scope."""
    cached = getattr(gh, SCOPE_CACHE_ATTR, None)
    if isinstance(cached, dict) and int(cached.get("pr_number", -1)) == pr_number:
        return cached

    pr = gh.get_pr(pr_number)
    current_head = str(pr.get("head", {}).get("sha", "") or "").strip()
    if not current_head:
        scope = _cumulative_scope(
            module,
            gh,
            pr_number,
            "",
            "unknown",
            "",
            "current PR head SHA unavailable",
            original_get_pr_diff,
            original_list_files,
        )
        scope["pr_number"] = pr_number
        setattr(gh, SCOPE_CACHE_ATTR, scope)
        return scope

    try:
        prior_review = _latest_compatible_context_review(module, gh, pr_number)
    except Exception as exc:
        scope = _cumulative_scope(
            module,
            gh,
            pr_number,
            current_head,
            "unknown",
            "",
            f"compatible prior-review readback failed: {str(exc)[:240]}",
            original_get_pr_diff,
            original_list_files,
        )
        scope["pr_number"] = pr_number
        setattr(gh, SCOPE_CACHE_ATTR, scope)
        return scope

    prior_head = str((prior_review or {}).get("commit_id", "") or "").strip()
    config_path = os.environ.get(
        "OPENROUTER_REVIEW_CONFIG",
        ".github/dcoir_review/openrouter-pr-review-pareto.yml",
    )
    config = module.load_pareto_context_config(config_path)
    body = os.environ.get("TRIGGER_COMMENT_BODY", "")
    command = module.hardened.matching_command(body, config.commands)
    if not command:
        review_mode = "unknown"
    else:
        review_mode = module.review_mode_for_command(body, command, config, bool(prior_head))

    if review_mode != "diff":
        reason = f"{review_mode or 'unknown'} requires cumulative review scope"
        scope = _cumulative_scope(
            module,
            gh,
            pr_number,
            current_head,
            review_mode,
            prior_head,
            reason,
            original_get_pr_diff,
            original_list_files,
        )
        scope["pr_number"] = pr_number
        setattr(gh, SCOPE_CACHE_ATTR, scope)
        return scope

    if not prior_head:
        scope = _cumulative_scope(
            module,
            gh,
            pr_number,
            current_head,
            review_mode,
            "",
            f"no prior compatible {ARCHITECTURE_CONTRACT} DCOIR context review",
            original_get_pr_diff,
            original_list_files,
        )
        scope["pr_number"] = pr_number
        setattr(gh, SCOPE_CACHE_ATTR, scope)
        return scope

    if prior_head == current_head:
        scope = _cumulative_scope(
            module,
            gh,
            pr_number,
            current_head,
            review_mode,
            prior_head,
            "prior compatible review already targets current head",
            original_get_pr_diff,
            original_list_files,
        )
        scope["pr_number"] = pr_number
        setattr(gh, SCOPE_CACHE_ATTR, scope)
        return scope

    encoded_base = urllib.parse.quote(prior_head, safe="")
    encoded_head = urllib.parse.quote(current_head, safe="")
    compare_path = f"/repos/{gh.repo}/compare/{encoded_base}...{encoded_head}"

    try:
        comparison = gh.request("GET", f"{compare_path}?per_page=1&page=1")
        if not isinstance(comparison, dict):
            raise RuntimeError("GitHub compare did not return an object")
        compare_status = str(comparison.get("status", "") or "").strip().lower()
        merge_base = str(comparison.get("merge_base_commit", {}).get("sha", "") or "").strip()
        files = comparison.get("files", [])
        if compare_status != "ahead":
            raise RuntimeError(f"compare status is {compare_status or 'missing'}, not ahead")
        if merge_base != prior_head:
            raise RuntimeError("prior reviewed head is not the exact compare merge base")
        if not isinstance(files, list):
            raise RuntimeError("compare files is not a list")
        max_files = int(getattr(config, "max_files", 100))
        if len(files) > max_files:
            raise RuntimeError(
                f"incremental compare contains {len(files)} files, exceeding governed max_files={max_files}"
            )
        diff = gh.request("GET", compare_path, accept="application/vnd.github.v3.diff")
        if not isinstance(diff, str):
            raise RuntimeError("GitHub compare diff did not return text")
        if files and not diff.strip():
            raise RuntimeError("GitHub compare reported changed files but returned an empty diff")
        scope = _scope_record(
            source="incremental-reviewed-head",
            prior_head=prior_head,
            current_head=current_head,
            files=[item for item in files if isinstance(item, dict)],
            diff=diff,
            review_mode=review_mode,
            compare_status=compare_status,
        )
    except Exception as exc:
        scope = _cumulative_scope(
            module,
            gh,
            pr_number,
            current_head,
            review_mode,
            prior_head,
            f"incremental compare rejected: {str(exc)[:300]}",
            original_get_pr_diff,
            original_list_files,
        )

    scope["pr_number"] = pr_number
    setattr(gh, SCOPE_CACHE_ATTR, scope)
    return scope


def _scope_summary(scope: dict[str, Any]) -> str:
    source = str(scope.get("source", "") or "")
    prior = str(scope.get("prior_reviewed_head_sha", "") or "")
    current = str(scope.get("current_head_sha", "") or "")
    file_count = len(scope.get("files", []) or [])
    if source == "incremental-reviewed-head":
        return (
            f"review scope: incremental reviewed-head {prior[:12]} -> {current[:12]} "
            f"({file_count} changed files)"
        )
    reason = str(scope.get("fallback_reason", "") or "").strip()
    suffix = f"; reason: {reason}" if reason else ""
    return f"review scope: cumulative full PR ({file_count} changed files){suffix}"


def apply_pareto_context_module(module: Any) -> None:
    """Apply the v41 incremental-frontier overlay to the active review module."""
    global _LAST_SCOPE
    _LAST_SCOPE = {}

    client_cls = module.base.GitHubClient
    original_get_pr_diff = getattr(module, _GET_DIFF_STORAGE, None)
    if original_get_pr_diff is None:
        original_get_pr_diff = client_cls.get_pr_diff
        setattr(module, _GET_DIFF_STORAGE, original_get_pr_diff)

    original_list_files = getattr(module, _LIST_FILES_STORAGE, None)
    if original_list_files is None:
        original_list_files = client_cls.list_files
        setattr(module, _LIST_FILES_STORAGE, original_list_files)

    original_prior = getattr(module, _PRIOR_STORAGE, None)
    if original_prior is None:
        original_prior = module.has_prior_successful_context_review
        setattr(module, _PRIOR_STORAGE, original_prior)

    original_deep_context = getattr(module, _DEEP_CONTEXT_STORAGE, None)
    if original_deep_context is None:
        original_deep_context = module.build_deep_context_block
        setattr(module, _DEEP_CONTEXT_STORAGE, original_deep_context)

    original_debug_json = getattr(module, _DEBUG_JSON_STORAGE, None)
    if original_debug_json is None:
        original_debug_json = module.hardened.write_debug_json_artifact_safely
        setattr(module, _DEBUG_JSON_STORAGE, original_debug_json)

    def get_pr_diff(self: Any, number: int) -> str:
        global _LAST_SCOPE
        cached = getattr(self, SCOPE_CACHE_ATTR, None)
        if (
            isinstance(cached, dict)
            and int(cached.get("pr_number", -1)) == number
            and bool(cached.get(INITIAL_DIFF_CONSUMED_KEY))
        ):
            # Downstream repair/publication logic validates against GitHub's
            # cumulative PR diff, not the narrower semantic review frontier.
            return original_get_pr_diff(self, number)
        scope = _resolve_review_scope(
            module,
            self,
            number,
            original_get_pr_diff,
            original_list_files,
        )
        scope[INITIAL_DIFF_CONSUMED_KEY] = True
        setattr(self, SCOPE_CACHE_ATTR, scope)
        _LAST_SCOPE = copy.deepcopy(scope)
        return str(scope.get("diff", "") or "")

    def list_files(self: Any, number: int) -> list[dict[str, Any]]:
        global _LAST_SCOPE
        scope = _resolve_review_scope(
            module,
            self,
            number,
            original_get_pr_diff,
            original_list_files,
        )
        _LAST_SCOPE = copy.deepcopy(scope)
        return [dict(item) for item in scope.get("files", []) if isinstance(item, dict)]

    def has_prior_successful_context_review(gh: Any, pr_number: int) -> bool:
        scope = getattr(gh, SCOPE_CACHE_ATTR, None)
        if isinstance(scope, dict) and int(scope.get("pr_number", -1)) == pr_number:
            return bool(str(scope.get("prior_reviewed_head_sha", "") or "").strip())
        return _latest_compatible_context_review(module, gh, pr_number) is not None

    def build_deep_context_block(gh: Any, pr: Any, files: Any, config: Any, review_mode: str):
        block, summary = original_deep_context(gh, pr, files, config, review_mode)
        scope = getattr(gh, SCOPE_CACHE_ATTR, None)
        scope_text = _scope_summary(scope) if isinstance(scope, dict) else "review scope: unavailable"
        summary_parts = [str(summary or "").strip(), scope_text, ARCHITECTURE_CONTRACT_MARKER]
        return block, "; ".join(part for part in summary_parts if part)

    def write_debug_json_artifact_safely(config: Any, relative_path: str, value: Any) -> None:
        if relative_path == "metadata/review-context.json" and isinstance(value, dict):
            enriched = dict(value)
            scope = dict(_LAST_SCOPE) if isinstance(_LAST_SCOPE, dict) else {}
            enriched.update(
                {
                    "review_contract": ARCHITECTURE_CONTRACT,
                    "review_scope_source": str(scope.get("source", "") or ""),
                    "prior_reviewed_head_sha": str(scope.get("prior_reviewed_head_sha", "") or ""),
                    "review_scope_current_head_sha": str(scope.get("current_head_sha", "") or ""),
                    "review_scope_compare_status": str(scope.get("compare_status", "") or ""),
                    "review_scope_fallback_reason": str(scope.get("fallback_reason", "") or ""),
                    "review_scope_file_count": len(scope.get("files", []) or []),
                }
            )
            value = enriched
        original_debug_json(config, relative_path, value)

    client_cls.get_pr_diff = get_pr_diff
    client_cls.list_files = list_files
    module.has_prior_successful_context_review = has_prior_successful_context_review
    module.build_deep_context_block = build_deep_context_block
    module.hardened.write_debug_json_artifact_safely = write_debug_json_artifact_safely

    module.DCOIR_REVIEW_ARCHITECTURE_CONTRACT = ARCHITECTURE_CONTRACT
    module.DCOIR_REVIEW_ARCHITECTURE_CONTRACT_MARKER = ARCHITECTURE_CONTRACT_MARKER
    module.latest_compatible_context_review = lambda gh, pr_number: _latest_compatible_context_review(
        module, gh, pr_number
    )
