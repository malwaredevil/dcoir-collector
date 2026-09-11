#!/usr/bin/env python3
"""Deterministic regressions for DCOIR Review v57 terminal disposition."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

from dcoir_review.entrypoint import DcoirReviewEntrypoint
import dcoir_review_required_runtime_patch_v54 as v54
import dcoir_review_required_runtime_patch_v57 as v57


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
        "body": "The changed contract may permit a concrete incorrect behavior.",
        "suggested_replacement": "",
        "validation": "Exercise the changed contract with a deterministic regression.",
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
        raise AssertionError("v57 bypassed a negative-control fail-closed case")
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

    # Only the final v35 adjudicator gets the active publication floor. Because
    # injection replaces the prompt object, v57 must preserve v54's stage label
    # explicitly rather than allowing it to fall back to primary-semantic.
    semantic_prompt = (
        "Final semantic adjudication pass.\n\n"
        "Publication-quality rules:\n"
        "- Return only distinct root-cause defects.\n\n"
        f"{v57.FINAL_ADJUDICATION_PROMPT_MARKER}\n[]"
    )
    original_callsite_probe = v57._is_final_v35_semantic_adjudication_call
    v57._is_final_v35_semantic_adjudication_call = lambda _prompt: True
    module.hardened.openrouter_review(semantic_prompt, {}, config, None)
    v57._is_final_v35_semantic_adjudication_call = original_callsite_probe
    injected = module.hardened.review_prompts[-1]
    assert v57.PROMPT_MARKER in injected
    assert "0.70" in injected
    assert "empty findings list and a clean summary" in injected
    assert injected.count(v57.PROMPT_MARKER) == 1
    assert module.hardened.review_stages[-1] == "semantic-adjudicator"
    assert module.hardened.debug_text_artifacts[v57.PROMPT_ARTIFACT_PATH] == injected

    # v44/v52 escalation uses the same leading adjudication block but different
    # bounded-evidence wording; v57 must not rewrite that independent contract.
    escalation_prompt = (
        "Final semantic adjudication pass.\n\n"
        "Publication-quality rules:\n"
        "- Return only distinct root-cause defects.\n\n"
        "Candidate hypotheses from the bounded primary/challenger evidence:\n[]\n\n"
        "Escalation context scope: candidate-scoped."
    )
    module.hardened.openrouter_review(escalation_prompt, {}, config, None)
    assert module.hardened.review_prompts[-1] == escalation_prompt
    assert module.hardened.review_stages[-1] != "semantic-adjudicator"

    ordinary_prompt = "Routine per-file review prompt."
    module.hardened.openrouter_review(ordinary_prompt, {}, config, None)
    assert module.hardened.review_prompts[-1] == ordinary_prompt
    assert module.hardened.review_stages[-1] != "semantic-adjudicator"

    untrusted_marker_prompt = (
        "Final semantic adjudication pass.\n\n"
        "PR diff mentions: "
        f"{v57.PROMPT_MARKER}\n\n"
        f"{v57.FINAL_ADJUDICATION_PROMPT_MARKER}\n[]"
    )
    module.hardened.openrouter_review(untrusted_marker_prompt, {}, config, None)
    assert module.hardened.review_prompts[-1] == untrusted_marker_prompt

    tiny_budget_config = SimpleNamespace(minimum_confidence=0.70, fail_on_summary_only_problem=True, max_prompt_chars=220)
    v57._is_final_v35_semantic_adjudication_call = lambda _prompt: True
    module.hardened.openrouter_review(semantic_prompt, {}, tiny_budget_config, None)
    v57._is_final_v35_semantic_adjudication_call = original_callsite_probe
    bounded_injected = module.hardened.review_prompts[-1]
    assert len(bounded_injected) <= tiny_budget_config.max_prompt_chars
    assert bounded_injected.endswith(v57.PROMPT_TRUNCATION_MARKER)
    assert v57.PROMPT_MARKER in bounded_injected

    tiny_marker_budget = SimpleNamespace(minimum_confidence=0.70, fail_on_summary_only_problem=True, max_prompt_chars=8)
    v57._is_final_v35_semantic_adjudication_call = lambda _prompt: True
    module.hardened.openrouter_review(semantic_prompt, {}, tiny_marker_budget, None)
    v57._is_final_v35_semantic_adjudication_call = original_callsite_probe
    smallest_bounded = module.hardened.review_prompts[-1]
    assert len(smallest_bounded) == tiny_marker_budget.max_prompt_chars

    malformed_budget_config = SimpleNamespace(
        minimum_confidence=0.70,
        fail_on_summary_only_problem=True,
        max_prompt_chars="invalid",
    )
    v57._is_final_v35_semantic_adjudication_call = lambda _prompt: True
    module.hardened.openrouter_review(semantic_prompt, {}, malformed_budget_config, None)
    v57._is_final_v35_semantic_adjudication_call = original_callsite_probe
    malformed_budget_injected = module.hardened.review_prompts[-1]
    assert v57.PROMPT_MARKER in malformed_budget_injected
    assert not malformed_budget_injected.endswith(v57.PROMPT_TRUNCATION_MARKER)

    # Re-injection is idempotent for an already annotated final prompt.
    reinjected = v57._inject_publication_floor(injected, config)
    assert reinjected == injected

    # Exact live run 34566845633 confidence shape: final v35 semantic adjudication
    # completed and retained only 0.60/0.50/0.45 hypotheses below the 0.70 floor.
    # The clean terminal path additionally requires a non-problem summary.
    live_shape = adjudicated_result(
        [
            finding(".github/AGENTS.md", 22, 0.60, "Lane-neutral duty may be narrowed"),
            finding("AGENTS.md", 248, 0.50, "Validation guidance may be narrowed"),
            finding(
                ".github/agent-governance/codex_cloud_environment.md",
                77,
                0.45,
                "Readback gate may lack a named actor",
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

    # #430's earlier-stage contract stays fail-closed: the same weak findings
    # without completed semantic adjudication do not get a clean disposition.
    early = {
        "summary": "Possible weak first-pass concern.",
        "findings": [finding("probe.py", 10, 0.55)],
        "_quality_retry_attempted": True,
    }
    expect_legacy_failure(module, early, config)

    # An attempted marker without model/count evidence is not enough to bypass
    # the historical terminal quality gate.
    incomplete_marker = {
        "summary": v57.CLEAN_SUMMARY,
        "findings": [finding("probe.py", 10, 0.55)],
        "_semantic_adjudication_attempted": True,
    }
    expect_legacy_failure(module, incomplete_marker, config)

    count_mismatch = adjudicated_result([finding("probe.py", 10, 0.55)])
    count_mismatch["_semantic_adjudication_output_findings"] = 2
    expect_legacy_failure(module, count_mismatch, config)

    # v35 sets this marker when the provider returned more adjudicated entries
    # than the configured cap. Even if the retained entries are otherwise valid
    # and below threshold, the discarded pre-cap response may have been malformed
    # and must never be reinterpreted as a clean result.
    overflow_trimmed = adjudicated_result([finding("probe.py", 10, 0.55)])
    overflow_trimmed["_semantic_adjudication_overflow_trimmed"] = 1
    expect_legacy_failure(module, overflow_trimmed, config)

    # The preexisting summary-only problem gate remains authoritative. A final
    # adjudicator that still says a correctness issue remains cannot be cleared
    # merely because its structured candidates are below the publication floor.
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

    # Honor the existing configuration switch as well: when the repository has
    # explicitly disabled the summary-only problem gate, v57 may use the same
    # bounded low-confidence disposition, but malformed/empty summaries are still
    # rejected before that policy switch is consulted.
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

    # Any v44/v55 scoped adjudication remains on its existing v52/v55 path.
    for scope in ("candidate-scoped", "broad"):
        scoped = adjudicated_result(
            [finding("probe.py", 10, 0.55)],
            v57.CLEAN_SUMMARY,
            context_scope=scope,
        )
        expect_legacy_failure(module, scoped, config)

    # Even fully adjudicated low-confidence output remains fail-closed when its
    # anchor is not an added changed line.
    unanchored = adjudicated_result(
        [finding("probe.py", 99, 0.55)],
        v57.CLEAN_SUMMARY,
    )
    expect_legacy_failure(module, unanchored, config)

    # Any at/above-floor candidate, malformed candidate, informational candidate,
    # or required deterministic sentinel preserves the existing fail-closed path.
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

    populated_replacement = finding("probe.py", 10, 0.55)
    populated_replacement["suggested_replacement"] = "replacement text must come from repair synthesis"
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

    # Exercise the actual composed production normalizer without any provider
    # call. This is the missing interaction regression from the live failure.
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    assert getattr(review, v57.APPLIED_MARKER, False) is True
    prod_config = review.load_pareto_context_config(
        ".github/dcoir_review/openrouter-pr-review-pareto.yml"
    )
    assert round(float(prod_config.minimum_confidence), 2) == 0.70
    assert review.hardened.summary_suggests_problem(v57.CLEAN_SUMMARY) is False

    production_live_shape = adjudicated_result(
        [
            finding(".github/AGENTS.md", 22, 0.60),
            finding("AGENTS.md", 248, 0.50),
            finding(".github/agent-governance/codex_cloud_environment.md", 77, 0.45),
        ],
        v57.CLEAN_SUMMARY,
    )
    assert review.split_findings_with_review_body_fallback(
        production_live_shape,
        prod_config,
        {
            (".github/AGENTS.md", 22): 1,
            ("AGENTS.md", 248): 2,
            (".github/agent-governance/codex_cloud_environment.md", 77): 3,
        },
        "+governance",
        [],
    ) == ([], [])
    assert production_live_shape["summary"] == v57.CLEAN_SUMMARY
    assert production_live_shape[v57.DISPOSITION_MARKER]["candidate_count"] == 3

    production_problem_summary = adjudicated_result(
        [finding("AGENTS.md", 248, 0.55)],
        "A correctness issue remains after semantic adjudication.",
    )
    try:
        review.split_findings_with_review_body_fallback(
            production_problem_summary,
            prod_config,
            {("AGENTS.md", 248): 1},
            "+governance",
            [],
        )
    except review.hardened.ReviewQualityError:
        pass
    else:
        raise AssertionError("production path bypassed the summary-only problem fail-closed gate")

    production_overflow = adjudicated_result(
        [finding("AGENTS.md", 248, 0.55)],
        v57.CLEAN_SUMMARY,
    )
    production_overflow["_semantic_adjudication_overflow_trimmed"] = 1
    try:
        review.split_findings_with_review_body_fallback(
            production_overflow,
            prod_config,
            {("AGENTS.md", 248): 1},
            "+governance",
            [],
        )
    except review.hardened.ReviewQualityError:
        pass
    else:
        raise AssertionError("production path converted overflow-trimmed adjudication to clean")

    production_early = {
        "summary": "Possible weak first-pass concern.",
        "findings": [finding("AGENTS.md", 248, 0.55)],
        "_quality_retry_attempted": True,
    }
    try:
        review.split_findings_with_review_body_fallback(
            production_early,
            prod_config,
            {("AGENTS.md", 248): 1},
            "+governance",
            [],
        )
    except review.hardened.ReviewQualityError:
        pass
    else:
        raise AssertionError("production path weakened #430 earlier-stage fail-closed behavior")

    print(
        "dcoir_review_required_runtime_patch_v57_selftest passed: "
        "only final v35 adjudication may cleanly withdraw fully valid changed-line "
        "sub-threshold candidates with a valid non-problem summary and no overflow; "
        "earlier/escalation/malformed/unanchored/sentinel/summary/overflow cases "
        "remain fail-closed and final-adjudicator telemetry stays classified"
    )


if __name__ == "__main__":
    main()
