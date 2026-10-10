#!/usr/bin/env python3
"""Deterministic regressions for stable final-adjudication policy."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from dcoir_review.entrypoint import DcoirReviewEntrypoint
from dcoir_review import review_telemetry as telemetry
from dcoir_review import semantic_adjudication as adjudication
from dcoir_review import final_adjudication_policy as final_policy
from dcoir_review import terminal_low_confidence_disposition as terminal_policy
from dcoir_review_final_adjudication_policy_selftest_prompt import (
    run_prompt_regressions,
)
from dcoir_review_final_adjudication_policy_selftest_production import (
    run_production_regressions,
)


class FakeHardened:
    ReviewQualityError = RuntimeError

    def __init__(self) -> None:
        self.review_prompts: list[str] = []
        self.review_stages: list[str] = []
        self.debug_artifacts: dict[str, Any] = {}
        self.debug_text_artifacts: dict[str, str] = {}
        self.force_required_sentinel = False

    def openrouter_review(self, prompt, schema, config, _reporter=None):
        self.review_prompts.append(str(prompt))
        self.review_stages.append(telemetry.classify_stage(prompt, schema, config))
        return {"summary": "clean", "findings": []}, "fake-model", "default"

    def required_risk_sentinels(self, values):
        return list(values) if self.force_required_sentinel else []

    @staticmethod
    def non_actionable_finding_reason(item) -> str:
        return str(item.get("_non_actionable_reason", "") or "") if isinstance(item, dict) else "invalid"

    @staticmethod
    def summary_suggests_problem(summary: str) -> bool:
        lowered = str(summary or "").lower()
        return any(
            phrase in lowered
            for phrase in (
                "issue remains",
                "problem remains",
                "correctness issue",
                "regression remains",
            )
        )

    def write_debug_json_artifact_safely(self, _config, path: str, payload: Any) -> None:
        self.debug_artifacts[path] = payload

    def write_debug_text_artifact_safely(self, _config, path: str, payload: Any) -> None:
        self.debug_text_artifacts[path] = str(payload)


class FakeModule:
    def __init__(self) -> None:
        self.hardened = FakeHardened()
        self.status_events: list[tuple[str, str]] = []
        self.base = SimpleNamespace(emit_status=self._emit_status)
        self.original_split_calls = 0

    def _emit_status(self, stage: str, message: str) -> None:
        self.status_events.append((stage, message))

    def split_findings_with_review_body_fallback(
        self,
        _result,
        _config,
        _line_index,
        _diff="",
        _risk_sentinels=None,
    ):
        self.original_split_calls += 1
        raise RuntimeError("legacy fail-closed path")


def finding(path: str, line: int, confidence: float, title: str = "Candidate") -> dict[str, Any]:
    return {
        "title": title,
        "severity": "medium",
        "confidence": confidence,
        "path": path,
        "line": line,
        "body": "Concrete incorrect behavior is possible.",
        "suggested_replacement": "",
        "validation": "Run deterministic regression.",
    }


def adjudicated_result(
    findings: list[dict[str, Any]],
    summary: str = terminal_policy.CLEAN_SUMMARY,
    *,
    context_scope: str | None = None,
    provider_result_keys: tuple[str, ...] = ("summary", "findings"),
) -> dict[str, Any]:
    result = {
        "summary": summary,
        "findings": findings,
        adjudication.PROVIDER_RESULT_KEYS_ATTR: provider_result_keys,
        "_semantic_adjudication_attempted": True,
        "_semantic_adjudication_model": "anthropic/claude-opus-5",
        "_semantic_adjudication_input_candidates": max(1, len(findings)),
        "_semantic_adjudication_output_findings": len(findings),
        adjudication.FINAL_ADJUDICATION_COMPLETION_ATTR: adjudication.FINAL_ADJUDICATION_COMPLETION_TOKEN,
    }
    if context_scope is not None:
        result["_semantic_adjudication_context_scope"] = context_scope
    return result


def expect_legacy_failure(module: FakeModule, result: dict[str, Any], config: Any, sentinels=None) -> None:
    before = module.original_split_calls
    try:
        module.split_findings_with_review_body_fallback(
            result,
            config,
            {("probe.py", 10): 1},
            "+probe",
            list(sentinels or []),
        )
    except RuntimeError as exc:
        assert "legacy fail-closed path" in str(exc)
    else:
        raise AssertionError("stable final policy bypassed fail-closed")
    assert module.original_split_calls == before + 1


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    config = SimpleNamespace(minimum_confidence=0.70, fail_on_summary_only_problem=True)
    module = FakeModule()
    final_policy.apply_pareto_context_module(module)
    assert getattr(module, final_policy.APPLIED_MARKER, False) is True
    installed_split = module.split_findings_with_review_body_fallback
    assert not hasattr(module.hardened, "_dcoir_review_v57_original_openrouter_review")
    final_policy.apply_pareto_context_module(module)
    assert module.split_findings_with_review_body_fallback is installed_split

    run_prompt_regressions(module, config)

    live_shape = adjudicated_result(
        [
            finding(".github/AGENTS.md", 22, 0.60, "Lane-neutral duty may be narrowed"),
            finding("AGENTS.md", 248, 0.50, "Validation guidance may narrow"),
            finding(
                ".github/agent-governance/codex_cloud_environment.md",
                77,
                0.45,
                "Readback gate may lack actor",
            ),
        ],
        terminal_policy.CLEAN_SUMMARY,
    )
    findings, unanchored = module.split_findings_with_review_body_fallback(
        live_shape,
        config,
        {
            (".github/AGENTS.md", 22): 1,
            ("AGENTS.md", 248): 2,
            (".github/agent-governance/codex_cloud_environment.md", 77): 3,
        },
        "+governance",
        [],
    )
    assert findings == []
    assert unanchored == []
    assert module.original_split_calls == 0
    assert live_shape["findings"] == []
    assert live_shape["summary"] == terminal_policy.CLEAN_SUMMARY
    marker = live_shape[terminal_policy.DISPOSITION_MARKER]
    assert marker["candidate_count"] == 3
    assert marker["minimum_confidence"] == 0.70
    assert marker["lowest_confidence"] == 0.45
    assert marker["highest_confidence"] == 0.60
    assert marker["adjudication_model"] == "anthropic/claude-opus-5"
    assert marker["adjudication_scope"] == "final-v35"
    artifact = module.hardened.debug_artifacts[
        "metadata/v57-terminal-low-confidence-disposition.json"
    ]
    assert artifact["candidate_count"] == 3
    assert any(
        stage == "terminal-low-confidence-disposition"
        and "publication_floor=0.70" in message
        and "result=clean" in message
        for stage, message in module.status_events
    )

    early = {
        "summary": "Possible weak first-pass concern.",
        "findings": [finding("probe.py", 10, 0.55)],
        "_quality_retry_attempted": True,
    }
    expect_legacy_failure(module, early, config)

    incomplete_marker = {
        "summary": terminal_policy.CLEAN_SUMMARY,
        "findings": [finding("probe.py", 10, 0.55)],
        "_semantic_adjudication_attempted": True,
    }
    expect_legacy_failure(module, incomplete_marker, config)

    count_mismatch = adjudicated_result([finding("probe.py", 10, 0.55)])
    count_mismatch["_semantic_adjudication_output_findings"] = 2
    expect_legacy_failure(module, count_mismatch, config)

    overflow_trimmed = adjudicated_result([finding("probe.py", 10, 0.55)])
    overflow_trimmed["_semantic_adjudication_overflow_trimmed"] = 1
    expect_legacy_failure(module, overflow_trimmed, config)

    problem_summary = adjudicated_result(
        [finding("probe.py", 10, 0.55)],
        "A correctness issue remains after semantic adjudication.",
    )
    expect_legacy_failure(module, problem_summary, config)

    malformed_summary = adjudicated_result([finding("probe.py", 10, 0.55)])
    malformed_summary["summary"] = {"unexpected": "object"}
    expect_legacy_failure(module, malformed_summary, config)

    empty_summary = adjudicated_result(
        [finding("probe.py", 10, 0.55)],
        "   ",
    )
    expect_legacy_failure(module, empty_summary, config)

    summary_gate_disabled = SimpleNamespace(
        minimum_confidence=0.70,
        fail_on_summary_only_problem=False,
    )
    disabled_result = adjudicated_result(
        [finding("probe.py", 10, 0.55)],
        "A correctness issue remains after semantic adjudication.",
    )
    assert module.split_findings_with_review_body_fallback(
        disabled_result,
        summary_gate_disabled,
        {("probe.py", 10): 1},
        "+probe",
        [],
    ) == ([], [])

    disabled_malformed_summary = adjudicated_result([finding("probe.py", 10, 0.55)])
    disabled_malformed_summary["summary"] = []
    expect_legacy_failure(module, disabled_malformed_summary, summary_gate_disabled)

    for scope in ("candidate-scoped", "broader-context"):
        # Escalation stages mark only complete adjudications with the token.
        complete = adjudicated_result([finding("probe.py", 10, 0.55)], context_scope=scope)
        assert module.split_findings_with_review_body_fallback(
            complete, config, {("probe.py", 10): 1}, "+probe", [],
        ) == ([], [])
        assert complete[terminal_policy.DISPOSITION_MARKER]["adjudication_scope"] == f"final-{scope}"
        partial = adjudicated_result([finding("probe.py", 10, 0.55)], context_scope=scope)
        del partial[adjudication.FINAL_ADJUDICATION_COMPLETION_ATTR]
        expect_legacy_failure(module, partial, config)

    unanchored = adjudicated_result(
        [finding("probe.py", 99, 0.55)],
        terminal_policy.CLEAN_SUMMARY,
    )
    # Sub-floor findings are never published, so advisory content (an anchor
    # outside the changed lines, informational framing, replacement text)
    # still takes the clean terminal disposition.
    informational = finding("probe.py", 10, 0.55)
    informational["_non_actionable_reason"] = "informational-only"
    populated_replacement = finding("probe.py", 10, 0.55)
    populated_replacement["suggested_replacement"] = "replacement text"
    for advisory in (unanchored, adjudicated_result([informational]), adjudicated_result([populated_replacement])):
        assert module.split_findings_with_review_body_fallback(
            advisory, config, {("probe.py", 10): 1}, "+probe", [],
        ) == ([], [])

    at_floor = adjudicated_result([finding("probe.py", 10, 0.70)])
    expect_legacy_failure(module, at_floor, config)

    mixed = adjudicated_result(
        [finding("probe.py", 10, 0.55), finding("probe.py", 11, 0.90)],
    )
    expect_legacy_failure(module, mixed, config)

    malformed = finding("probe.py", 10, 0.55)
    malformed["confidence"] = 10**400
    expect_legacy_failure(
        module,
        adjudicated_result([malformed]),
        config,
    )

    malformed_replacement = finding("probe.py", 10, 0.55)
    malformed_replacement["suggested_replacement"] = {"unexpected": "object"}
    expect_legacy_failure(
        module,
        adjudicated_result([malformed_replacement]),
        config,
    )

    extra_field = finding("probe.py", 10, 0.55)
    extra_field["unexpected"] = True
    expect_legacy_failure(
        module,
        adjudicated_result([extra_field]),
        config,
    )

    overlength_title = finding("probe.py", 10, 0.55, "T" * 121)
    expect_legacy_failure(
        module,
        adjudicated_result([overlength_title]),
        config,
    )

    top_level_extra_property = adjudicated_result([finding("probe.py", 10, 0.55)])
    top_level_extra_property["unexpected"] = True
    expect_legacy_failure(
        module,
        top_level_extra_property,
        config,
    )

    spoofed_metadata = adjudicated_result([finding("probe.py", 10, 0.55)])
    spoofed_metadata[adjudication.FINAL_ADJUDICATION_COMPLETION_ATTR] = "spoofed"
    expect_legacy_failure(
        module,
        spoofed_metadata,
        config,
    )

    spoofed_envelope_marker = adjudicated_result(
        [finding("probe.py", 10, 0.55)],
        provider_result_keys=("summary", "findings", "_semantic_adjudication_result_shape"),
    )
    spoofed_envelope_marker["_semantic_adjudication_result_shape"] = "flat-single-finding"
    expect_legacy_failure(
        module,
        spoofed_envelope_marker,
        config,
    )

    mixed_case_severity = finding("probe.py", 10, 0.55)
    mixed_case_severity["severity"] = "Medium"
    expect_legacy_failure(
        module,
        adjudicated_result([mixed_case_severity]),
        config,
    )

    padded_severity = finding("probe.py", 10, 0.55)
    padded_severity["severity"] = " medium "
    expect_legacy_failure(
        module,
        adjudicated_result([padded_severity]),
        config,
    )

    module.hardened.force_required_sentinel = True
    try:
        # Never clean; a sub-floor-only result yields to the sentinel fallback.
        sentinel_result = adjudicated_result([finding("probe.py", 10, 0.55)])
        before = module.original_split_calls
        assert module.split_findings_with_review_body_fallback(
            sentinel_result, config, {("probe.py", 10): 1}, "+probe", [object()],
        ) == ([], [])
        assert module.original_split_calls == before + 1
        assert terminal_policy.DISPOSITION_MARKER not in sentinel_result
        fallback = sentinel_result[terminal_policy.SENTINEL_FALLBACK_MARKER]
        assert fallback["mode"] == "required-sentinel-fallback"
        assert sentinel_result["summary"] == terminal_policy.SENTINEL_FALLBACK_SUMMARY
        assert sentinel_result["findings"] == []
        incomplete_completion = adjudicated_result([finding("probe.py", 10, 0.55)])
        del incomplete_completion[adjudication.FINAL_ADJUDICATION_COMPLETION_ATTR]
        output_count_mismatch = adjudicated_result([finding("probe.py", 10, 0.55)])
        output_count_mismatch["_semantic_adjudication_output_findings"] = 2
        invalid_provider_envelope = adjudicated_result(
            [finding("probe.py", 10, 0.55)],
            provider_result_keys=("summary", "findings", "unexpected"),
        )
        incomplete_retry_metadata = adjudicated_result([finding("probe.py", 10, 0.55)])
        incomplete_retry_metadata["_quality_retry_attempted"] = True
        for incomplete in (
            incomplete_completion,
            output_count_mismatch,
            invalid_provider_envelope,
            incomplete_retry_metadata,
        ):
            expect_legacy_failure(module, incomplete, config, sentinels=[object()])
        malformed = finding("probe.py", 10, 0.55)
        malformed["severity"] = "urgent"
        for bad in (finding("probe.py", 10, 0.90), malformed):
            expect_legacy_failure(module, adjudicated_result([bad]), config, sentinels=[object()])
    finally:
        module.hardened.force_required_sentinel = False

    run_production_regressions(entrypoint, adjudicated_result, finding)

    print("dcoir_review_final_adjudication_policy_selftest passed")


if __name__ == "__main__":
    main()
