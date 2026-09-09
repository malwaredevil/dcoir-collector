#!/usr/bin/env python3
"""Deterministic regression checks for DCOIR Review v53 repair gating."""

from __future__ import annotations

import importlib

from dcoir_review.entrypoint import DcoirReviewEntrypoint


PATH = "probe.py"
DIFF = (
    "diff --git a/probe.py b/probe.py\n"
    "index 1111111..2222222 100644\n"
    "--- a/probe.py\n"
    "+++ b/probe.py\n"
    "@@ -1 +1 @@\n"
    "-value = 1\n"
    "+value = 2\n"
)


class FakeGH:
    def __init__(self) -> None:
        self.diff_calls = 0

    def get_pr_diff(self, pr_number: int) -> str:
        assert pr_number == 517
        self.diff_calls += 1
        return DIFF


class Reporter:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def update(self, stage: str, message: str) -> None:
        self.events.append((stage, message))


def finding(confidence, line: int, detector_suggestion: str = "") -> dict:
    return {
        "title": f"Finding {line}",
        "severity": "high",
        "confidence": confidence,
        "path": PATH,
        "line": line,
        "body": "Verifier-supported defect.",
        "suggested_replacement": detector_suggestion,
        "validation": "python3 -m py_compile probe.py",
    }


def marker(v25, item: dict) -> dict:
    value = item.get(v25.REPAIR_MARKER)
    assert isinstance(value, dict), item
    return value


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.execution_policy_patch_module_names[-1] == "dcoir_review_required_runtime_patch_v53"

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v21 = importlib.import_module("dcoir_review_required_runtime_patch_v21")
    v25 = importlib.import_module("dcoir_review_required_runtime_patch_v25")
    v33 = importlib.import_module("dcoir_review_required_runtime_patch_v33")
    v36 = importlib.import_module("dcoir_review_required_runtime_patch_v36")
    v53 = importlib.import_module("dcoir_review_required_runtime_patch_v53")
    assert getattr(review, v53.APPLIED_MARKER, False) is True

    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    assert config.fix_synthesis_min_confidence == 0.80
    assert v53.repair_confidence_floor(config) == 0.80
    assert v53.finding_confidence({"confidence": True}) is None
    assert v53.finding_confidence({"confidence": "nan"}) is None
    assert v53.finding_confidence({"confidence": 1.2}) is None

    original_verify = v21.verify_findings_for_publication
    original_build = v36._build_repair_set_for_finding
    original_debug = review.hardened.write_debug_json_artifact_safely
    calls: list[tuple[int, float, str, str]] = []
    metrics: list[tuple[str, dict]] = []

    def fake_verify(mod, findings, gh, pr, cfg, reporter):
        return [dict(item) for item in findings]

    def fake_build(mod, ordinal, item, gh, head_sha, pr_diff, right_line_index, cfg, file_cache):
        assert head_sha == "deadbeef"
        assert pr_diff == DIFF
        assert right_line_index[(PATH, 1)] == 2
        calls.append(
            (
                ordinal,
                float(item["confidence"]),
                str(item.get("suggested_replacement", "")),
                str(item.get("_detector_suggested_replacement", "")),
            )
        )
        result = dict(item)
        result[v25.REPAIR_MARKER] = {
            "version": v36.VERSION,
            "outcome": v36.REPAIR_SET_OUTCOME,
            "repair_set_id": f"R{ordinal:02d}",
            "path": PATH,
            "line": int(item["line"]),
            "edits": [],
            "edit_count": 0,
            "native_suggestion_count": 0,
            "guidance_edit_count": 0,
            "author_model": "anthropic/claude-opus-5",
            "critic_model": "openai/gpt-5.6-sol-pro",
            "critic_accepted": True,
        }
        return result

    def fake_debug(cfg, path, payload):
        if path == "metadata/repair-v53-metrics.json":
            metrics.append((path, dict(payload)))

    v21.verify_findings_for_publication = fake_verify
    v36._build_repair_set_for_finding = fake_build
    review.hardened.write_debug_json_artifact_safely = fake_debug
    try:
        # A below-floor verified finding remains published and must not consume
        # the one eligible repair slot. The at-floor finding is attempted; the
        # later above-floor finding is then budget-deferred.
        config.fix_synthesis_enabled = True
        config.fix_synthesis_min_confidence = 0.80
        config.fix_synthesis_max_findings = 1
        gh = FakeGH()
        reporter = Reporter()
        calls.clear()
        metrics.clear()
        result = review.synthesize_fixes_for_findings(
            [
                finding(0.79, 1, "detector output must never be trusted"),
                finding(0.80, 1, "also untrusted"),
                finding(0.95, 1),
            ],
            gh,
            {"number": 517, "head": {"sha": "deadbeef"}},
            {},
            config,
            reporter,
        )
        assert len(result) == 3
        first = marker(v25, result[0])
        second = marker(v25, result[1])
        third = marker(v25, result[2])
        assert first["outcome"] == v53.CONFIDENCE_DEFERRED_OUTCOME
        assert first["finding_confidence"] == 0.79
        assert first["repair_confidence_floor"] == 0.80
        assert result[0]["suggested_replacement"] == ""
        assert result[0]["_detector_suggested_replacement"] == "detector output must never be trusted"
        assert second["outcome"] == v36.REPAIR_SET_OUTCOME
        assert third["outcome"] == v33.DEFERRED_OUTCOME
        assert calls == [(2, 0.80, "", "also untrusted")], calls
        assert gh.diff_calls == 1
        assert metrics[-1][1]["repair_confidence_qualified"] == 2
        assert metrics[-1][1]["repair_confidence_deferred"] == 1
        assert metrics[-1][1]["repair_attempts"] == 1
        assert metrics[-1][1]["repair_budget_deferred"] == 1

        # Malformed/boolean/non-finite/out-of-range confidence fails closed for
        # repair only. It must not even fetch the PR diff because no repair call
        # can start, and every verified finding remains visible.
        config.fix_synthesis_max_findings = 8
        gh = FakeGH()
        reporter = Reporter()
        calls.clear()
        metrics.clear()
        result = review.synthesize_fixes_for_findings(
            [finding(True, 1), finding("not-a-number", 1), finding(float("nan"), 1), finding(1.2, 1)],
            gh,
            {"number": 517, "head": {"sha": "deadbeef"}},
            {},
            config,
            reporter,
        )
        assert len(result) == 4
        assert all(marker(v25, item)["outcome"] == v53.CONFIDENCE_DEFERRED_OUTCOME for item in result)
        assert calls == []
        assert gh.diff_calls == 0
        assert metrics[-1][1]["repair_confidence_deferred"] == 4
        assert metrics[-1][1]["repair_attempts"] == 0

        # Globally disabled repair synthesis preserves the existing v33 budget-
        # deferred contract rather than introducing a new confidence classification.
        config.fix_synthesis_enabled = False
        gh = FakeGH()
        reporter = Reporter()
        calls.clear()
        metrics.clear()
        result = review.synthesize_fixes_for_findings(
            [finding(0.99, 1), finding(0.20, 1)],
            gh,
            {"number": 517, "head": {"sha": "deadbeef"}},
            {},
            config,
            reporter,
        )
        assert len(result) == 2
        assert all(marker(v25, item)["outcome"] == v33.DEFERRED_OUTCOME for item in result)
        assert calls == []
        assert gh.diff_calls == 0
        assert metrics[-1][1]["repair_synthesis_enabled"] is False
        assert metrics[-1][1]["repair_confidence_deferred"] == 0
        assert metrics[-1][1]["repair_attempts"] == 0
        assert metrics[-1][1]["repair_budget_deferred"] == 2

        # With synthesis enabled and a zero floor, ordinary finite confidence
        # retains the historical all-eligible behavior within the count budget.
        config.fix_synthesis_enabled = True
        config.fix_synthesis_min_confidence = 0.0
        config.fix_synthesis_max_findings = 2
        gh = FakeGH()
        reporter = Reporter()
        calls.clear()
        metrics.clear()
        result = review.synthesize_fixes_for_findings(
            [finding(0.0, 1), finding(0.5, 1)],
            gh,
            {"number": 517, "head": {"sha": "deadbeef"}},
            {},
            config,
            reporter,
        )
        assert len(result) == 2
        assert [marker(v25, item)["outcome"] for item in result] == [
            v36.REPAIR_SET_OUTCOME,
            v36.REPAIR_SET_OUTCOME,
        ]
        assert [call[1] for call in calls] == [0.0, 0.5]
        assert gh.diff_calls == 1
    finally:
        v21.verify_findings_for_publication = original_verify
        v36._build_repair_set_for_finding = original_build
        review.hardened.write_debug_json_artifact_safely = original_debug

    print(
        "dcoir_review_required_runtime_patch_v53_selftest passed: configured repair confidence floor "
        "gates only repair synthesis while verified findings remain publishable"
    )


if __name__ == "__main__":
    main()
