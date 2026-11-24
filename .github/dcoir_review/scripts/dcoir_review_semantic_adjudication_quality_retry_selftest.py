#!/usr/bin/env python3
"""Behavior regressions for the bounded final semantic-adjudication quality retry."""

from __future__ import annotations

import copy

from dcoir_review import semantic_adjudication_confidence as confidence_policy
from dcoir_review import semantic_adjudication_quality_retry as quality_retry
from dcoir_review import structured_result_disposition_state as disposition
from dcoir_review_semantic_adjudication_quality_retry_selftest_support import (
    CLEAN,
    INITIAL_MODEL,
    LINES,
    RETRY_MODEL,
    Harness,
    base_config,
    finding,
    load_review,
    response,
)


def _retry_repairs_and_records_both_calls(review) -> None:
    # The final adjudicator can produce only 0.60-confidence candidates after
    # the earlier quality gate ran. Retry once; never lower the 0.70 floor.
    harness = Harness(review)
    result = harness.run(response(finding(0.60)), response(finding(0.88)))
    assert len(harness.calls) == 2
    assert [item["confidence"] for item in result["findings"]] == [0.88]
    assert result["_quality_retry_attempted"] is True
    assert result["_semantic_adjudication_model"] == INITIAL_MODEL
    assert result["_quality_retry_model"] == RETRY_MODEL
    assert result["_quality_retry_provider_result_keys"] == ["findings", "summary"]
    assert f"semantic-adjudicator={INITIAL_MODEL}" in harness.model_label
    assert f"semantic-adjudicator-retry={RETRY_MODEL}" in harness.model_label
    assert "prompts/07-semantic-adjudication-quality-retry.txt" in harness.debug_text
    for path in (
        "responses/07-semantic-adjudication-quality-retry-result.json",
        "responses/07-semantic-adjudication-quality-retry-initial-result.json",
    ):
        assert path in harness.debug_json
    assert any(
        stage == "semantic-adjudication-quality-retry"
        and message.startswith("no finding meets confidence 0.70;")
        for stage, message in harness.reporter.events
    )


def _repeated_low_confidence_still_fails_publication(review, config) -> None:
    harness = Harness(review)
    result = harness.run(response(finding(0.60)), response(finding(0.60)))
    assert len(harness.calls) == 2
    assert result["findings"][0]["confidence"] == 0.60
    try:
        review.hardened.split_findings(result, config, LINES)
    except review.hardened.ReviewQualityError:
        pass
    else:
        raise AssertionError("Repeated low-confidence result must fail the publication quality gate")


def _clean_retry_withdraws_rejected_finding(review, config) -> None:
    harness = Harness(review)
    result = harness.run(response(finding(0.60)), CLEAN)
    assert len(harness.calls) == 2
    assert result["findings"] == []
    assert review.hardened.split_findings(result, config, LINES) == ([], [])


def _floor_admitted_findings_do_not_spend_a_retry(review) -> None:
    # A complete missing-confidence finding is admitted at the floor by the
    # downstream confidence stage, so it must not depend on a retry succeeding.
    harness = Harness(review)
    initial = response(finding(None))
    result = harness.run(initial, RuntimeError("retry provider unavailable"))
    assert len(harness.calls) == 1
    assert "_quality_retry_attempted" not in result
    assert "confidence" not in result["findings"][0]
    hardened = type("Hardened", (), {"ReviewQualityError": RuntimeError})
    normalized, count, _floor = confidence_policy._normalize_semantic_adjudication_confidence(
        type("Module", (), {"hardened": hardened}), result, base_config()
    )
    assert count == 1 and normalized["findings"][0]["confidence"] == 0.70


def _floor_admitted_finding_survives_a_clean_retry(review) -> None:
    harness = Harness(review)
    result = harness.run(response(finding(None), finding(0.60, line=13)), CLEAN)
    assert len(harness.calls) == 2
    assert [item["confidence"] for item in result["findings"]] == [0.70]
    assert result["_quality_retry_initial_survivor_count"] == 1
    initial_artifact = harness.debug_json[
        "responses/07-semantic-adjudication-quality-retry-initial-result.json"
    ]["result"]
    assert "confidence" not in initial_artifact["findings"][0]
    assert result["_quality_retry_initial_raw_digest"] == review.hardened.raw_findings_digest(
        initial_artifact
    )
    assert result[confidence_policy.NORMALIZATION_MARKER] == confidence_policy.NORMALIZATION_VALUE
    assert result[confidence_policy.NORMALIZATION_COUNT] == 1


def _overflow_marker_survives_retry_merge(review) -> None:
    harness = Harness(review)
    result = harness.run(
        response(finding(0.60), finding(0.60, line=13, title="Second hypothesis")),
        response(finding(0.60)),
        config=base_config(semantic_adjudication_max_findings=1),
    )
    assert len(harness.calls) == 2
    assert result["_semantic_adjudication_overflow_trimmed"] == 1
    assert result["_quality_retry_attempted"] is True


def _flat_retry_is_normalized_without_clean_certification(review) -> None:
    harness = Harness(review)
    result = harness.run(response(finding(0.60)), finding(0.88))
    assert len(harness.calls) == 2
    assert [item["confidence"] for item in result["findings"]] == [0.88]
    assert result["_quality_retry_retry_summary"] == ""
    assert "summary" not in result["_quality_retry_provider_result_keys"]
    assert not quality_retry.quality_retry_metadata_is_valid(result)


def _retry_check_leaves_first_pass_disposition_state_alone(review, config) -> None:
    # In diff mode the real quality-gate predicate plans a bounded
    # low-confidence disposition on config. The final-stage retry check must
    # neither overwrite the first-pass plan nor divert final findings to it.
    first_pass_plan = {"reason": "first-pass plan", "candidate_count": 1}
    diff_config = copy.copy(config)
    diff_config.semantic_adjudication_model_stack = [INITIAL_MODEL]
    diff_config.minimum_confidence = 0.70
    setattr(diff_config, disposition.ALLOW_ATTR, True)
    setattr(diff_config, disposition.PENDING_ATTR, first_pass_plan)
    harness = Harness(review)
    result = harness.run(
        response(finding(0.65)),
        response(finding(0.88)),
        reason=review.hardened.review_quality_retry_reason,
        config=diff_config,
    )
    assert len(harness.calls) == 2
    assert result["findings"][0]["confidence"] == 0.88
    assert getattr(diff_config, disposition.PENDING_ATTR) is first_pass_plan
    assert getattr(diff_config, disposition.ALLOW_ATTR) is True


def _no_retry_when_predicate_is_clean(review) -> None:
    harness = Harness(review)
    result = harness.run(response(finding(0.91)), RuntimeError("must not retry"))
    assert len(harness.calls) == 1
    assert "_quality_retry_attempted" not in result


def _floor_insertion_keeps_previous_findings(review, config) -> None:
    # The retry prompt reserves room for the publication-floor instruction,
    # so inserting it never truncates the previous findings at the end.
    from dcoir_review import final_adjudication_policy as final_policy

    budget = copy.copy(config)
    budget.max_prompt_chars = 120000
    initial = response(finding(0.60), finding(0.45, line=13, title="Last previous finding"))
    retry_prompt = quality_retry.build_retry_prompt(
        review, "Publication-quality rules:\n" + "E" * 130000, initial, [], budget,
        "no finding meets confidence 0.70",
    )
    assert len(retry_prompt) <= budget.max_prompt_chars - quality_retry.FLOOR_INSTRUCTION_RESERVE_CHARS
    setattr(budget, quality_retry.FINAL_ADJUDICATION_RETRY_ATTR, True)
    projected = final_policy._inject_publication_floor(retry_prompt, budget)
    assert final_policy.PROMPT_MARKER in projected
    assert len(projected) - len(retry_prompt) <= quality_retry.FLOOR_INSTRUCTION_RESERVE_CHARS
    assert projected.rstrip().endswith(retry_prompt.rstrip()[-200:])
    assert "Last previous finding" in projected
    assert not projected.endswith(final_policy.PROMPT_TRUNCATION_MARKER)


def main() -> None:
    review = load_review()
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    _retry_repairs_and_records_both_calls(review)
    _repeated_low_confidence_still_fails_publication(review, config)
    _clean_retry_withdraws_rejected_finding(review, config)
    _floor_admitted_findings_do_not_spend_a_retry(review)
    _floor_admitted_finding_survives_a_clean_retry(review)
    _overflow_marker_survives_retry_merge(review)
    _flat_retry_is_normalized_without_clean_certification(review)
    _retry_check_leaves_first_pass_disposition_state_alone(review, config)
    _no_retry_when_predicate_is_clean(review)
    _floor_insertion_keeps_previous_findings(review, config)
    print("dcoir_review_semantic_adjudication_quality_retry_selftest passed")


if __name__ == "__main__":
    main()
