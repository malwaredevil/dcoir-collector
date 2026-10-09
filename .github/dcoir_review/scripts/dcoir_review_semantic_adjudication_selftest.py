#!/usr/bin/env python3
"""Regression checks for canonical DCOIR Review semantic adjudication."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

from dcoir_review.entrypoint import DcoirReviewEntrypoint


class _Reporter:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def update(self, stage: str, message: str) -> None:
        self.events.append((stage, message))


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert "dcoir_review_required_runtime_patch_v35" not in entrypoint.patch_module_names
    assert "dcoir_review.semantic_adjudication_confidence" not in entrypoint.patch_module_names
    assert "dcoir_review.review_orchestration" in entrypoint.execution_policy_patch_module_names

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v21 = importlib.import_module("dcoir_review.finding_verifier")
    semantic_evidence = importlib.import_module("dcoir_review.semantic_evidence_hardening")
    adjudication = importlib.import_module("dcoir_review.semantic_adjudication")
    assert adjudication.quality_retry.valid_retry_summary("Clean summary.\nMore evidence.")
    for malformed_summary in (None, 17, {}, " \n\t", "\x00", "\u200b"):
        assert not adjudication.quality_retry.valid_retry_summary(malformed_summary)

    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    assert config.debug is False
    assert config.semantic_adjudication_review is True
    assert config.semantic_adjudication_max_findings <= config.max_inline_comments
    assert config.semantic_adjudication_model_stack

    assert "untrusted hypothesis" in adjudication.ADJUDICATION_BLOCK
    assert "concrete minimal input" in adjudication.ADJUDICATION_BLOCK
    assert "Collapse multiple manifestations" in adjudication.ADJUDICATION_BLOCK
    assert "MAY add a high-confidence defect" in adjudication.ADJUDICATION_BLOCK
    assert "first try to prove it false" in v21.VERIFIER_FALSIFICATION_BLOCK

    # Directly demonstrated defects in changed executable fixture/test/benchmark
    # code remain reviewable. Consuming evidence is required only when the claim
    # reaches beyond the supplied code into loader/scoring/downstream behavior.
    assert "does not require a separate production consumer" in semantic_evidence.PREDICATE_AUDIT_BLOCK
    assert "directly demonstrated defect in changed executable fixture, test, or benchmark" in adjudication.ADJUDICATION_BLOCK
    assert "Do not reject a defect solely because the changed file is labeled test, fixture, benchmark, or non-production" in v21.VERIFIER_FALSIFICATION_BLOCK
    assert "For fixture-only findings, report only when" not in semantic_evidence.PREDICATE_AUDIT_BLOCK
    assert "fixture or documentation finding is publishable only when" not in adjudication.ADJUDICATION_BLOCK

    digest, count = adjudication._candidate_digest(
        {
            "findings": [
                {
                    "path": "probe.py",
                    "line": 10,
                    "severity": "high",
                    "confidence": 0.94,
                    "title": "First hypothesis",
                    "body": "Possible scope failure",
                    "validation": "counterexample A",
                },
                {
                    "path": "probe.py",
                    "line": 11,
                    "severity": "medium",
                    "confidence": 0.90,
                    "title": "Neighboring manifestation",
                    "body": "Possible duplicate root cause",
                    "validation": "counterexample B",
                },
            ]
        },
        12000,
    )
    assert count == 2
    assert "First hypothesis" in digest and "Neighboring manifestation" in digest

    debug_text: dict[str, str] = {}
    debug_json: dict[str, dict[str, Any]] = {}
    reporter = _Reporter()

    def fake_detector(*args, **kwargs):
        return (
            {
                "summary": "Raw detector hypotheses",
                "findings": [
                    {
                        "path": "probe.py",
                        "line": 10,
                        "severity": "high",
                        "confidence": 0.94,
                        "title": "First hypothesis",
                        "body": "Possible scope failure",
                        "validation": "counterexample A",
                    },
                    {
                        "path": "probe.py",
                        "line": 11,
                        "severity": "medium",
                        "confidence": 0.90,
                        "title": "Neighboring manifestation",
                        "body": "Possible duplicate root cause",
                        "validation": "counterexample B",
                    },
                ],
            },
            "detector-model",
            "default",
        )

    def fake_openrouter(prompt: str, schema: dict[str, Any], cfg: Any, reporter: Any = None):
        assert "First hypothesis" in prompt
        assert "concrete minimal input" in prompt
        assert "Independently adjudicate" in prompt
        # The adjudicator is authoritative and may return a proven root cause
        # that was not literally named in the detector candidate titles.
        return (
            {
                "summary": "One demonstrated root cause survives adjudication.",
                "findings": [
                    {
                        "path": "probe.py",
                        "line": 12,
                        "severity": "medium",
                        "confidence": 0.97,
                        "title": "Predicate accepts rejected evidence",
                        "body": "Counterexample: a rejected proposition still satisfies the positive branch. The sibling OR path omits the contextual rejection filter.",
                        "validation": "Trace the rejected input through the weaker sibling predicate and observe the true return value.",
                    }
                ],
            },
            "adjudicator-model",
            "default",
        )

    fake_hardened = SimpleNamespace(
        parse_yaml_like_data=lambda path: {},
        bool_value=lambda data, key, default: default,
        write_debug_text_artifact_safely=lambda cfg, path, text: debug_text.__setitem__(path, text),
        write_debug_json_artifact_safely=lambda cfg, path, payload: debug_json.__setitem__(path, payload),
        openrouter_review=fake_openrouter,
        result_findings=lambda result: list(result.get("findings", [])),
        ReviewQualityError=RuntimeError,
    )
    fake_base = SimpleNamespace(sanitize_text=lambda text, cfg: str(text))
    fake_module = SimpleNamespace(
        openrouter_review_with_hybrid_first_pass=fake_detector,
        hardened=fake_hardened,
        base=fake_base,
        build_prompt=lambda *args, **kwargs: "PR EVIDENCE: changed predicate and tests",
        rank_findings_for_required_budget=lambda findings, limit: findings[:limit],
    )
    v35_hybrid = adjudication.build_semantic_adjudication_stage(fake_module, fake_detector)
    fake_config = SimpleNamespace(
        semantic_adjudication_review=True,
        semantic_adjudication_max_findings=8,
        semantic_adjudication_candidate_digest_chars=24000,
        semantic_adjudication_model_stack=["adjudicator-model"],
        max_prompt_chars=120000,
        minimum_confidence=0.70,
    )
    result, model_label, tier = v35_hybrid(
        {"number": 1},
        [],
        "diff",
        {},
        fake_config,
        reporter,
        [],
        {},
        "",
        "deep-forced",
        "",
        object(),
    )
    assert len(result["findings"]) == 1
    assert result["findings"][0]["title"] == "Predicate accepts rejected evidence"
    assert result["_semantic_adjudication_input_candidates"] == 2
    assert result["_semantic_adjudication_output_findings"] == 1
    assert "semantic-adjudicator=adjudicator-model" in model_label
    assert tier == "default, default"
    assert "prompts/06-semantic-adjudication-prompt.txt" in debug_text
    assert "responses/06-semantic-adjudication-result.json" in debug_json
    assert any(stage == "semantic-adjudication" and "input=2; retained=1" in message for stage, message in reporter.events)

    # Regression: the final adjudicator can produce only 0.60-confidence
    # candidates after the earlier quality gate already ran. Retry once, then
    # require a newly supported result rather than lowering the 0.70 floor.
    retry_calls: list[str] = []

    def low_then_supported(prompt: str, schema: dict[str, Any], cfg: Any, reporter: Any = None):
        retry_calls.append(prompt)
        confidence = 0.88 if "Review quality retry:" in prompt else 0.60
        return (
            {
                "summary": "The scoped source conflict is backed by the changed lines.",
                "findings": [{
                    "path": "probe.py", "line": 12, "severity": "medium",
                    "confidence": confidence, "title": "Source scope conflict",
                    "body": "The changed rule still narrows by an alert label alone.",
                    "validation": "Compare the added rule with the unchanged routing condition.",
                }],
            },
            "adjudicator-model",
            "default",
        )

    repair_hardened = SimpleNamespace(**vars(fake_hardened))
    repair_hardened.openrouter_review = low_then_supported
    repair_hardened.review_quality_retry_reason = lambda result, cfg, sentinels, lines: (
        "no finding meets confidence 0.70"
        if any(item.get("confidence", 0) < 0.70 for item in result.get("findings", []))
        else ""
    )
    repair_hardened.build_quality_retry_prompt = (
        lambda prompt, prior, sentinels, cfg, reason: "Review quality retry: " + reason + "\n" + prompt
    )
    repair_hardened.merge_quality_retry_results = lambda *, initial_result, retry_result, config, line_index, retry_reason: {
        **retry_result, "_quality_retry_attempted": True,
    }
    repair_module = SimpleNamespace(**vars(fake_module))
    repair_module.hardened = repair_hardened
    repaired, _, _ = adjudication.build_semantic_adjudication_stage(
        repair_module, fake_detector
    )({"number": 1}, [], "diff", {}, fake_config, reporter, [], {}, "", "deep-forced", "", object())
    assert len(retry_calls) == 2
    assert repaired["findings"][0]["confidence"] == 0.88
    assert repaired["_quality_retry_attempted"] is True
    assert "prompts/07-semantic-adjudication-quality-retry.txt" in debug_text
    assert "responses/07-semantic-adjudication-quality-retry-result.json" in debug_json
    assert "responses/07-semantic-adjudication-quality-retry-initial-result.json" in debug_json

    # A second low-confidence adjudication is never silently upgraded to
    # an accepted finding or reported as a clean review. Retry exactly once.
    rejected_calls: list[str] = []

    def always_low(prompt: str, schema: dict[str, Any], cfg: Any, reporter: Any = None):
        rejected_calls.append(prompt)
        first = low_then_supported(prompt, schema, cfg, reporter)
        downgraded = dict(first[0])
        downgraded["findings"] = [{**item, "confidence": 0.60} for item in first[0]["findings"]]
        return downgraded, first[1], first[2]

    fail_closed_hardened = SimpleNamespace(**vars(repair_hardened))
    fail_closed_hardened.openrouter_review = always_low
    fail_closed_module = SimpleNamespace(**vars(repair_module))
    fail_closed_module.hardened = fail_closed_hardened
    still_rejected, _, _ = adjudication.build_semantic_adjudication_stage(
        fail_closed_module, fake_detector
    )({"number": 1}, [], "diff", {}, fake_config, reporter, [], {}, "", "deep-forced", "", object())
    assert len(rejected_calls) == 2
    assert still_rejected["_quality_retry_attempted"] is True
    assert still_rejected["findings"][0]["confidence"] == 0.60
    try:
        review.hardened.split_findings(still_rejected, config, {("probe.py", 12): 1})
    except review.hardened.ReviewQualityError:
        pass
    else:
        raise AssertionError("Repeated low-confidence result must fail publication quality gate")

    # A retry may legitimately withdraw a speculative low-confidence finding.
    # A clean, evidence-bounded retry must not resurrect the rejected original.
    clean_calls: list[str] = []

    def low_then_clean(prompt: str, schema: dict[str, Any], cfg: Any, reporter: Any = None):
        clean_calls.append(prompt)
        if "Review quality retry:" in prompt:
            return {"summary": "No remaining actionable findings.", "findings": []}, "adjudicator-model", "default"
        return low_then_supported(prompt, schema, cfg, reporter)

    clean_hardened = SimpleNamespace(**vars(repair_hardened))
    clean_hardened.openrouter_review = low_then_clean
    clean_hardened.merge_quality_retry_results = review.hardened.merge_quality_retry_results
    clean_module = SimpleNamespace(**vars(repair_module))
    clean_module.hardened = clean_hardened
    fake_config.minimum_confidence = 0.70
    clean_result, _, _ = adjudication.build_semantic_adjudication_stage(
        clean_module, fake_detector
    )({"number": 1}, [], "diff", {}, fake_config, reporter, [], {}, "", "deep-forced", "", object())
    assert len(clean_calls) == 2
    assert clean_result["findings"] == []
    assert clean_result["_quality_retry_attempted"] is True
    assert review.hardened.split_findings(clean_result, config, {("probe.py", 12): 1}) == ([], [])

    # Complete findings with omitted confidence are admitted only at the normal
    # floor and survive a clean retry so the downstream verifier can assess them.
    missing_confidence_calls: list[str] = []

    def missing_confidence_then_clean(prompt, schema, cfg, reporter=None):
        missing_confidence_calls.append(prompt)
        if "Review quality retry:" in prompt:
            return {"summary": "No remaining actionable findings.", "findings": []}, "adjudicator-model", "default"
        return (
            {
                "summary": "The scoped source conflict is backed by the changed lines.",
                "findings": [{
                    "path": "probe.py", "line": 12, "severity": "medium",
                    "title": "Source scope conflict",
                    "body": "The changed rule still narrows by an alert label alone.",
                    "suggested_replacement": "",
                    "validation": "Compare the added rule with the unchanged routing condition.",
                }],
            },
            "adjudicator-model",
            "default",
        )

    missing_confidence_hardened = SimpleNamespace(**vars(repair_hardened))
    missing_confidence_hardened.openrouter_review = missing_confidence_then_clean
    missing_confidence_hardened.merge_quality_retry_results = review.hardened.merge_quality_retry_results
    missing_confidence_hardened.raw_findings_digest = review.hardened.raw_findings_digest
    missing_confidence_module = SimpleNamespace(**vars(repair_module))
    missing_confidence_module.hardened = missing_confidence_hardened
    missing_confidence_result, _, _ = adjudication.build_semantic_adjudication_stage(
        missing_confidence_module, fake_detector
    )(
        {"number": 1}, [], "diff", {}, fake_config, reporter, [], {("probe.py", 12): 1},
        "", "deep-forced", "", object(),
    )
    assert len(missing_confidence_calls) == 2
    assert len(missing_confidence_result["findings"]) == 1
    assert missing_confidence_result["findings"][0]["confidence"] == 0.70
    assert missing_confidence_result["_quality_retry_initial_survivor_count"] == 1
    assert missing_confidence_result["_quality_retry_initial_raw_digest"] == (
        review.hardened.raw_findings_digest(
            debug_json[
                "responses/07-semantic-adjudication-quality-retry-initial-result.json"
            ]["result"]
        )
    )
    assert missing_confidence_result[
        "_semantic_adjudication_confidence_normalization"
    ] == "minimum-floor-for-verifier-admission"
    assert missing_confidence_result[
        "_semantic_adjudication_confidence_normalized_count"
    ] == 1
    assert "confidence" not in debug_json[
        "responses/07-semantic-adjudication-quality-retry-initial-result.json"
    ]["result"]["findings"][0]

    invalid_summary_hardened = SimpleNamespace(**vars(repair_hardened))
    invalid_summary_calls = 0

    def invalid_retry_summary(prompt, schema, cfg, provider_reporter=None):
        nonlocal invalid_summary_calls
        invalid_summary_calls += 1
        if invalid_summary_calls == 1:
            return low_then_supported(prompt, schema, cfg, provider_reporter)
        return (
            {"summary": {"status": "clean"}, "findings": []},
            "adjudicator-model",
            "default",
        )

    invalid_summary_hardened.openrouter_review = invalid_retry_summary
    def forbidden_merge(**_kwargs):
        raise AssertionError("malformed retry summary reached result merging")

    invalid_summary_hardened.merge_quality_retry_results = forbidden_merge
    invalid_summary_module = SimpleNamespace(**vars(repair_module))
    invalid_summary_module.hardened = invalid_summary_hardened
    try:
        adjudication.build_semantic_adjudication_stage(
            invalid_summary_module, fake_detector
        )(
            {"number": 1}, [], "diff", {}, fake_config, reporter, [], {},
            "", "deep-forced", "", object(),
        )
    except invalid_summary_hardened.ReviewQualityError as exc:
        assert "missing or invalid summary" in str(exc)
    else:
        raise AssertionError("malformed retry summary did not fail closed")

    verifier_prompt = v21._verifier_prompt(
        {
            "title": "Candidate",
            "severity": "medium",
            "confidence": 0.95,
            "body": "Candidate body",
            "validation": "Candidate validation",
        },
        "probe.py",
        1,
        "return True",
        "return True\n",
        review.base,
        config,
    )
    assert v21.VERIFIER_FALSIFICATION_BLOCK in verifier_prompt
    assert "directly executable defect in changed test, fixture, or benchmark code remains verifiable" in verifier_prompt
    assert "test-fixture-only text misread as executable behavior" not in verifier_prompt

    # The canonical verifier prompt is directly owned by finding_verifier; no
    # stored-original v35 shim or prompt wrapper survives.
    assert v21._verifier_prompt.__module__ == "dcoir_review.finding_verifier"
    assert not hasattr(v21, "_dcoir_review_v35_original_verifier_prompt")

    # Stable defaults follow current governed production policy, not the retired
    # historical Opus 5 fallback constant.
    assert adjudication.adjudication_models(config) == [
        "anthropic/claude-opus-5.5",
        "openai/gpt-5.6-sol-pro",
    ]
    assert adjudication.ADJUDICATION_BLOCK.count(
        "EVERY retained finding MUST include ``confidence``"
    ) == 1

    # Boundary/malformed controls fail closed or preserve the preceding stage.
    try:
        adjudication.build_semantic_adjudication_stage(fake_module, None)
    except RuntimeError:
        pass
    else:
        raise AssertionError("non-callable semantic predecessor must fail closed")

    try:
        adjudication._candidate_digest({"findings": [{"path": "x.py", "line": 1}]}, 1)
    except ValueError:
        pass
    else:
        raise AssertionError("undersized candidate digest budget must fail explicitly")

    original_openrouter = fake_hardened.openrouter_review
    skip_calls = {"count": 0}
    def should_not_run(*_args, **_kwargs):
        skip_calls["count"] += 1
        raise AssertionError("semantic adjudicator should not run")
    fake_hardened.openrouter_review = should_not_run
    try:
        disabled = SimpleNamespace(**vars(fake_config))
        disabled.semantic_adjudication_review = False
        stage = adjudication.build_semantic_adjudication_stage(fake_module, fake_detector)
        expected = fake_detector()
        assert stage({}, [], "", {}, disabled, None, [], {}, "", "deep-forced", "", None) == expected
        assert stage({}, [], "", {}, fake_config, None, [], {}, "", "first-pass", "", None) == expected
    finally:
        fake_hardened.openrouter_review = original_openrouter
    assert skip_calls["count"] == 0

    # Tiny configured prompt budgets remain true hard ceilings, even when the
    # budget is shorter than the truncation marker.
    for tiny_budget in (0, 1, 7):
        tiny = SimpleNamespace(**vars(fake_config))
        tiny.max_prompt_chars = tiny_budget
        seen = {"prompt": None}
        def capture_prompt(prompt, *_args, **_kwargs):
            seen["prompt"] = prompt
            return {"summary": "clean", "findings": []}, "adjudicator-model", "default"
        fake_hardened.openrouter_review = capture_prompt
        try:
            adjudication.build_semantic_adjudication_stage(fake_module, fake_detector)(
                {}, [], "", {}, tiny, None, [], {}, "", "deep-forced", "", None
            )
        finally:
            fake_hardened.openrouter_review = original_openrouter
        assert isinstance(seen["prompt"], str)
        assert len(seen["prompt"]) <= tiny_budget

    # Provider failure remains fail-closed and is not translated into a clean result.
    sentinel = RuntimeError("semantic adjudicator provider failed")
    def fail_provider(*_args, **_kwargs):
        raise sentinel
    fake_hardened.openrouter_review = fail_provider
    try:
        try:
            adjudication.build_semantic_adjudication_stage(fake_module, fake_detector)(
                {}, [], "", {}, fake_config, None, [], {}, "", "deep-forced", "", None
            )
        except RuntimeError as exc:
            assert exc is sentinel
        else:
            raise AssertionError("semantic adjudicator provider failure must propagate")
    finally:
        fake_hardened.openrouter_review = original_openrouter

    print("dcoir_review_semantic_adjudication_selftest passed")


if __name__ == "__main__":
    main()
