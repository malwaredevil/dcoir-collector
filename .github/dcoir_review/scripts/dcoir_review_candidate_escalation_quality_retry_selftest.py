#!/usr/bin/env python3
"""Regression: v44's outer adjudication must get its own final-quality retry."""

from __future__ import annotations

import copy
from types import SimpleNamespace

from dcoir_review import candidate_escalation_quality_retry as candidate_retry
from dcoir_review_semantic_adjudication_quality_retry_selftest_support import (
    LINES, RETRY_MARKER, Reporter, base_config, finding,
    load_review, response,
)


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
        hardened=SimpleNamespace(
            openrouter_review=provider,
            result_findings=lambda item: item.get("findings", []),
            review_quality_retry_reason=reason or (
                lambda value, _config, _sentinels, _lines:
                    "none met the configured minimum confidence 0.70"
                    if value.get("findings") and all(
                        x.get("confidence", 0) < 0.70 for x in value["findings"]
                    ) else ""
            ),
            build_quality_retry_prompt=lambda prompt, prior, sentinels, cfg, why:
                f"{RETRY_MARKER} {why}\n{prompt}",
            merge_quality_retry_results=review.hardened.merge_quality_retry_results,
            raw_findings_digest=review.hardened.raw_findings_digest,
            sanitize_github_output=lambda text, cfg: str(text),
            write_debug_text_artifact_safely=lambda cfg, path, content: debug.__setitem__(path, content),
            write_debug_json_artifact_safely=lambda cfg, path, content: debug.__setitem__(path, content),
            ReviewQualityError=review.hardened.ReviewQualityError,
        ),
        rank_findings_for_required_budget=lambda items, limit: items[:limit],
    )
    cfg=base_config(max_inline_comments=8)
    initial={
        **copy.deepcopy(initial),
        "_semantic_adjudication_attempted":True,
        "_semantic_adjudication_model":"original-opus",
        "_semantic_adjudication_input_candidates":3,
        "_semantic_adjudication_context_scope":"broader-context",
        "_semantic_adjudication_output_findings":len(initial["findings"]),
    }
    result, model, tier = candidate_retry.retry_candidate_escalation(
        module, initial, {"type":"object"}, cfg, reporter, [], LINES,
        "exact changed PR evidence", "broader-context",
    )
    return result, model, tier, calls, debug, cfg, review


def test_live_failure_reproduced_and_recovered():
    # Run 37983201801: the 0.72/0.70 broad recovery was replaced by
    # final v44 adjudication findings at 0.62, 0.55 and 0.58.
    initial=response(finding(0.62), finding(0.55), finding(0.58))
    # Use the real quality-gate wrapper, not a fake predicate: this is the
    # dispatch seam missed by the previous v35-only tool repair.
    production_reason = load_review().hardened.review_quality_retry_reason
    result, model, _, calls, debug, cfg, review=run(
        initial, response(finding(0.86)), reason=production_reason
    )
    assert len(calls)==1
    assert model=="repair-adjudicator"
    assert result["findings"][0]["confidence"]==0.86
    assert result["_semantic_adjudication_context_scope"]=="broader-context"
    assert result["_semantic_adjudication_model"]=="original-opus"
    assert result["_semantic_adjudication_output_findings"]==1
    assert result["_quality_retry_attempted"] is True
    assert "responses/07-semantic-adjudication-quality-retry-initial-result.json" in debug
    assert len(review.hardened.split_findings(result,cfg,LINES)[0])==1


def test_second_low_stays_rejected():
    result, _, _, calls, _, cfg, review=run(response(finding(0.62)),response(finding(0.60)))
    assert len(calls)==1
    try:
        review.hardened.split_findings(result,cfg,LINES)
    except review.hardened.ReviewQualityError:
        pass
    else:
        raise AssertionError("Second sub-threshold final response must not publish")


def test_failed_retry_retains_original():
    initial=response(finding(0.62))
    result, model, _, calls, debug, cfg, review=run(initial, RuntimeError("provider failure"))
    assert len(calls)==1 and model is None
    assert result["findings"]==initial["findings"]
    assert "responses/07-semantic-adjudication-quality-retry-failed.json" in debug
    try:
        review.hardened.split_findings(result,cfg,LINES)
    except review.hardened.ReviewQualityError:
        pass
    else:
        raise AssertionError("Failed retry cannot convert unsupported findings to clean")


def test_publishable_final_skips_retry():
    result, model, _, calls, _, cfg, review=run(response(finding(0.86)), RuntimeError("must not call"))
    assert model is None and calls==[]
    assert len(review.hardened.split_findings(result,cfg,LINES)[0])==1


def main():
    test_live_failure_reproduced_and_recovered()
    test_second_low_stays_rejected()
    test_failed_retry_retains_original()
    test_publishable_final_skips_retry()
    test_outer_candidate_stage_uses_final_retry()
    print("dcoir_review_candidate_escalation_quality_retry_selftest passed")



# Exercise the actual v44 stage composition, not only the extracted helper.
def test_outer_candidate_stage_uses_final_retry():
    from dcoir_review import candidate_scoped_escalation as stage
    from dcoir_review_candidate_scoped_escalation_selftest import (
        FILES, finding as stage_finding, make_module, patch_execution, restore_execution, invoke,
    )

    module, _original_calls, _debug = make_module([
        stage_finding("src/a.py", "first-pass")
    ])
    originals, calls = patch_execution(
        {"mode": "broader-context", "reasons": ["scoped-path-budget-exceeded"],
         "candidate_count": 1, "selected_paths": [item["filename"] for item in FILES],
         "escalated_candidate_keys": []},
        [{"findings": [stage_finding("src/a.py", "challenger")]}],
        [{**stage_finding("src/a.py", "low-final"), "confidence": 0.62}],
    )
    original_retry = stage.quality_retry.retry_candidate_escalation
    retry_calls = []

    def repaired(_module, result, _schema, _cfg, _reporter, _sentinels,
                 _index, evidence, context_scope):
        retry_calls.append((result["findings"][0]["confidence"], evidence, context_scope))
        fixed = dict(result)
        fixed["findings"] = [
            {**result["findings"][0], "confidence": 0.88}
        ]
        return fixed, "retry-opus", "retry-tier"

    stage.quality_retry.retry_candidate_escalation = repaired
    try:
        result, model_label, tier_label = invoke(module)
    finally:
        stage.quality_retry.retry_candidate_escalation = original_retry
        restore_execution(originals)
    assert len(calls["adjudicator"]) == 1
    assert retry_calls == [(0.62, "BROAD", "broader-context")]
    assert result["findings"][0]["confidence"] == 0.88
    assert result["_candidate_escalation"]["adjudicator_call_count"] == 2
    assert "candidate-adjudicator-retry=retry-opus" in model_label
    assert "retry-tier" in tier_label

if __name__=="__main__":
    main()
