#!/usr/bin/env python3
"""Deterministic regressions for DCOIR Review v52 bounded recovery."""

from __future__ import annotations

import importlib
import json
import os

from dcoir_review.entrypoint import DcoirReviewEntrypoint


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return self._raw


class Reporter:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def update(self, stage: str, message: str) -> None:
        self.events.append((stage, message))


def finding(path: str, line: int, confidence: float, title: str = "Potential validation defect") -> dict:
    return {
        "path": path,
        "line": line,
        "severity": "medium",
        "confidence": confidence,
        "title": title,
        "body": "The changed behavior may skip a required validation boundary.",
        "validation": "Exercise the changed line with positive and negative controls.",
    }


def provider_response(content: str) -> dict:
    return {
        "model": "anthropic/claude-opus-5",
        "provider": "Anthropic",
        "service_tier": "default",
        "choices": [{"finish_reason": "stop", "message": {"content": content}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 8, "cost": 0.002},
    }


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.execution_policy_patch_module_names == (
        "dcoir_review_required_runtime_patch_v48",
        "dcoir_review_required_runtime_patch_v48_prompt_guard",
        "dcoir_review_required_runtime_patch_v52",
    )

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v52 = importlib.import_module("dcoir_review_required_runtime_patch_v52")
    provider = importlib.import_module("dcoir_review_required_runtime_patch_v52_provider")
    disposition = importlib.import_module("dcoir_review_required_runtime_patch_v52_disposition")
    assert getattr(review, v52.APPLIED_MARKER, False) is True
    assert callable(getattr(review.hardened, "_dcoir_review_v48_original_openrouter_request_once", None))

    # The balanced scanner ignores braces and escaped quotes inside JSON strings.
    sample = 'prefix {"summary":"brace { ok } and \\"quote\\"","findings":[]} suffix'
    ranges = provider.balanced_object_ranges(sample)
    assert len(ranges) == 1
    assert json.loads(sample[ranges[0][0] : ranges[0][1]])["findings"] == []
    assert provider.balanced_object_ranges('prefix {"summary":"truncated"') == []
    assert len(provider.balanced_object_ranges('{"a":1} {"b":2}')) == 2

    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    config.openrouter_capture_request_telemetry = True
    config.openrouter_require_stop_finish_reason = False
    config.openrouter_require_object_response = True
    original_urlopen = review.hardened.urllib.request.urlopen
    previous_key = os.environ.get("OPENROUTER_API_KEY")
    os.environ["OPENROUTER_API_KEY"] = "selftest-key"

    def install(content: str) -> None:
        review.hardened.urllib.request.urlopen = (
            lambda request, timeout=180: FakeResponse(provider_response(content))
        )

    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "findings": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["summary", "findings"],
        "additionalProperties": False,
    }
    try:
        direct = json.dumps({"summary": "clean", "findings": []})
        install(direct)
        parsed, _, _ = review.hardened.openrouter_request_once(
            "probe", schema, config, [], "anthropic/claude-opus-5"
        )
        assert parsed["findings"] == []
        assert getattr(config, provider.RECOVERY_ATTR) == "direct"

        fenced = "```json\n" + direct + "\n```"
        install(fenced)
        parsed, _, _ = review.hardened.openrouter_request_once(
            "probe", schema, config, [], "anthropic/claude-opus-5"
        )
        assert parsed["findings"] == []
        assert getattr(config, provider.RECOVERY_ATTR) == "fenced-object"

        envelope = (
            'Incidental provider prose before the object. '
            '{"summary":"brace { ok } and \\"quote\\"","findings":[]} '
            'Incidental prose after it.'
        )
        install(envelope)
        parsed, _, _ = review.hardened.openrouter_request_once(
            "probe", schema, config, [], "anthropic/claude-opus-5"
        )
        assert parsed["findings"] == []
        assert getattr(config, provider.RECOVERY_ATTR) == "balanced-envelope"
        telemetry = config._openrouter_last_request_telemetry
        assert telemetry["structured_output_recovery"] == "balanced-envelope"
        assert telemetry["request_events"][-1]["structured_output_recovery"] == "balanced-envelope"

        for bad in (
            'prefix {"summary":"a","findings":[]} middle {"summary":"b","findings":[]} suffix',
            'prefix {"summary":"truncated","findings":[]',
            'prefix [{"summary":"array-root","findings":[]}] suffix',
        ):
            install(bad)
            try:
                review.hardened.openrouter_request_once(
                    "probe", schema, config, [], "anthropic/claude-opus-5"
                )
            except json.JSONDecodeError:
                pass
            else:
                raise AssertionError("ambiguous, malformed, or structural output did not fail closed")
            assert getattr(config, provider.RECOVERY_ATTR) == "failed"
    finally:
        review.hardened.urllib.request.urlopen = original_urlopen
        if previous_key is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = previous_key

    # Only anchored/actionable findings within the configured confidence margin
    # may bypass broad quality retry. The 0.60/0.68 case mirrors PR #501 evidence.
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    setattr(config, disposition.ALLOW_ATTR, True)
    line_index = {("a.py", 10): 1, ("b.py", 20): 2}
    near = {
        "summary": "Two bounded hypotheses require disposition.",
        "findings": [finding("a.py", 10, 0.68), finding("b.py", 20, 0.60)],
    }
    reason = review.hardened.review_quality_retry_reason(near, config, [], line_index)
    assert reason == ""
    pending = getattr(config, disposition.PENDING_ATTR)
    assert pending["candidate_count"] == 2
    assert round(float(pending["candidate_floor"]), 2) == 0.60

    too_low = {"summary": "weak", "findings": [finding("a.py", 10, 0.59)]}
    assert review.hardened.review_quality_retry_reason(too_low, config, [], line_index)
    unanchored = {"summary": "near", "findings": [finding("a.py", 11, 0.68)]}
    assert review.hardened.review_quality_retry_reason(unanchored, config, [], line_index)
    summary_only = {"summary": "Found an issue in the changed validation boundary.", "findings": []}
    assert review.hardened.review_quality_retry_reason(summary_only, config, [], line_index)

    for gate_name in (
        "candidate_scoped_escalation_review",
        "adversarial_confirmation_review",
        "semantic_adjudication_review",
    ):
        previous = getattr(config, gate_name, True)
        setattr(config, gate_name, False)
        try:
            assert review.hardened.review_quality_retry_reason(near, config, [], line_index)
        finally:
            setattr(config, gate_name, previous)

    original_required = review.hardened.required_risk_sentinels
    original_non_actionable = review.hardened.non_actionable_finding_reason
    try:
        review.hardened.required_risk_sentinels = lambda values: [object()]
        assert review.hardened.review_quality_retry_reason(near, config, [], line_index)
        review.hardened.required_risk_sentinels = original_required
        review.hardened.non_actionable_finding_reason = lambda item: "informational-only"
        assert review.hardened.review_quality_retry_reason(near, config, [], line_index)
    finally:
        review.hardened.required_risk_sentinels = original_required
        review.hardened.non_actionable_finding_reason = original_non_actionable

    # Bounded disposition makes exactly one independent semantic call, using the
    # confirmation stack rather than paying for challenger + adjudicator replay.
    reporter = Reporter()
    original_evidence = disposition.v44_scope.build_bounded_evidence
    original_challenger = disposition.v44_execution.run_challenger
    original_adjudicator = disposition.v44_execution.run_adjudicator
    calls: list[str] = []
    try:
        disposition.v44_scope.build_bounded_evidence = (
            lambda module, gh, pr, files, cfg, sentinels, paths: ("bounded exact-head evidence", "")
        )

        def forbidden_challenger(*args, **kwargs):
            raise AssertionError("v52 low-confidence diff disposition must not run a challenger")

        def adjudicator(module, schema_arg, cfg, rep, hypotheses, evidence, scope):
            calls.append("disposition")
            assert scope == "candidate-scoped"
            assert len(hypotheses) == 2
            assert cfg is not config
            assert list(cfg.semantic_adjudication_model_stack) == list(
                config.adversarial_confirmation_model_stack
            )
            return {"summary": "clean after bounded disposition", "findings": []}, "sol", ""

        disposition.v44_execution.run_challenger = forbidden_challenger
        disposition.v44_execution.run_adjudicator = adjudicator
        result, model_label, _ = disposition.bounded_low_confidence_disposition(
            review,
            near,
            "opus-primary",
            "",
            {"number": 515, "head": {"sha": "a" * 40}},
            [
                {"filename": "a.py", "status": "modified", "patch": "+a"},
                {"filename": "b.py", "status": "modified", "patch": "+b"},
            ],
            "diff",
            schema,
            config,
            reporter,
            [],
            line_index,
            "",
            "diff",
            "incremental",
            object(),
            pending,
        )
        assert result["findings"] == []
        assert calls == ["disposition"]
        assert "low-confidence-disposition=sol" in model_label
        assert any(
            stage == "structured-low-confidence-disposition"
            and "independent_calls=1" in message
            for stage, message in reporter.events
        )
    finally:
        disposition.v44_scope.build_bounded_evidence = original_evidence
        disposition.v44_execution.run_challenger = original_challenger
        disposition.v44_execution.run_adjudicator = original_adjudicator

    print(
        "dcoir_review_required_runtime_patch_v52_selftest passed: "
        "single-object envelope recovery is deterministic/fail-closed and "
        "near-threshold anchored hypotheses use one bounded independent disposition"
    )


if __name__ == "__main__":
    main()
