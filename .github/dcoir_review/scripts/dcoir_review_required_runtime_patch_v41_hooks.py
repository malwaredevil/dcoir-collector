"""Runtime hooks composing the v41 review-scope overlay."""

from __future__ import annotations

import copy
from typing import Any

from dcoir_review_required_runtime_patch_v41_review_state import (
    ARCHITECTURE_CONTRACT,
    ARCHITECTURE_CONTRACT_MARKER,
    BASE_CONTRACT_PREFIX,
    latest_compatible_context_review,
)
from dcoir_review_required_runtime_patch_v41_scope import (
    INITIAL_DIFF_CONSUMED_KEY,
    SCOPE_CACHE_ATTR,
    resolve_review_scope,
)

_GET_DIFF_STORAGE = "_dcoir_v41_original_get_pr_diff"
_LIST_FILES_STORAGE = "_dcoir_v41_original_list_files"
_DEEP_CONTEXT_STORAGE = "_dcoir_v41_original_build_deep_context_block"
_DEBUG_JSON_STORAGE = "_dcoir_v41_original_write_debug_json_artifact_safely"
_LAST_SCOPE: dict[str, Any] = {}


def _scope_summary(scope: dict[str, Any]) -> str:
    source = str(scope.get("source", "") or "")
    prior = str(scope.get("prior_reviewed_head_sha", "") or "")
    current = str(scope.get("current_head_sha", "") or "")
    file_count = len(scope.get("files", []) or [])
    if source == "incremental-reviewed-head":
        return f"review scope: incremental reviewed-head {prior[:12]} -> {current[:12]} ({file_count} changed files)"
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
        if isinstance(cached, dict) and int(cached.get("pr_number", -1)) == number and bool(cached.get(INITIAL_DIFF_CONSUMED_KEY)):
            return original_get_pr_diff(self, number)
        scope = resolve_review_scope(module, self, number, original_get_pr_diff, original_list_files)
        scope[INITIAL_DIFF_CONSUMED_KEY] = True
        setattr(self, SCOPE_CACHE_ATTR, scope)
        _LAST_SCOPE = copy.deepcopy(scope)
        return str(scope.get("diff", "") or "")

    def list_files(self: Any, number: int) -> list[dict[str, Any]]:
        global _LAST_SCOPE
        scope = resolve_review_scope(module, self, number, original_get_pr_diff, original_list_files)
        _LAST_SCOPE = copy.deepcopy(scope)
        return [dict(item) for item in scope.get("files", []) if isinstance(item, dict)]

    def has_prior_successful_context_review(gh: Any, pr_number: int) -> bool:
        scope = getattr(gh, SCOPE_CACHE_ATTR, None)
        if isinstance(scope, dict) and int(scope.get("pr_number", -1)) == pr_number:
            return str(scope.get("source", "") or "") == "incremental-reviewed-head"
        return latest_compatible_context_review(module, gh, pr_number) is not None

    def build_deep_context_block(gh: Any, pr: Any, files: Any, config: Any, review_mode: str):
        block, summary = original_deep_context(gh, pr, files, config, review_mode)
        scope = getattr(gh, SCOPE_CACHE_ATTR, None)
        scope_text = _scope_summary(scope) if isinstance(scope, dict) else "review scope: unavailable"
        current_base = str(pr.get("base", {}).get("sha", "") or "").strip().lower() if isinstance(pr, dict) else ""
        base_marker = f"{BASE_CONTRACT_PREFIX}{current_base}" if current_base else ""
        return block, "; ".join(part for part in [str(summary or "").strip(), scope_text, ARCHITECTURE_CONTRACT_MARKER, base_marker] if part)

    def write_debug_json_artifact_safely(config: Any, relative_path: str, value: Any) -> None:
        if relative_path == "metadata/review-context.json" and isinstance(value, dict):
            enriched = dict(value)
            scope = dict(_LAST_SCOPE) if isinstance(_LAST_SCOPE, dict) else {}
            enriched.update({"review_contract": ARCHITECTURE_CONTRACT, "review_scope_source": str(scope.get("source", "") or ""), "prior_reviewed_head_sha": str(scope.get("prior_reviewed_head_sha", "") or ""), "review_scope_current_head_sha": str(scope.get("current_head_sha", "") or ""), "prior_reviewed_base_sha": str(scope.get("prior_reviewed_base_sha", "") or ""), "review_scope_current_base_sha": str(scope.get("current_base_sha", "") or ""), "review_scope_compare_status": str(scope.get("compare_status", "") or ""), "review_scope_fallback_reason": str(scope.get("fallback_reason", "") or ""), "review_scope_file_count": len(scope.get("files", []) or [])})
            value = enriched
        original_debug_json(config, relative_path, value)

    client_cls.get_pr_diff = get_pr_diff
    client_cls.list_files = list_files
    module.has_prior_successful_context_review = has_prior_successful_context_review
    module.build_deep_context_block = build_deep_context_block
    module.hardened.write_debug_json_artifact_safely = write_debug_json_artifact_safely
    module.DCOIR_REVIEW_ARCHITECTURE_CONTRACT = ARCHITECTURE_CONTRACT
    module.DCOIR_REVIEW_ARCHITECTURE_CONTRACT_MARKER = ARCHITECTURE_CONTRACT_MARKER
    module.DCOIR_REVIEW_BASE_CONTRACT_PREFIX = BASE_CONTRACT_PREFIX
    module.latest_compatible_context_review = lambda gh, pr_number: latest_compatible_context_review(module, gh, pr_number)
