#!/usr/bin/env python3
"""Regression checks for DCOIR Review v39 adjudicator confidence compatibility."""

from __future__ import annotations

import importlib
from pathlib import Path

from dcoir_review.entrypoint import DcoirReviewEntrypoint


def _finding(*, confidence_marker: object = ...):
    item = {
        "title": "Rejected proposition counts as positive evidence",
        "severity": "high",
        "path": "probe.py",
        "line": 2,
        "body": (
            "A rejected proposition reaches the positive lane-separation predicate; "
            "the exact sibling branch needs the same polarity filter."
        ),
        "suggested_replacement": "",
        "validation": "python3 -m py_compile probe.py",
    }
    if confidence_marker is not ...:
        item["confidence"] = confidence_marker
    return item


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    names = entrypoint.patch_module_names
    assert "dcoir_review_required_runtime_patch_v39" in names
    assert names.index("dcoir_review_required_runtime_patch_v38") < names.index(
        "dcoir_review_required_runtime_patch_v39"
    )
    assert names.index("dcoir_review_required_runtime_patch_v39") < names.index(
        "dcoir_review_required_runtime_patch_v31"
    )

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v21 = importlib.import_module("dcoir_review_required_runtime_patch_v21")
    v35 = importlib.import_module("dcoir_review_required_runtime_patch_v35")
    v39 = importlib.import_module("dcoir_review_required_runtime_patch_v39")

    assert getattr(review, v39.APPLIED_MARKER, False) is True
    assert "EVERY retained finding MUST include ``confidence``" in v35.ADJUDICATION_BLOCK

    config = review.load_pareto_context_config(
        ".github/dcoir_review/openrouter-pr-review-pareto.yml"
    )
    assert config.debug is False
    assert float(config.minimum_confidence) == 0.70

    # Canonical numeric confidence is authoritative and unchanged.
    canonical = {
        "findings": [_finding(confidence_marker=0.93)],
        "_semantic_adjudication_attempted": True,
    }
    normalized, count, floor = v39._normalize_semantic_adjudication_confidence(
        review, canonical, config
    )
    assert normalized is canonical
    assert count == 0
    assert floor == 0.70
    assert normalized["findings"][0]["confidence"] == 0.93

    # Reproduce live run 33389436164: otherwise complete retained finding with
    # the schema-required confidence field omitted. v39 assigns only the normal
    # review floor so the independent v21 verifier can judge it.
    live_shape = {
        "findings": [_finding()],
        "_semantic_adjudication_attempted": True,
        "_semantic_adjudication_model": "anthropic/claude-opus-5",
    }
    normalized, count, floor = v39._normalize_semantic_adjudication_confidence(
        review, live_shape, config
    )
    assert count == 1
    assert floor == 0.70
    assert normalized["findings"][0]["confidence"] == 0.70
    assert normalized[v39.NORMALIZATION_MARKER] == v39.NORMALIZATION_VALUE
    assert normalized[v39.NORMALIZATION_COUNT] == 1

    # Null confidence is the same provider omission class; it may be admitted to
    # verification but is never promoted above the configured publication floor.
    null_shape = {
        "findings": [_finding(confidence_marker=None)],
        "_semantic_adjudication_attempted": True,
    }
    normalized_null, count_null, _ = v39._normalize_semantic_adjudication_confidence(
        review, null_shape, config
    )
    assert count_null == 1
    assert normalized_null["findings"][0]["confidence"] == 0.70

    # The ordinary normalizer now accepts the candidate only because it sits at
    # the normal configured threshold; publication is still not authorized here.
    selected, unanchored = review.hardened.split_findings(
        normalized,
        config,
        {("probe.py", 2): 1},
    )
    assert len(selected) == 1 and not unanchored
    assert selected[0]["confidence"] == 0.70

    # Prove the next production authority remains the independent v21 verifier.
    original_openrouter = review.hardened.openrouter_review
    original_fetch = review.fetch_pr_file_text

    class _Reporter:
        def __init__(self):
            self.events = []

        def update(self, stage, message):
            self.events.append((stage, message))

    class _GH:
        pass

    def _fake_openrouter(prompt, schema, cfg, reporter=None):
        assert schema["title"] == "DCOIR Candidate Finding Verifier"
        return (
            {
                "supported": True,
                "confidence": 0.99,
                "evidence": "The exact anchored call lacks the sibling polarity guard.",
                "reason": "Concrete rejected input reaches the branch.",
            },
            "openai/gpt-5.6-sol-pro",
            "tier-test",
        )

    review.hardened.openrouter_review = _fake_openrouter
    review.fetch_pr_file_text = lambda gh, path, head: "def f():\n    old_call()\n"
    try:
        verified = v21.verify_findings_for_publication(
            review,
            selected,
            _GH(),
            {"head": {"sha": "deadbeef"}},
            config,
            _Reporter(),
        )
    finally:
        review.hardened.openrouter_review = original_openrouter
        review.fetch_pr_file_text = original_fetch

    assert len(verified) == 1
    assert verified[0]["confidence"] == 0.70
    assert verified[0][v21.VERIFIER_MARKER]["supported"] is True
    assert verified[0][v21.VERIFIER_MARKER]["confidence"] == 0.99

    # Missing confidence is the only tolerated finding-field drift. Partial
    # findings and malformed supplied confidence remain fail-closed.
    malformed = _finding()
    malformed.pop("validation")
    for bad_result, expected in (
        (
            {"findings": [malformed], "_semantic_adjudication_attempted": True},
            "partial finding",
        ),
        (
            {
                "findings": [_finding(confidence_marker=True)],
                "_semantic_adjudication_attempted": True,
            },
            "non-numeric confidence",
        ),
        (
            {
                "findings": [_finding(confidence_marker="0.93")],
                "_semantic_adjudication_attempted": True,
            },
            "non-numeric confidence",
        ),
        (
            {
                "findings": [_finding(confidence_marker=1.01)],
                "_semantic_adjudication_attempted": True,
            },
            "outside 0.0..1.0",
        ),
    ):
        try:
            v39._normalize_semantic_adjudication_confidence(review, bad_result, config)
        except review.hardened.ReviewQualityError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"v39 did not fail closed for {expected}")

    # Detector/challenger results are outside this compatibility seam and remain
    # unchanged, including their missing confidence if malformed upstream.
    detector_result = {"findings": [_finding()]}
    untouched, count, _ = v39._normalize_semantic_adjudication_confidence(
        review, detector_result, config
    )
    assert untouched is detector_result
    assert count == 0
    assert "confidence" not in untouched["findings"][0]

    # Bad configured floors never become a compatibility escape hatch.
    original_floor = config.minimum_confidence
    for bad_floor in (-0.01, 1.01, True, "not-a-number"):
        config.minimum_confidence = bad_floor
        try:
            v39._normalize_semantic_adjudication_confidence(review, live_shape, config)
        except review.hardened.ReviewQualityError:
            pass
        else:
            raise AssertionError(f"v39 accepted invalid configured floor {bad_floor!r}")
    config.minimum_confidence = original_floor

    # Applying v39 twice must not stack wrappers or duplicate prompt contracts.
    wrapper_before = review.openrouter_review_with_hybrid_first_pass
    block_before = v35.ADJUDICATION_BLOCK
    v39.apply_pareto_context_module(review)
    assert review.openrouter_review_with_hybrid_first_pass is wrapper_before
    assert v35.ADJUDICATION_BLOCK == block_before
    assert v35.ADJUDICATION_BLOCK.count("EVERY retained finding MUST include ``confidence``") == 1

    source = Path(
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v39.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("git push", "create_commit(", "update_file(", "merge_pull_request"):
        assert forbidden not in source

    print("dcoir_review_required_runtime_patch_v39_selftest passed")


if __name__ == "__main__":
    main()
