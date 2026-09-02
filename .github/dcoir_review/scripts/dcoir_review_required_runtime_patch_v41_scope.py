"""Review-scope resolution for the v41 runtime overlay."""

from __future__ import annotations

import os
import urllib.parse
from typing import Any

from dcoir_review_required_runtime_patch_v41_review_state import (
    ARCHITECTURE_CONTRACT,
    BASE_CONTRACT_PREFIX,
    _review_base_sha,
    latest_compatible_context_review,
)

SCOPE_CACHE_ATTR = "_dcoir_v41_review_scope"
INITIAL_DIFF_CONSUMED_KEY = "_initial_semantic_diff_consumed"


def _scope_record(*, source: str, prior_head: str, current_head: str, prior_base: str, current_base: str, files: list[dict[str, Any]], diff: str, review_mode: str, fallback_reason: str = "", compare_status: str = "") -> dict[str, Any]:
    return {"source": source, "prior_reviewed_head_sha": prior_head, "current_head_sha": current_head, "prior_reviewed_base_sha": prior_base, "current_base_sha": current_base, "review_mode": review_mode, "fallback_reason": fallback_reason, "compare_status": compare_status, "files": files, "diff": diff}


def _cumulative_scope(module: Any, gh: Any, pr_number: int, current_head: str, current_base: str, review_mode: str, prior_head: str, prior_base: str, reason: str, original_get_pr_diff: Any, original_list_files: Any) -> dict[str, Any]:
    return _scope_record(source="cumulative-full-pr", prior_head=prior_head, current_head=current_head, prior_base=prior_base, current_base=current_base, files=original_list_files(gh, pr_number), diff=original_get_pr_diff(gh, pr_number), review_mode=review_mode, fallback_reason=reason)


def _cache_scope(gh: Any, scope: dict[str, Any], pr_number: int) -> dict[str, Any]:
    scope["pr_number"] = pr_number
    setattr(gh, SCOPE_CACHE_ATTR, scope)
    return scope


def resolve_review_scope(module: Any, gh: Any, pr_number: int, original_get_pr_diff: Any, original_list_files: Any) -> dict[str, Any]:
    """Resolve incremental scope or conservatively fall back to cumulative PR scope."""
    cached = getattr(gh, SCOPE_CACHE_ATTR, None)
    if isinstance(cached, dict) and int(cached.get("pr_number", -1)) == pr_number:
        return cached
    pr = gh.get_pr(pr_number)
    current_head = str(pr.get("head", {}).get("sha", "") or "").strip().lower()
    current_base = str(pr.get("base", {}).get("sha", "") or "").strip().lower()
    if not current_head or not current_base:
        missing = "current PR head SHA" if not current_head else "current PR base SHA"
        return _cache_scope(gh, _cumulative_scope(module, gh, pr_number, current_head, current_base, "unknown", "", "", f"{missing} unavailable", original_get_pr_diff, original_list_files), pr_number)
    try:
        prior_review = latest_compatible_context_review(module, gh, pr_number)
    except Exception as exc:
        return _cache_scope(gh, _cumulative_scope(module, gh, pr_number, current_head, current_base, "unknown", "", "", f"compatible prior-review readback failed: {str(exc)[:240]}", original_get_pr_diff, original_list_files), pr_number)
    prior_head = str((prior_review or {}).get("commit_id", "") or "").strip().lower()
    prior_base = _review_base_sha(prior_review) if isinstance(prior_review, dict) else ""
    config_path = os.environ.get("OPENROUTER_REVIEW_CONFIG", ".github/dcoir_review/openrouter-pr-review-pareto.yml")
    config = module.load_pareto_context_config(config_path)
    body = os.environ.get("TRIGGER_COMMENT_BODY", "")
    command = module.hardened.matching_command(body, config.commands)
    review_mode = "unknown" if not command else module.review_mode_for_command(body, command, config, bool(prior_head and prior_base))
    if review_mode != "diff":
        return _cache_scope(gh, _cumulative_scope(module, gh, pr_number, current_head, current_base, review_mode, prior_head, prior_base, f"{review_mode or 'unknown'} requires cumulative review scope", original_get_pr_diff, original_list_files), pr_number)
    if not prior_head or not prior_base:
        return _cache_scope(gh, _cumulative_scope(module, gh, pr_number, current_head, current_base, review_mode, "", "", f"no prior compatible {ARCHITECTURE_CONTRACT} DCOIR context review with base-state marker", original_get_pr_diff, original_list_files), pr_number)
    if prior_base != current_base:
        return _cache_scope(gh, _cumulative_scope(module, gh, pr_number, current_head, current_base, review_mode, prior_head, prior_base, f"PR base moved since prior review: {prior_base[:12]} -> {current_base[:12]}", original_get_pr_diff, original_list_files), pr_number)
    if prior_head == current_head:
        return _cache_scope(gh, _cumulative_scope(module, gh, pr_number, current_head, current_base, review_mode, prior_head, prior_base, "prior compatible review already targets current head", original_get_pr_diff, original_list_files), pr_number)
    encoded_base = urllib.parse.quote(prior_head, safe="")
    encoded_head = urllib.parse.quote(current_head, safe="")
    compare_path = f"/repos/{gh.repo}/compare/{encoded_base}...{encoded_head}"
    try:
        comparison = gh.request("GET", f"{compare_path}?per_page=1&page=1")
        if not isinstance(comparison, dict): raise RuntimeError("GitHub compare did not return an object")
        compare_status = str(comparison.get("status", "") or "").strip().lower()
        merge_base = str(comparison.get("merge_base_commit", {}).get("sha", "") or "").strip().lower()
        files = comparison.get("files", [])
        if compare_status != "ahead": raise RuntimeError(f"compare status is {compare_status or 'missing'}, not ahead")
        if merge_base != prior_head: raise RuntimeError("prior reviewed head is not the exact compare merge base")
        if not isinstance(files, list): raise RuntimeError("compare files is not a list")
        max_files = int(getattr(config, "max_files", 100))
        if len(files) > max_files: raise RuntimeError(f"incremental compare contains {len(files)} files, exceeding governed max_files={max_files}")
        diff = gh.request("GET", compare_path, accept="application/vnd.github.v3.diff")
        if not isinstance(diff, str): raise RuntimeError("GitHub compare diff did not return text")
        if files and not diff.strip(): raise RuntimeError("GitHub compare reported changed files but returned an empty diff")
        scope = _scope_record(source="incremental-reviewed-head", prior_head=prior_head, current_head=current_head, prior_base=prior_base, current_base=current_base, files=[item for item in files if isinstance(item, dict)], diff=diff, review_mode=review_mode, compare_status=compare_status)
    except Exception as exc:
        scope = _cumulative_scope(module, gh, pr_number, current_head, current_base, review_mode, prior_head, prior_base, f"incremental compare rejected: {str(exc)[:300]}", original_get_pr_diff, original_list_files)
    return _cache_scope(gh, scope, pr_number)
