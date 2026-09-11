#!/usr/bin/env python3
"""Regression tests for DCOIR Review runtime patch v55."""

from __future__ import annotations

import copy
import importlib
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from dcoir_review.entrypoint import DcoirReviewEntrypoint

ROOT = Path(__file__).resolve().parents[1]
import dcoir_review_required_runtime_patch_v33 as v33
import dcoir_review_required_runtime_patch_v35 as v35
import dcoir_review_required_runtime_patch_v37 as v37
import dcoir_review_required_runtime_patch_v44 as v44
import dcoir_review_required_runtime_patch_v51 as v51
import dcoir_review_required_runtime_patch_v55 as v55
import dcoir_review_execution as execution


def finding(line: int, title: str, *, confidence: float = 0.95) -> dict:
    return {
        "path": "sample.py",
        "line": line,
        "severity": "moderate",
        "confidence": confidence,
        "title": title,
        "body": f"{title} body",
        "suggested_replacement": "replacement",
    }


def config() -> SimpleNamespace:
    return SimpleNamespace(
        verifier_max_candidates=12,
        verifier_min_candidates=1,
        verifier_deep_min_candidates=2,
        verifier_deep_max_candidates=12,
        verifier_high_risk_max_candidates=12,
        minimum_confidence=0.7,
        review_mode="standard",
        context_mode="diff",
        quality_max_retries=1,
        semantic_adjudicator_max_findings=12,
        semantic_adjudicator_max_chars=12000,
        semantic_adjudicator_summary_max_chars=800,
        _review_state={"risk_sentinels": []},
    )


def fake_line_index(*lines: int) -> dict:
    return {"sample.py": set(lines)}


def run(payload: object, incoming: list[dict], *, line_index=None, cfg=None):
    hardened = SimpleNamespace()
    hardened.calls = 0
    hardened.non_actionable_finding_reason = lambda _item: ""
    hardened.required_risk_sentinels = lambda _items: []

    def fake_openrouter_review(_prompt, _schema, _config, _reporter=None):
        hardened.calls += 1
        return payload, "adjudicator-model", "default"

    hardened.openrouter_review = fake_openrouter_review
    hardened.ReviewQualityError = RuntimeError
    hardened.semantic_finding_identity = v51.semantic_finding_identity
    hardened.ranked_finding_identity = v51.ranked_finding_identity
    hardened.summary_suggests_problem = lambda summary: "problem" in str(summary).lower()

    rank_calls: list[list[dict]] = []

    def fake_rank(values, _config, _line_index, _risk_sentinels=None, _diff=""):
        copied = [dict(item) for item in values]
        rank_calls.append(copied)
        return copied

    hardened.rank_and_filter_findings = fake_rank
    module = SimpleNamespace(hardened=hardened)
    reporter = SimpleNamespace(events=[], update=lambda stage, message: reporter.events.append((stage, message)))
    result = v55.run_adjudicator(
        module,
        cfg or config(),
        reporter,
        incoming,
        line_index or fake_line_index(1, 2, 3, 4, 5),
        "diff",
    )
    return result, module, hardened, rank_calls, reporter


def fail_closed(payload: object, incoming: list[dict], text: str, *, line_index=None, cfg=None):
    hardened = SimpleNamespace()
    hardened.calls = 0
    hardened.non_actionable_finding_reason = lambda _item: ""
    hardened.required_risk_sentinels = lambda _items: []

    def fake_openrouter_review(_prompt, _schema, _config, _reporter=None):
        hardened.calls += 1
        return payload, "adjudicator-model", "default"

    hardened.openrouter_review = fake_openrouter_review
    hardened.ReviewQualityError = RuntimeError
    hardened.semantic_finding_identity = v51.semantic_finding_identity
    hardened.ranked_finding_identity = v51.ranked_finding_identity
    hardened.summary_suggests_problem = lambda summary: "problem" in str(summary).lower()
    hardened.rank_and_filter_findings = lambda values, _config, _line_index, _risk_sentinels=None, _diff="": [dict(item) for item in values]
    module = SimpleNamespace(hardened=hardened)
    reporter = SimpleNamespace(events=[], update=lambda stage, message: reporter.events.append((stage, message)))
    try:
        v55.run_adjudicator(
            module,
            cfg or config(),
            reporter,
            incoming,
            line_index or fake_line_index(1, 2, 3, 4, 5),
            "diff",
        )
    except RuntimeError as exc:
        assert text in str(exc)
    else:
        raise AssertionError(f"expected fail-closed error containing: {text}")
    return hardened.calls


def production_review():
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    return review


def production_config(review):
    return review.load_pareto_context_config(
        str(ROOT / "openrouter-pr-review-pareto.yml")
    )


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.telemetry_patch_module_names == (
        "dcoir_review_required_runtime_patch_v54",
    )
    post_telemetry = entrypoint.post_telemetry_patch_module_names
    assert post_telemetry[0] == "dcoir_review_required_runtime_patch_v58"
    assert post_telemetry[-3:] == (
        "dcoir_review_required_runtime_patch_v55",
        "dcoir_review_required_runtime_patch_v56",
        "dcoir_review_required_runtime_patch_v57",
    )
    assert post_telemetry.index("dcoir_review_required_runtime_patch_v55") < post_telemetry.index("dcoir_review_required_runtime_patch_v56")

    # v55 owns a new terminal seam rather than mutating the versioned v44 helper.
    original = getattr(execution, v55.RUN_STORAGE, None) or execution.run_adjudicator
    fake_apply_module = SimpleNamespace()
    v55.apply_pareto_context_module(fake_apply_module)
    assert getattr(fake_apply_module, v55.APPLIED_MARKER, False) is True
    assert execution.run_adjudicator is v55.run_adjudicator
    assert getattr(execution, v55.RUN_STORAGE) is original
    v55.apply_pareto_context_module(fake_apply_module)
    assert getattr(execution, v55.RUN_STORAGE) is original

    cfg = config()
    assert v33.verifier_candidate_limit(cfg) == 12

    # Canonical envelopes remain on the historical v37/v35 path.
    canonical = {"summary": "canonical", "findings": [finding(1, "canonical")]}
    (canonical_result, _model, _tier), _module, hardened, rank_calls, reporter = run(
        canonical, [finding(1, "upstream")]
    )
    assert canonical_result == canonical
    assert hardened.calls == 1
    assert rank_calls == []
    assert reporter.events == []

    # A valid bare finding-array envelope is recovered once and re-ranked.
    bare = [finding(1, "bare one"), finding(2, "bare two")]
    (recovered, _model, _tier), _module, hardened, rank_calls, reporter = run(
        bare, [finding(1, "upstream")]
    )
    assert recovered["summary"].startswith("Recovered semantic adjudication output")
    assert [item["title"] for item in recovered["findings"]] == ["bare one", "bare two"]
    assert recovered["_semantic_shape_recovery"] == "bare_finding_array"
    assert hardened.calls == 1
    assert len(rank_calls) == 1
    assert reporter.events and reporter.events[-1][0] == "quality-recovery"

    # A single finding object is recovered only when it is structurally valid.
    single = finding(3, "single")
    (single_result, _model, _tier), _module, hardened, rank_calls, _reporter = run(
        single, [finding(3, "upstream")]
    )
    assert [item["title"] for item in single_result["findings"]] == ["single"]
    assert single_result["_semantic_shape_recovery"] == "single_finding_object"
    assert hardened.calls == 1
    assert len(rank_calls) == 1

    # Mixed lists and malformed objects remain fail-closed.
    assert fail_closed([finding(1, "ok"), {"title": "bad"}], [finding(1, "upstream")], "non-canonical") == 1
    assert fail_closed({"title": "bad"}, [finding(1, "upstream")], "non-canonical") == 1

    # Recovery output still obeys anchoring and candidate-set constraints.
    assert fail_closed(
        [finding(99, "unanchored")],
        [finding(99, "upstream")],
        "outside the PR diff",
        line_index=fake_line_index(1, 2, 3),
    ) == 1

    assert fail_closed(
        [finding(2, "invented")],
        [finding(1, "upstream")],
        "outside the candidate set",
    ) == 1

    # Duplicate semantic identities collapse deterministically before the rank seam.
    duplicate_payload = [finding(1, "same"), finding(1, "same")]
    (deduped, _model, _tier), _module, _hardened, rank_calls, _reporter = run(
        duplicate_payload,
        [finding(1, "same")],
    )
    assert len(deduped["findings"]) == 1
    assert len(rank_calls) == 1 and len(rank_calls[0]) == 1

    # The configured recovery limit remains fail-closed.
    too_many_cfg = config()
    too_many_cfg.semantic_adjudicator_max_findings = 1
    assert fail_closed(
        [finding(1, "one"), finding(2, "two")],
        [finding(1, "one"), finding(2, "two")],
        "exceeded",
        cfg=too_many_cfg,
    ) == 1

    # Oversized recovery output is deterministically bounded by the active candidate set.
    tiny_chars = config()
    tiny_chars.semantic_adjudicator_max_chars = 1
    assert fail_closed(
        [finding(1, "one")],
        [finding(1, "one")],
        "exceeded",
        cfg=tiny_chars,
    ) == 1

    # Production composition exercises v55 with the full runtime chain active.
    review = production_review()
    assert getattr(review, v55.APPLIED_MARKER, False) is True
    production_cfg = production_config(review)
    assert production_cfg.semantic_adjudicator_max_findings >= 1

    # Production openrouter seam recovers a bare list while preserving telemetry wrapper shape.
    original_openrouter = review.hardened.openrouter_review
    original_rank = review.hardened.rank_and_filter_findings
    original_sentinels = review.hardened.required_risk_sentinels
    original_non_actionable = review.hardened.non_actionable_finding_reason
    original_summary_problem = review.hardened.summary_suggests_problem
    try:
        calls = 0

        def fake_openrouter(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            return [finding(1, "production bare")], "fake-model", "default"

        review.hardened.openrouter_review = fake_openrouter
        review.hardened.rank_and_filter_findings = lambda values, *_args, **_kwargs: [dict(item) for item in values]
        review.hardened.required_risk_sentinels = lambda _items: []
        review.hardened.non_actionable_finding_reason = lambda _item: ""
        review.hardened.summary_suggests_problem = lambda _summary: False
        reporter = SimpleNamespace(events=[], update=lambda stage, message: reporter.events.append((stage, message)))
        result, model, tier = execution.run_adjudicator(
            review,
            production_cfg,
            reporter,
            [finding(1, "production bare")],
            fake_line_index(1),
            "diff",
        )
        assert calls == 1
        assert model == "fake-model" and tier == "default"
        assert result["_semantic_shape_recovery"] == "bare_finding_array"
        assert result["findings"][0]["title"] == "production bare"
    finally:
        review.hardened.openrouter_review = original_openrouter
        review.hardened.rank_and_filter_findings = original_rank
        review.hardened.required_risk_sentinels = original_sentinels
        review.hardened.non_actionable_finding_reason = original_non_actionable
        review.hardened.summary_suggests_problem = original_summary_problem

    print("dcoir_review_required_runtime_patch_v55_selftest passed")


if __name__ == "__main__":
    main()
