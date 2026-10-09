#!/usr/bin/env python3
"""Fail-closed malformed-output regressions for the final adjudication retry."""

from __future__ import annotations

from dcoir_review import review_scope_guard as scope_guard
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


def _failed_retry_keeps_first_pass(review, config) -> None:
    # The retry is an optional repair. A provider failure or malformed retry
    # output is never merged; the first pass continues to downstream gates.
    first_pass = response(finding(0.60), summary="No remaining actionable findings.")
    for retry_reply, failure in (
        (RuntimeError("all retry models failed"), "all retry models failed"),
        (response(summary={"status": "clean"}), "missing or invalid summary"),
        ({"summary": "No remaining actionable findings.", "findings": {}}, "missing or invalid findings"),
        ({"summary": "No remaining actionable findings.", "findings": [None]}, "missing or invalid findings"),
        ({"title": "Partial"}, "complete flat single finding"),
    ):
        harness = Harness(review)
        result = harness.run(first_pass, retry_reply, merge=forbidden_merge)
        assert len(harness.calls) == 2
        assert result["findings"] == first_pass["findings"]
        assert not any(key.startswith("_quality_retry_") for key in result)
        recorded = harness.debug_json[quality_retry.RETRY_FAILED_ARTIFACT_PATH]
        assert failure in recorded["failure"] and recorded["kept"] == "first-pass-adjudication"
        assert any(
            stage == "semantic-adjudication-quality-retry" and message.startswith("retry failed (")
            for stage, message in harness.reporter.events
        )
        # The pre-existing terminal low-confidence disposition still applies.
        assert review.split_findings_with_review_body_fallback(
            result, config, {("probe.py", 12): 1}, "+changed", []
        ) == ([], [])


def _run_aborts_are_not_swallowed(review) -> None:
    # Script timeouts and superseded/unverifiable PR heads must end the run,
    # never fall back to the first-pass result.
    for abort in (
        TimeoutError("script timeout"),
        scope_guard.ReviewSupersededError("newer head"),
        scope_guard.ReviewHeadVerificationError("head unverifiable"),
    ):
        harness = Harness(review)
        try:
            harness.run(response(finding(0.60)), abort, merge=forbidden_merge)
        except type(abort):
            pass
        else:
            raise AssertionError(f"retry swallowed run-level abort {type(abort).__name__}")
        assert len(harness.calls) == 2
        assert quality_retry.RETRY_FAILED_ARTIFACT_PATH not in harness.debug_json


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
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    _failed_retry_keeps_first_pass(review, config)
    _run_aborts_are_not_swallowed(review)
    _malformed_initial_findings_fail_before_retry(review)
    print("dcoir_review_semantic_adjudication_quality_retry_validation_selftest passed")


if __name__ == "__main__":
    main()
