#!/usr/bin/env python3
"""Fail-closed malformed-output regressions for the final adjudication retry."""

from __future__ import annotations

from dcoir_review import semantic_adjudication_quality_retry as quality_retry
from dcoir_review_semantic_adjudication_quality_retry_selftest_support import (
    CLEAN,
    Harness,
    always_retry,
    base_config,
    finding,
    forbidden_merge,
    load_review,
    response,
)


def _summary_contract() -> None:
    assert quality_retry.valid_retry_summary("Clean summary.\nMore evidence.")
    for malformed in (None, 17, {}, " \n\t", "\x00", "\u200b"):
        assert not quality_retry.valid_retry_summary(malformed)


def _malformed_retry_output_fails_closed(review) -> None:
    harness = Harness(review)
    harness.expect_failure(
        "missing or invalid summary",
        response(finding(0.60)),
        response(summary={"status": "clean"}),
        merge=forbidden_merge,
    )
    for malformed_findings in ({}, [None]):
        harness.expect_failure(
            "missing or invalid findings",
            response(finding(0.60)),
            {"summary": "No remaining actionable findings.", "findings": malformed_findings},
            merge=forbidden_merge,
        )
    # An incomplete flat object is neither an envelope nor a complete finding.
    harness.expect_failure(
        "complete flat single finding",
        response(finding(0.60)),
        {"title": "Partial"},
        merge=forbidden_merge,
    )


def _malformed_initial_findings_fail_before_retry(review) -> None:
    # A clean retry must never hide malformed first-pass output, and the
    # bounded retry provider call is not spent on it.
    harness = Harness(review)
    for initial in (response(None), response(finding(0.60), None)):
        harness.expect_failure(
            "non-object finding",
            initial,
            CLEAN,
            config=base_config(semantic_adjudication_max_findings=1),
            merge=forbidden_merge,
        )
        assert len(harness.calls) == 1
    partial_missing_confidence = finding(None)
    del partial_missing_confidence["suggested_replacement"]
    for invalid in (partial_missing_confidence, finding("0.60"), finding(True), finding(1.5)):
        harness.expect_failure(
            "semantic-adjudication confidence",
            response(invalid),
            CLEAN,
            reason=always_retry,
            merge=forbidden_merge,
        )
        assert len(harness.calls) == 1


def main() -> None:
    review = load_review()
    _summary_contract()
    _malformed_retry_output_fails_closed(review)
    _malformed_initial_findings_fail_before_retry(review)
    print("dcoir_review_semantic_adjudication_quality_retry_validation_selftest passed")


if __name__ == "__main__":
    main()
