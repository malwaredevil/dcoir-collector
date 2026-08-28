#!/usr/bin/env python3
"""Full production-patch-stack regression for DCOIR Review v20."""

from __future__ import annotations

import importlib

from dcoir_review.entrypoint import DcoirReviewEntrypoint


PROBE_PATH = ".github/dcoir_review/evaluation/live_suggestion_probe.py"
PROBE_LINE = 10
PROBE_TEXT = '    if severity == "critical" or "high":'
EXPECTED_REPLACEMENT = '    if severity == "critical" or severity == "high":'


def patched_review_modules():
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    # Import these only after the full patch chain has run, matching production
    # entrypoint import/application order rather than priming the module cache.
    v16 = importlib.import_module("dcoir_review_required_runtime_patch_v16")
    v20 = importlib.import_module("dcoir_review_required_runtime_patch_v20")
    # Selection selftests must not invoke optional prompt-engineering/provider work.
    v16.v9._ensure_prompt_review = lambda _config: None
    return review, v16, v20


def test_truthy_branch_survives_full_stack_selection(review, v16, v20) -> dict:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    sentinel = review.hardened.RiskSentinel(
        path=PROBE_PATH,
        line=PROBE_LINE,
        label="truthy literal branch condition",
        detail="a literal string after or is always truthy",
        text=PROBE_TEXT,
    )
    selected = review.hardened.add_risk_sentinel_fallback_findings([], [sentinel], config, [])
    assert len(selected) == 1, selected
    finding = selected[0]
    assert finding["path"] == PROBE_PATH
    assert int(finding["line"]) == PROBE_LINE
    assert finding.get("_risk_sentinel_kind") == v20.PYTHON_TRUTHY_LITERAL_BRANCH
    assert v20.PYTHON_TRUTHY_LITERAL_BRANCH in v16.CORE_REQUIRED_KINDS
    assert "always-truthy" in str(finding.get("title", ""))
    return finding


def test_detector_suggestion_stays_untrusted(review, v20, finding: dict) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    detector = dict(finding)
    detector["suggested_replacement"] = EXPECTED_REPLACEMENT
    stripped = review.strip_detector_suggested_replacements([detector])
    assert stripped[0]["suggested_replacement"] == ""
    assert stripped[0]["_detector_suggested_replacement"] == EXPECTED_REPLACEMENT
    v20._mark_independent_synthesis_results(stripped)
    assert not stripped[0].get(v20.SYNTHESIS_VERIFIED_MARKER)
    rendered = review.base.build_inline_comment(stripped[0], "test-model", config)
    assert "```suggestion" not in rendered


def test_verified_independent_synthesis_renders_native_suggestion(review, v20, finding: dict) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    synthesized = dict(finding)
    synthesized["suggested_replacement"] = EXPECTED_REPLACEMENT
    v20._mark_independent_synthesis_results([synthesized])
    assert synthesized[v20.SYNTHESIS_VERIFIED_MARKER] is True
    rendered = review.base.build_inline_comment(synthesized, "test-model", config)
    assert f"```suggestion\n{EXPECTED_REPLACEMENT}\n```" in rendered


def main() -> None:
    review, v16, v20 = patched_review_modules()
    finding = test_truthy_branch_survives_full_stack_selection(review, v16, v20)
    test_detector_suggestion_stays_untrusted(review, v20, finding)
    test_verified_independent_synthesis_renders_native_suggestion(review, v20, finding)
    print("dcoir_review_required_runtime_patch_v20_selftest passed")


if __name__ == "__main__":
    main()
