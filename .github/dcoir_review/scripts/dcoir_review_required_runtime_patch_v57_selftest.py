#!/usr/bin/env python3
"""Deterministic regressions for DCOIR Review v57."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from dcoir_review.entrypoint import DcoirReviewEntrypoint
import dcoir_review_required_runtime_patch_v54 as v54
import dcoir_review_required_runtime_patch_v57 as v57
from dcoir_review_required_runtime_patch_v57_selftest_prompt import (
    run_prompt_regressions,
)
from dcoir_review_required_runtime_patch_v57_selftest_production import (
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
        self.review_stages.append(v54.classify_stage(prompt, schema, config))
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
    summary: str = v57.CLEAN_SUMMARY,
    *,
    context_scope: str | None = None,
) -> dict[str, Any]:
    result = {
        "summary": summary,
        "findings": findings,
        "_semantic_adjudication_attempted": True,
        "_semantic_adjudication_model": "anthropic/claude-opus-5",
        "_semantic_adjudication_input_candidates": max(1, len(findings)),
        "_semantic_adjudication_output_findings": len(findings),
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
        raise AssertionError("v57 bypassed fail-closed")
    assert module.original_split_calls == before + 1


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.post_telemetry_patch_module_names[-3:] == (
        "dcoir_review_required_runtime_patch_v55",
        "dcoir_review_required_runtime_patch_v56",
        "dcoir_review_required_runtime_patch_v57",
    )

    config = SimpleNamespace(minimum_confidence=0.70, fail_on_summary_only_problem=True)
    module = FakeModule()
    v57.apply_pareto_context_module(module)
    assert getattr(module, v57.APPLIED_MARKER, False) is True
    stored_review = getattr(module.hardened, v57.REVIEW_STORAGE)
    stored_split = getattr(module, v57.SPLIT_STORAGE)
    v57.apply_pareto_context_module(module)
    assert getattr(module.hardened, v57.REVIEW_STORAGE) is stored_review
    assert getattr(module, v57.SPLIT_STORAGE) is stored_split

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
        v57.CLEAN_SUMMARY,
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
    assert live_shape["summary"] == v57.CLEAN_SUMMARY
    marker = live_shape[v57.DISPOSITION_MARKER]
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
        "summary": v57.CLEAN_SUMMARY,
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

    for scope in ("candidate-scoped", "broad"):
        scoped = adjudicated_result(
            [finding("probe.py", 10, 0.55)],
            v57.CLEAN_SUMMARY,
            context_scope=scope,
        )
        expect_legacy_failure(module, scoped, config)

    unanchored = adjudicated_result(
        [finding("probe.py", 99, 0.55)],
        v57.CLEAN_SUMMARY,
    )
    expect_legacy_failure(module, unanchored, config)

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

    populated_replacement = finding("probe.py", 10, 0.55)
    populated_replacement["suggested_replacement"] = "replacement text"
    expect_legacy_failure(
        module,
        adjudicated_result([populated_replacement]),
        config,
    )

    informational = finding("probe.py", 10, 0.55)
    informational["_non_actionable_reason"] = "informational-only"
    expect_legacy_failure(
        module,
        adjudicated_result([informational]),
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
        expect_legacy_failure(
            module,
            adjudicated_result([finding("probe.py", 10, 0.55)]),
            config,
            sentinels=[object()],
        )
    finally:
        module.hardened.force_required_sentinel = False

    run_production_regressions(entrypoint, adjudicated_result, finding)

    print("dcoir_review_required_runtime_patch_v57_selftest passed")


if __name__ == "__main__":
    main()
