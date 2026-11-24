#!/usr/bin/env python3
"""Required-sentinel fallback of the terminal low-confidence disposition.

A sub-floor-only model result must never suppress the deterministic risk
sentinel findings. It yields to them (never a clean claim) once the result has
been repaired, either by a completed final adjudication or by a whole-PR quality
retry with complete retry metadata. Partial, unrepaired, malformed, or
publishable results keep the fail-closed split.
"""

from __future__ import annotations

from types import SimpleNamespace

from dcoir_review import semantic_adjudication as adjudication
from dcoir_review import final_adjudication_policy as final_policy
from dcoir_review import terminal_low_confidence_disposition as terminal_policy
from dcoir_review_final_adjudication_policy_selftest import (
    FakeModule, adjudicated_result, expect_legacy_failure, finding,
)

LINES = {("probe.py", 10): 1}


def split(module, result, config):
    return module.split_findings_with_review_body_fallback(result, config, LINES, "+probe", [object()])


def assert_sentinel_fallback(module, result, config) -> None:
    before = module.original_split_calls
    assert split(module, result, config) == ([], [])
    assert module.original_split_calls == before + 1
    assert terminal_policy.DISPOSITION_MARKER not in result
    assert result[terminal_policy.SENTINEL_FALLBACK_MARKER]["mode"] == "required-sentinel-fallback"
    assert result["summary"] == terminal_policy.SENTINEL_FALLBACK_SUMMARY
    assert result["findings"] == []


def quality_retried(findings, summary="pickle.loads remains a correctness issue."):
    """A non-adjudicated diff-mode result after a complete whole-PR quality retry."""
    return {
        "summary": summary,
        "findings": findings,
        "_quality_retry_attempted": True,
        "_quality_retry_reason": "none met the configured minimum confidence 0.70",
        "_quality_retry_initial_summary": "Initial.",
        "_quality_retry_retry_summary": summary,
        "_quality_retry_merge_contract": "filtered-initial-v1",
        "_quality_retry_initial_finding_count": 1,
        "_quality_retry_initial_survivor_count": 0,
        "_quality_retry_initial_rejected_count": 1,
        "_quality_retry_retry_finding_count": len(findings),
        "_quality_retry_initial_raw_digest": "digest",
        "_quality_retry_provider_result_keys": ["findings", "summary"],
        "_quality_retry_model": "retry-model",
    }


def main() -> None:
    config = SimpleNamespace(minimum_confidence=0.70, fail_on_summary_only_problem=True)
    module = FakeModule()
    final_policy.apply_pareto_context_module(module)
    module.hardened.force_required_sentinel = True
    low = finding("probe.py", 10, 0.55)

    # Completed final adjudication, including a summary that names the risk.
    assert_sentinel_fallback(module, adjudicated_result([dict(low)]), config)
    assert_sentinel_fallback(
        module, adjudicated_result([dict(low)], "pickle.loads remains a correctness issue."), config
    )
    # Non-adjudicated result repaired by a complete whole-PR quality retry.
    assert_sentinel_fallback(module, quality_retried([dict(low)]), config)

    # Partial or unrepaired evidence keeps the fail-closed split.
    incomplete_completion = adjudicated_result([dict(low)])
    del incomplete_completion[adjudication.FINAL_ADJUDICATION_COMPLETION_ATTR]
    output_count_mismatch = adjudicated_result([dict(low)])
    output_count_mismatch["_semantic_adjudication_output_findings"] = 2
    invalid_provider_envelope = adjudicated_result(
        [dict(low)], provider_result_keys=("summary", "findings", "unexpected"),
    )
    incomplete_retry_metadata = adjudicated_result([dict(low)])
    incomplete_retry_metadata["_quality_retry_attempted"] = True
    partial_quality_retry = quality_retried([dict(low)])
    del partial_quality_retry["_quality_retry_model"]
    unrepaired = {"summary": "Initial.", "findings": [dict(low)]}
    for incomplete in (
        incomplete_completion, output_count_mismatch, invalid_provider_envelope,
        incomplete_retry_metadata, partial_quality_retry, unrepaired,
    ):
        expect_legacy_failure(module, incomplete, config, sentinels=[object()])

    # Publishable or malformed findings never qualify.
    malformed = dict(low)
    malformed["severity"] = "urgent"
    for bad in (finding("probe.py", 10, 0.90), malformed):
        expect_legacy_failure(module, adjudicated_result([bad]), config, sentinels=[object()])
        expect_legacy_failure(module, quality_retried([bad]), config, sentinels=[object()])

    print("dcoir_review_terminal_sentinel_fallback_selftest passed")


if __name__ == "__main__":
    main()
