#!/usr/bin/env python3
"""Deterministic regressions for DCOIR Review v57 terminal disposition."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

from dcoir_review.entrypoint import DcoirReviewEntrypoint
import dcoir_review_required_runtime_patch_v57 as v57


class FakeHardened:
    ReviewQualityError = RuntimeError

    def __init__(self) -> None:
        self.review_prompts: list[str] = []
        self.debug_artifacts: dict[str, Any] = {}
        self.force_required_sentinel = False

    def openrouter_review(self, prompt, _schema, _config, _reporter=None):
        self.review_prompts.append(str(prompt))
        return {"summary": "clean", "findings": []}, "fake-model", "default"

    def required_risk_sentinels(self, values):
        return list(values) if self.force_required_sentinel else []

    @staticmethod
    def non_actionable_finding_reason(item) -> str:
        return str(item.get("_non_actionable_reason", "") or "") if isinstance(item, dict) else "invalid"

    def write_debug_json_artifact_safely(self, _config, path: str, payload: Any) -> None:
        self.debug_artifacts[path] = payload


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


def adjudicated_result(findings: list[dict[str, Any]], summary: str = "Adjudicated hypotheses remain.") -> dict[str, Any]:
    return {
        "summary": summary,
        "findings": findings,
        "_semantic_adjudication_attempted": True,
        "_semantic_adjudication_model": "anthropic/claude-opus-5",
        "_semantic_adjudication_output_findings": len(findings),
    }


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

    config = SimpleNamespace(minimum_confidence=0.70)
    module = FakeModule()
    v57.apply_pareto_context_module(module)
    assert getattr(module, v57.APPLIED_MARKER, False) is True
    stored_review = getattr(module.hardened, v57.REVIEW_STORAGE)
    stored_split = getattr(module, v57.SPLIT_STORAGE)
    v57.apply_pareto_context_module(module)
    assert getattr(module.hardened, v57.REVIEW_STORAGE) is stored_review
    assert getattr(module, v57.SPLIT_STORAGE) is stored_split

    # Semantic adjudicators receive the active publication floor, while other
    # model stages keep their prompt unchanged.
    semantic_prompt = (
        "Final semantic adjudication pass.\n\n"
        "Publication-quality rules:\n"
        "- Return only distinct root-cause defects."
    )
    module.hardened.openrouter_review(semantic_prompt, {}, config, None)
    injected = module.hardened.review_prompts[-1]
    assert v57.PROMPT_MARKER in injected
    assert "0.70" in injected
    assert "empty findings list and a clean summary" in injected
    assert injected.count(v57.PROMPT_MARKER) == 1

    ordinary_prompt = "Routine per-file review prompt."
    module.hardened.openrouter_review(ordinary_prompt, {}, config, None)
    assert module.hardened.review_prompts[-1] == ordinary_prompt

    # Re-injection is idempotent for an already annotated semantic prompt.
    reinjected = v57._inject_publication_floor(injected, config)
    assert reinjected == injected

    # Exact live run 34566845633 terminal shape: semantic adjudication completed
    # and retained only 0.60/0.50/0.45 hypotheses below the 0.70 publication floor.
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
        "Three possible concerns remain after semantic adjudication.",
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
        "summary": "Incomplete semantic metadata.",
        "findings": [finding("probe.py", 10, 0.55)],
        "_semantic_adjudication_attempted": True,
    }
    expect_legacy_failure(module, incomplete_marker, config)

    count_mismatch = adjudicated_result([finding("probe.py", 10, 0.55)])
    count_mismatch["_semantic_adjudication_output_findings"] = 2
    expect_legacy_failure(module, count_mismatch, config)

    # Even fully adjudicated low-confidence output remains fail-closed when its
    # anchor is not an added changed line.
    unanchored = adjudicated_result(
        [finding("probe.py", 99, 0.55)],
        "Low-confidence candidate anchored outside the changed diff.",
    )
    expect_legacy_failure(module, unanchored, config)

    # Any at/above-floor candidate, malformed candidate, informational candidate,
    # or required deterministic sentinel preserves the existing fail-closed path.
    at_floor = adjudicated_result([finding("probe.py", 10, 0.70)], "Candidate at the publication floor.")
    expect_legacy_failure(module, at_floor, config)

    mixed = adjudicated_result(
        [finding("probe.py", 10, 0.55), finding("probe.py", 11, 0.90)],
        "Mixed confidence candidates.",
    )
    expect_legacy_failure(module, mixed, config)

    malformed = finding("probe.py", 10, 0.55)
    malformed["confidence"] = 10**400
    expect_legacy_failure(
        module,
        adjudicated_result([malformed], "Malformed confidence."),
        config,
    )

    informational = finding("probe.py", 10, 0.55)
    informational["_non_actionable_reason"] = "informational-only"
    expect_legacy_failure(
        module,
        adjudicated_result([informational], "Informational candidate."),
        config,
    )

    module.hardened.force_required_sentinel = True
    try:
        expect_legacy_failure(
            module,
            adjudicated_result(
                [finding("probe.py", 10, 0.55)],
                "Required sentinel remains.",
            ),
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
        "Adjudicator retained only uncertain hypotheses.",
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
        "completed semantic adjudication may cleanly withdraw only fully valid "
        "changed-line sub-threshold candidates while earlier/malformed/unanchored/sentinel cases remain fail-closed"
    )


if __name__ == "__main__":
    main()
