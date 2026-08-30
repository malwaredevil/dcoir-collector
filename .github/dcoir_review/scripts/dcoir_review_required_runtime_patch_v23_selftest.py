#!/usr/bin/env python3
"""Production-stack regression for DCOIR Review v23 ordinary selection."""

from __future__ import annotations

import importlib

from dcoir_review.entrypoint import DcoirReviewEntrypoint


PROBE_PATH = ".github/dcoir_review/evaluation/live_verifier_probe.py"
PROBE_LINE = 12


def patched_review_modules():
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    v16 = importlib.import_module("dcoir_review_required_runtime_patch_v16")
    v20 = importlib.import_module("dcoir_review_required_runtime_patch_v20")
    v16.v9._ensure_prompt_review = lambda _config: None
    return review, v16, v20


def ordinary_finding() -> dict:
    return {
        "title": "Fix inverted upper-bound comparison",
        "severity": "medium",
        "confidence": 0.99,
        "path": PROBE_PATH,
        "line": PROBE_LINE,
        "body": "The documented inclusive 0 through 60 range is implemented with the upper comparison reversed.",
        "suggested_replacement": "",
        "validation": "python3 -m py_compile .github/dcoir_review/evaluation/live_verifier_probe.py",
    }


def test_ordinary_finding_survives_both_selector_passes(review, v16) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    candidate = ordinary_finding()
    path, line, _legacy_kind = v16._postable_key(candidate)
    # Later v26 explicitly tolerates legacy sentinel-kind inference from ordinary
    # finding prose; the production contract is immutable model anchoring when
    # no real risk sentinel was detected. Keep this v23 regression focused on
    # the stable path/line and verbatim finding semantics instead of an obsolete
    # internal-kind assumption.
    assert path == PROBE_PATH and line == PROBE_LINE, (path, line, _legacy_kind)

    selected = review.hardened.add_risk_sentinel_fallback_findings([candidate], [], config, [])
    assert len(selected) == 1, selected
    assert selected[0]["path"] == PROBE_PATH
    assert int(selected[0]["line"]) == PROBE_LINE
    assert selected[0]["title"] == candidate["title"]
    assert selected[0]["body"] == candidate["body"]

    review.hardened.enforce_risk_sentinel_findings(selected, [], config, [])
    assert len(selected) == 1, selected
    assert selected[0]["path"] == PROBE_PATH
    assert int(selected[0]["line"]) == PROBE_LINE
    assert selected[0]["title"] == candidate["title"]
    assert selected[0]["body"] == candidate["body"]


def test_required_sentinel_keeps_priority_under_one_comment_budget(review, v20) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    original_limit = config.max_inline_comments
    config.max_inline_comments = 1
    try:
        sentinel = review.hardened.RiskSentinel(
            path=".github/dcoir_review/evaluation/live_suggestion_probe.py",
            line=10,
            label="truthy literal branch condition",
            detail="a literal string after or is always truthy",
            text='    if severity == "critical" or "high":',
        )
        selected = review.hardened.add_risk_sentinel_fallback_findings([ordinary_finding()], [sentinel], config, [])
        assert len(selected) == 1, selected
        assert selected[0].get("_risk_sentinel_kind") == v20.PYTHON_TRUTHY_LITERAL_BRANCH
        assert selected[0]["path"].endswith("live_suggestion_probe.py")
    finally:
        config.max_inline_comments = original_limit


def main() -> None:
    review, v16, v20 = patched_review_modules()
    test_ordinary_finding_survives_both_selector_passes(review, v16)
    test_required_sentinel_keeps_priority_under_one_comment_budget(review, v20)
    print("dcoir_review_required_runtime_patch_v23_selftest passed")


if __name__ == "__main__":
    main()
