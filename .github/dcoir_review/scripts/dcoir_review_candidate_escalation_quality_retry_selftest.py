#!/usr/bin/env python3
"""Regression: v44's outer adjudication must get its own final-quality retry."""

from __future__ import annotations

import copy
from types import SimpleNamespace

from dcoir_review import candidate_escalation_quality_retry as candidate_retry
import dcoir_review_candidate_scoped_escalation_selftest as stage_test
from dcoir_review_semantic_adjudication_quality_retry_selftest_support import (
    LINES, RETRY_MARKER, Reporter, base_config, finding,
    load_review, response,
)

ARTIFACT = "09-v44-broad-adjudication-quality-retry"
HYPOTHESIS = finding(0.91, line=11, title="Hypothesis dropped by the adjudicator")


def hardened_for(review, provider, reason, debug):
    return SimpleNamespace(
        openrouter_review=provider,
        result_findings=lambda item: item.get("findings", []),
        review_quality_retry_reason=reason,
        build_quality_retry_prompt=lambda prompt, prior, sentinels, cfg, why:
            f"{RETRY_MARKER} {why}\n{prompt}",
        merge_quality_retry_results=review.hardened.merge_quality_retry_results,
        raw_findings_digest=review.hardened.raw_findings_digest,
        sanitize_github_output=lambda text, cfg: str(text),
        write_debug_text_artifact_safely=lambda cfg, path, content: debug.__setitem__(path, content),
        write_debug_json_artifact_safely=lambda cfg, path, content: debug.__setitem__(path, content),
        ReviewQualityError=review.hardened.ReviewQualityError,
    )


def low_reason(value, _config, _sentinels, _lines):
    findings = value.get("findings")
    if findings and all(x.get("confidence", 0) < 0.70 for x in findings):
        return "none met the configured minimum confidence 0.70"
    return ""


def run(initial, retry, reason=None):
    review = load_review()
    calls, debug = [], {}
    reporter = Reporter()

    def provider(prompt, _schema, _cfg, _reporter):
        calls.append(prompt)
        assert RETRY_MARKER in prompt
        if isinstance(retry, BaseException):
            raise retry
        return copy.deepcopy(retry), "repair-adjudicator", "default"

    module = SimpleNamespace(
        hardened=hardened_for(review, provider, reason or low_reason, debug),
        base=SimpleNamespace(sanitize_text=lambda text, _cfg: str(text)),
        rank_findings_for_required_budget=lambda items, limit: items[:limit],
    )
    cfg = base_config(max_inline_comments=8)
    initial = {
        **copy.deepcopy(initial),
        "_semantic_adjudication_attempted": True,
        "_semantic_adjudication_model": "original-opus",
        "_semantic_adjudication_input_candidates": 3,
        "_semantic_adjudication_context_scope": "broader-context",
        "_semantic_adjudication_output_findings": len(initial["findings"]),
    }
    result, model, tier = candidate_retry.retry_candidate_escalation(
        module, initial, {"type": "object"}, cfg, reporter, [], LINES,
        [HYPOTHESIS], "exact changed PR evidence", "broader-context",
    )
    return result, model, tier, calls, debug, cfg, review, reporter


def test_live_failure_reproduced_and_recovered():
    # Run 37983201801: the 0.72/0.70 broad recovery was replaced by
    # final v44 adjudication findings at 0.62, 0.55 and 0.58.
    initial = response(finding(0.62), finding(0.55), finding(0.58))
    # Use the real quality-gate wrapper, not a fake predicate: this is the
    # dispatch seam missed by the previous v35-only tool repair.
    production_reason = load_review().hardened.review_quality_retry_reason
    result, model, _, calls, debug, cfg, review, reporter = run(
        initial, response(finding(0.86)), reason=production_reason
    )
    assert len(calls) == 1
    assert model == "repair-adjudicator"
    assert result["findings"][0]["confidence"] == 0.86
    assert result["_semantic_adjudication_context_scope"] == "broader-context"
    assert result["_semantic_adjudication_model"] == "original-opus"
    assert result["_semantic_adjudication_output_findings"] == 1
    assert result["_quality_retry_attempted"] is True
    assert f"responses/{ARTIFACT}-initial-result.json" in debug
    assert f"prompts/{ARTIFACT}.txt" in debug
    assert all(stage == candidate_retry.REPORT_STAGE for stage, _ in reporter.events)
    assert len(review.hardened.split_findings(result, cfg, LINES)[0]) == 1


def test_retry_prompt_is_the_exact_adjudicator_prompt():
    from dcoir_review import candidate_escalation_execution as execution

    _, _, _, calls, _, cfg, _, _ = run(response(finding(0.62)), response(finding(0.86)))
    module = SimpleNamespace(base=SimpleNamespace(sanitize_text=lambda text, _cfg: str(text)))
    expected = execution.adjudicator_prompt(
        module, cfg, [HYPOTHESIS], "exact changed PR evidence", "broader-context"
    )
    assert calls[0].endswith(expected)
    assert "Hypothesis dropped by the adjudicator" in calls[0]
    assert "Escalation context scope: broader-context." in calls[0]


def test_missing_confidence_retry_is_admitted_at_floor():
    result, model, _, _, _, cfg, review, _ = run(
        response(finding(0.62)), response(finding(None))
    )
    assert model == "repair-adjudicator"
    assert isinstance(result["findings"][0]["confidence"], float)
    assert len(review.hardened.split_findings(result, cfg, LINES)[0]) == 1


def test_second_low_stays_rejected():
    result, _, _, calls, _, cfg, review, _ = run(response(finding(0.62)), response(finding(0.60)))
    assert len(calls) == 1
    try:
        review.hardened.split_findings(result, cfg, LINES)
    except review.hardened.ReviewQualityError:
        pass
    else:
        raise AssertionError("Second sub-threshold final response must not publish")


def test_failed_retry_retains_original():
    initial = response(finding(0.62))
    result, model, _, calls, debug, cfg, review, _ = run(initial, RuntimeError("provider failure"))
    assert len(calls) == 1 and model is None
    assert result["findings"] == initial["findings"]
    assert f"responses/{ARTIFACT}-failed.json" in debug
    try:
        review.hardened.split_findings(result, cfg, LINES)
    except review.hardened.ReviewQualityError:
        pass
    else:
        raise AssertionError("Failed retry cannot convert unsupported findings to clean")


def test_publishable_final_skips_retry():
    result, model, _, calls, _, cfg, review, _ = run(response(finding(0.86)), RuntimeError("must not call"))
    assert model is None and calls == []
    assert len(review.hardened.split_findings(result, cfg, LINES)[0]) == 1


# Exercise the actual v44 stage composition, not only the extracted helper.
def test_outer_candidate_stage_uses_final_retry():
    from dcoir_review import candidate_scoped_escalation as stage
    module, _original_calls, _debug = stage_test.make_module([
        stage_test.finding("src/a.py", "first-pass")
    ])
    originals, calls = stage_test.patch_execution(
        {"mode": "broader-context", "reasons": ["scoped-path-budget-exceeded"],
         "candidate_count": 1, "selected_paths": [item["filename"] for item in stage_test.FILES],
         "escalated_candidate_keys": []},
        [{"findings": [stage_test.finding("src/a.py", "challenger")]}],
        [{**stage_test.finding("src/a.py", "low-final"), "confidence": 0.62}],
    )
    original_retry = stage.quality_retry.retry_candidate_escalation
    retry_calls = []

    def repaired(_module, result, _schema, _cfg, _reporter, _sentinels,
                 _index, hypotheses, evidence, context_scope):
        retry_calls.append(
            (result["findings"][0]["confidence"], len(hypotheses), evidence, context_scope)
        )
        fixed = dict(result)
        fixed["findings"] = [
            {**result["findings"][0], "confidence": 0.88}
        ]
        return fixed, "retry-opus", "retry-tier"

    stage.quality_retry.retry_candidate_escalation = repaired
    try:
        result, model_label, tier_label = stage_test.invoke(module)
    finally:
        stage.quality_retry.retry_candidate_escalation = original_retry
        stage_test.restore_execution(originals)
    assert len(calls["adjudicator"]) == 1
    assert retry_calls == [(0.62, 2, "BROAD", "broader-context")]
    assert result["findings"][0]["confidence"] == 0.88
    assert result["_candidate_escalation"]["adjudicator_call_count"] == 2
    assert "candidate-adjudicator-retry=retry-opus" in model_label
    assert "retry-tier" in tier_label


def run_scoped_stage(retry_findings):
    """Run the candidate-scoped stage with the real retry and merge owners."""
    review = load_review()
    scoped = stage_test.finding("src/a.py", "scoped")
    passthrough = stage_test.finding("src/c.py", "pass through")
    module, _calls, debug = stage_test.make_module([scoped, passthrough])
    seen_sentinels, prompts = [], []

    def provider(prompt, _schema, _cfg, _reporter):
        prompts.append(prompt)
        return {"summary": "Repaired.", "findings": retry_findings}, "retry-opus", "r"

    def reason(value, cfg, sentinels, lines):
        seen_sentinels.append([item.path for item in sentinels])
        return low_reason(value, cfg, sentinels, lines)

    module.hardened = hardened_for(review, provider, reason, debug)
    module.base = SimpleNamespace(sanitize_text=lambda text, _cfg: str(text))
    module.rank_findings_for_required_budget = lambda items, limit: items[:limit]
    originals, _ = stage_test.patch_execution(
        {"mode": "candidate-scoped", "reasons": ["uncovered-required-risk-sentinel"],
         "candidate_count": 1, "selected_paths": ["src/a.py"], "escalated_candidate_keys": []},
        [{"findings": []}],
        [{**scoped, "confidence": 0.62}],
    )
    cfg = base_config(max_inline_comments=8)
    for key, value in vars(stage_test.config()).items():
        setattr(cfg, key, value)
    sentinels = [SimpleNamespace(path="src/a.py"), SimpleNamespace(path="src/c.py")]
    lines = {("src/a.py", 4): 1, ("src/c.py", 4): 1}
    try:
        outcome = module.openrouter_review_with_hybrid_first_pass(
            stage_test.PR, stage_test.FILES, "diff", {"type": "object"}, cfg, None,
            sentinels, lines, "", "first-pass-deep", "", None,
        )
    finally:
        stage_test.restore_execution(originals)
    return outcome, scoped, passthrough, seen_sentinels, prompts, review, debug, cfg, lines


def test_candidate_scoped_retry_keeps_passthrough_findings():
    repaired = {**stage_test.finding("src/a.py", "scoped"), "confidence": 0.86}
    (result, model_label, _), _, passthrough, seen, prompts, *_ = run_scoped_stage([repaired])
    assert len(prompts) == 1
    assert seen == [["src/a.py"]], seen
    assert "Escalation context scope: candidate-scoped." in prompts[0]
    assert sorted(item["path"] for item in result["findings"]) == ["src/a.py", "src/c.py"]
    assert passthrough in result["findings"]
    assert result["_quality_retry_attempted"] is True
    assert result["_candidate_escalation"]["adjudicator_call_count"] == 2
    assert "candidate-adjudicator-retry=retry-opus" in model_label


def test_candidate_scoped_retry_out_of_scope_keeps_first_pass():
    escaped = {**stage_test.finding("src/c.py", "escaped"), "confidence": 0.9}
    (result, model_label, _), scoped, passthrough, _, prompts, review, debug, cfg, lines = (
        run_scoped_stage([escaped])
    )
    assert len(prompts) == 1
    # The escaped finding is rejected; the run keeps the pre-retry adjudication.
    assert escaped not in result["findings"]
    assert passthrough in result["findings"]
    assert {**scoped, "confidence": 0.62} in result["findings"]
    assert "_quality_retry_attempted" not in result
    assert result["_candidate_escalation"]["adjudicator_call_count"] == 2
    assert "candidate-adjudicator-retry" not in model_label
    record = debug[
        "responses/09-v44-candidate-adjudication-quality-retry-out-of-scope.json"
    ]
    assert record["kept"] == "first-pass-adjudication"
    assert record["rejected_result"]["findings"][0]["title"] == "escaped"
    # The publishable passthrough survives; the sub-floor finding does not.
    published = review.hardened.split_findings(result, cfg, lines)[0]
    assert published == [passthrough]


def test_retry_normalization_adds_to_first_pass_count():
    from dcoir_review import semantic_adjudication_confidence as confidence

    initial = response(finding(None, line=12), finding(0.62, title="Low"))
    retry = response(
        finding(None, title="Retry A"), finding(None, title="Retry B"),
    )
    result, model, *_ = run(
        initial, retry, reason=lambda *_args: "forced repair for count coverage"
    )
    assert model == "repair-adjudicator"
    assert result[confidence.NORMALIZATION_COUNT] == 3, result[confidence.NORMALIZATION_COUNT]


def main():
    test_live_failure_reproduced_and_recovered()
    test_retry_prompt_is_the_exact_adjudicator_prompt()
    test_missing_confidence_retry_is_admitted_at_floor()
    test_second_low_stays_rejected()
    test_failed_retry_retains_original()
    test_publishable_final_skips_retry()
    test_outer_candidate_stage_uses_final_retry()
    test_candidate_scoped_retry_keeps_passthrough_findings()
    test_candidate_scoped_retry_out_of_scope_keeps_first_pass()
    test_retry_normalization_adds_to_first_pass_count()
    print("dcoir_review_candidate_escalation_quality_retry_selftest passed")


if __name__ == "__main__":
    main()
