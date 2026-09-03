"""Fail-safe adaptive semantic-budget selection for DCOIR Review v46."""

from __future__ import annotations

import copy
from typing import Any

from dcoir_review_required_runtime_patch_v46_contract import (
    BUDGET_CONTRACT,
    positive_int,
)


def _configured(config: Any, name: str, fallback: int) -> int:
    return positive_int(getattr(config, name, fallback), fallback)


def select_budget_plan(
    package: dict[str, Any], config: Any, risk_sentinels: list[Any]
) -> dict[str, Any]:
    metadata = package.get("metadata", {}) if isinstance(package, dict) else {}
    base_prompt = _configured(config, "max_prompt_chars", 120000)
    base_deep = _configured(config, "deep_review_max_total_chars", 60000)
    selected = {
        "max_prompt_chars": base_prompt,
        "deep_review_max_total_chars": base_deep,
        "candidate_escalation_total_context_chars": _configured(
            config, "candidate_escalation_total_context_chars", 48000
        ),
        "semantic_adjudication_candidate_digest_chars": _configured(
            config, "semantic_adjudication_candidate_digest_chars", 24000
        ),
        "max_inline_comments": _configured(config, "max_inline_comments", 12),
    }
    plan = {
        "contract": BUDGET_CONTRACT,
        "package_id": str(metadata.get("package_id", "") or ""),
        "mode": "full-quality-floor",
        "reasons": [],
        "base": dict(selected),
        "selected": selected,
        "quality_floor_preserved": True,
    }
    if not bool(getattr(config, "adaptive_semantic_budgets_review", False)):
        plan["reasons"] = ["adaptive-budgets-disabled"]
        return plan
    if not metadata or not plan["package_id"]:
        plan["reasons"] = ["canonical-package-unavailable"]
        return plan
    if str(metadata.get("review_mode", "") or "") != "diff":
        plan["reasons"] = ["initial-or-deep-review-retains-full-budget"]
        return plan
    if str(metadata.get("scope_source", "") or "") != "incremental-reviewed-head":
        plan["reasons"] = ["non-incremental-scope-retains-full-budget"]
        return plan
    if str(metadata.get("scope_compare_status", "") or "").lower() != "ahead":
        plan["reasons"] = ["untrusted-incremental-compare-retains-full-budget"]
        return plan
    if str(metadata.get("scope_fallback_reason", "") or ""):
        plan["reasons"] = ["scope-fallback-retains-full-budget"]
        return plan
    if risk_sentinels or int(metadata.get("risk_sentinel_count", 0) or 0):
        plan["reasons"] = ["risk-sentinel-retains-full-budget"]
        return plan

    max_files = _configured(config, "adaptive_semantic_small_delta_max_files", 4)
    max_diff = _configured(config, "adaptive_semantic_small_delta_max_diff_chars", 20000)
    max_context = _configured(
        config, "adaptive_semantic_small_delta_max_context_chars", 30000
    )
    if int(metadata.get("changed_file_count", 0) or 0) > max_files:
        plan["reasons"] = ["changed-file-count-retains-full-budget"]
        return plan
    if int(metadata.get("diff_chars", 0) or 0) > max_diff:
        plan["reasons"] = ["diff-size-retains-full-budget"]
        return plan
    if int(metadata.get("deep_context_chars", 0) or 0) > max_context:
        plan["reasons"] = ["dependency-context-size-retains-full-budget"]
        return plan

    minimum = _configured(config, "adaptive_semantic_min_prompt_chars", 48000)
    target = _configured(config, "adaptive_semantic_small_delta_prompt_chars", 60000)
    selected["max_prompt_chars"] = min(base_prompt, max(minimum, target))
    selected["deep_review_max_total_chars"] = min(base_deep, max_context)
    plan["mode"] = "small-incremental-delta"
    plan["reasons"] = [
        "trusted-exact-head-incremental-scope",
        "small-low-risk-review-surface",
    ]
    return plan


def configured_for_plan(config: Any, plan: dict[str, Any]) -> Any:
    staged = copy.copy(config)
    for key, value in plan.get("selected", {}).items():
        setattr(staged, key, value)
    staged._dcoir_v46_context_package_id = str(plan.get("package_id", "") or "")
    staged._dcoir_v46_budget_mode = str(plan.get("mode", "") or "")
    return staged


__all__ = ["configured_for_plan", "select_budget_plan"]
