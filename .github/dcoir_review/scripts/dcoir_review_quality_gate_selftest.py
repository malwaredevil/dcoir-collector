#!/usr/bin/env python3
"""Production-stack regression for the stable DCOIR Review semantic quality gate."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

from dcoir_review.entrypoint import DcoirReviewEntrypoint
from dcoir_review import quality_gate


PROBE_PATH = ".github/dcoir_review/evaluation/live_verifier_probe.py"
PROBE_LINE = 12
LIVE_SUMMARY = (
    "Identified a correctness bug in is_recent where the upper boundary condition is inverted, "
    "causing values between 0 and 59 to return False instead of True."
)
LIVE_TYPED_FINDING_SUMMARY = (
    "Completed review of .github/dcoir_review/evaluation/live_verifier_probe.py. "
    "Found 1 correctness finding regarding an inverted upper-bound check in is_recent."
)
EXPECTED_RETRY_REASON = "model summary indicated a possible issue while the structured findings array was empty"


def test_stable_owner_composition() -> None:
    entrypoint = DcoirReviewEntrypoint()
    names = entrypoint.patch_module_names
    assert "dcoir_review.quality_gate" in names, names
    assert "dcoir_review_required_runtime_patch_v22" not in names, names
    index = names.index("dcoir_review.quality_gate")
    assert names[index + 1] == "dcoir_review.normalized_finding_selection", names[max(0, index - 2):index + 4]


def test_retry_uses_explicit_telemetry_stage_without_mutating_shared_config() -> None:
    captured: dict[str, object] = {}

    class Reporter:
        def update(self, _stage: str, _detail: str) -> None:
            return None

    def original(*_args, **_kwargs):
        return {"summary": LIVE_SUMMARY, "findings": []}, "primary", "default"

    def openrouter_review(_prompt, _schema, retry_config, _reporter):
        captured["stage"] = getattr(retry_config, "_dcoir_v54_stage_label", "")
        return {"summary": "retry", "findings": []}, "retry", "default"

    hardened = SimpleNamespace(
        sanitize_github_output=lambda value, _config: value,
        required_risk_sentinels=lambda sentinels: sentinels,
        build_quality_retry_prompt=lambda *_args: "retry-prompt",
        write_debug_text_artifact_safely=lambda *_args: None,
        openrouter_review=openrouter_review,
        write_debug_json_artifact_safely=lambda *_args: None,
        merge_quality_retry_results=lambda **kwargs: kwargs["retry_result"],
        result_findings=lambda result: result.get("findings", []),
    )
    module = SimpleNamespace(
        openrouter_review_with_hybrid_first_pass=original,
        build_prompt=lambda *_args: "aggregate-prompt",
    )
    quality_gate._patch_hybrid_boundary(module, hardened)
    config = SimpleNamespace(
        review_quality_retry_on_rejected_output=True,
        fail_on_summary_only_problem=True,
    )
    module.openrouter_review_with_hybrid_first_pass(
        {}, [], "", {}, config, Reporter(), [], {}, "", "standard", "", object()
    )
    assert captured["stage"] == "broad-quality-retry"
    assert not hasattr(config, "_dcoir_v54_stage_label")


def main() -> None:
    test_stable_owner_composition()
    test_retry_uses_explicit_telemetry_stage_without_mutating_shared_config()
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")

    for live_summary in (LIVE_SUMMARY, LIVE_TYPED_FINDING_SUMMARY):
        assert review.hardened.summary_suggests_problem(live_summary)
        assert review.hardened.review_quality_retry_reason(
            {"summary": live_summary, "findings": []},
            config,
            [],
            {(PROBE_PATH, PROBE_LINE): 1},
        ) == EXPECTED_RETRY_REASON

    for positive_summary in (
        "Found a semantic defect in the changed boundary check.",
        "Detected a vulnerability in the changed authorization branch.",
        "Observed a correctness bug in the new comparison.",
        "A vulnerability was identified in the changed authorization branch.",
        "A correctness bug was found in the new comparison.",
        "Found 1 correctness finding in the changed comparison.",
        "Detected two security findings in the changed workflow.",
        "A logic finding was identified in the new branch.",
        "No unrelated issues were found. Identified a correctness bug in the changed comparison.",
    ):
        assert review.hardened.summary_suggests_problem(positive_summary), positive_summary

    for clean_summary in (
        "No bugs were found in the changed diff.",
        "Found no defects in the changed code.",
        "No vulnerabilities were identified.",
        "Found 0 correctness findings in the changed code.",
        "Detected zero security findings in the changed workflow.",
        "This behavior is not a bug and requires no code change.",
        "The change is not a security vulnerability.",
        "A vulnerability was not identified in this change.",
        "Bug fixes were applied; no actionable findings were found.",
        "The review mentions a finding schema but reports no issue.",
    ):
        assert not review.hardened.summary_suggests_problem(clean_summary), clean_summary

    assert quality_gate.semantic_recovery_reason({"summary": LIVE_SUMMARY, "findings": []}, config) == EXPECTED_RETRY_REASON
    print("dcoir_review_quality_gate_selftest passed")


if __name__ == "__main__":
    main()
