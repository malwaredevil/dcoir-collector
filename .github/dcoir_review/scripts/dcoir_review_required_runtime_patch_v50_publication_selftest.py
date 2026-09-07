#!/usr/bin/env python3
"""Offline publication/reporter regressions for verified-finding gate state v50."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v21 as v21
import dcoir_review_required_runtime_patch_v45 as v45
import dcoir_review_required_runtime_patch_v50 as v50
import dcoir_review_required_runtime_patch_v50_prior as prior_io
import dcoir_review_required_runtime_patch_v50_state as state
import dcoir_review_required_runtime_patch_v50_selftest as core
from dcoir_review.entrypoint import DcoirReviewEntrypoint

ROOT = Path(__file__).resolve().parent.parent


def test_body_blocks_false_clean_without_duplicate_inline_publication() -> None:
    module = core.review_module()
    setattr(module, v50._PRIOR_ATTR, core.blocked_prior())
    original_persist = prior_io.persist_gate_state
    try:
        prior_io.persist_gate_state = lambda *_args: True
        v50._patch_review_body(module)
        body = module.hardened.build_review_body_with_unanchored(
            {"summary": ""}, [], [], "model", core.config(), core.NEW_HEAD
        )
    finally:
        prior_io.persist_gate_state = original_persist
    assert "v45 exact-head body" in body
    assert "Gate status: `BLOCKED`" in body
    assert "Carried unresolved prior verified findings: `1`" in body
    assert "src/b.py:20" in body
    active = getattr(module, v50._STATE_ATTR)
    assert active["gate_status"] == "blocked"
    assert active["current_published_count"] == 0
    assert active["carried_unresolved_count"] == 1
    final = module.artifacts[state.FINAL_ARTIFACT_PATH]
    assert final["unresolved_finding_count"] == 1


def test_body_fails_closed_when_gate_state_cannot_persist() -> None:
    module = core.review_module()
    setattr(module, v50._PRIOR_ATTR, core.blocked_prior())
    original_persist = prior_io.persist_gate_state
    try:
        prior_io.persist_gate_state = lambda *_args: False
        v50._patch_review_body(module)
        try:
            module.hardened.build_review_body_with_unanchored(
                {"summary": ""}, [], [], "model", core.config(), core.NEW_HEAD
            )
        except core.ReviewQualityError as exc:
            assert "could not persist exact-head verified-finding gate state" in str(exc)
        else:
            raise AssertionError("gate-state persistence failure must block publication")
    finally:
        prior_io.persist_gate_state = original_persist
    assert not hasattr(module, v50._STATE_ATTR)


def test_verifier_wrapper_preserves_v45_and_adds_gate_telemetry() -> None:
    module = core.review_module()
    original = v21.verify_findings_for_publication
    stored = getattr(v21, v50._VERIFIER_STORAGE, None)
    had_stored = hasattr(v21, v50._VERIFIER_STORAGE)
    original_loader = prior_io.load_prior_gate_context
    updates: list[tuple[str, str]] = []
    try:
        def prior_verifier(review_module, items, _gh, pr, _cfg, _reporter):
            setattr(
                review_module,
                v45._DISPOSITION_ATTR,
                {
                    "reviewed_head_sha": pr["head"]["sha"],
                    "verifier_candidate_count": len(items),
                    "verifier_supported_count": len(items),
                    "verifier_suppressed_count": 0,
                },
            )
            return items

        v21.verify_findings_for_publication = prior_verifier
        if hasattr(v21, v50._VERIFIER_STORAGE):
            delattr(v21, v50._VERIFIER_STORAGE)
        prior_io.load_prior_gate_context = lambda *_args: core.blocked_prior()
        v50._patch_verifier(module)
        reporter = SimpleNamespace(update=lambda kind, text: updates.append((kind, text)))
        item = core.current_finding("src/a.py", 10, "Current")
        verified = v21.verify_findings_for_publication(
            module,
            [item],
            SimpleNamespace(),
            {"head": {"sha": core.NEW_HEAD}},
            core.config(),
            reporter,
        )
        assert verified == [item]
        disposition = getattr(module, v45._DISPOSITION_ATTR)
        assert disposition["carried_unresolved_count"] == 1
        assert disposition["prior_gate_status"] == "blocked"
        assert disposition["incremental_gate_indeterminate"] is False
        assert updates and updates[-1][0] == "verified-gate-state"
    finally:
        v21.verify_findings_for_publication = original
        prior_io.load_prior_gate_context = original_loader
        if had_stored:
            setattr(v21, v50._VERIFIER_STORAGE, stored)
        elif hasattr(v21, v50._VERIFIER_STORAGE):
            delattr(v21, v50._VERIFIER_STORAGE)


def test_completion_reporter_exposes_blocked_carried_state() -> None:
    module = core.review_module()
    v50._patch_progress_reporter(module)
    setattr(
        module,
        v50._STATE_ATTR,
        {
            "gate_status": "blocked",
            "carried_unresolved_count": 2,
            "indeterminate_prior_count": 0,
        },
    )
    reporter = module.ProgressReporter(core.config())
    reporter.complete("model", 0, "COMMENT")
    assert reporter.steps[-1][0] == "completed"
    assert "0 new inline findings" in reporter.steps[-1][1]
    assert "gate BLOCKED by 2 carried unresolved prior verified findings" in reporter.steps[-1][1]
    assert "legacy completion" not in reporter.steps[-1][1]
    assert "Verified finding gate: `BLOCKED`." in reporter.updated_bodies[-1]
    assert "Carried unresolved prior verified findings: `2`." in reporter.updated_bodies[-1]


def test_completion_reporter_exposes_indeterminate_gate() -> None:
    module = core.review_module()
    v50._patch_progress_reporter(module)
    setattr(
        module,
        v50._STATE_ATTR,
        {
            "gate_status": "indeterminate",
            "carried_unresolved_count": 0,
            "indeterminate_prior_count": 3,
        },
    )
    reporter = module.ProgressReporter(core.config())
    reporter.complete("model", 0, "COMMENT")
    assert "0 new inline findings" in reporter.steps[-1][1]
    assert "gate INDETERMINATE/BLOCKED" in reporter.steps[-1][1]
    assert "known_prior=3" in reporter.steps[-1][1]
    assert "Verified finding gate: `INDETERMINATE / BLOCKED`." in reporter.updated_bodies[-1]


def test_completion_reporter_delegates_when_gate_is_clear() -> None:
    module = core.review_module()
    v50._patch_progress_reporter(module)
    setattr(module, v50._STATE_ATTR, {"gate_status": "clear"})
    reporter = module.ProgressReporter(core.config())
    reporter.complete("model", 0, "COMMENT")
    assert "legacy completion" in reporter.steps[-1][1]


def test_production_registration() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.post_terminal_patch_module_names[-4:] == (
        "dcoir_review_required_runtime_patch_v44",
        "dcoir_review_required_runtime_patch_v45",
        "dcoir_review_required_runtime_patch_v46",
        "dcoir_review_required_runtime_patch_v50",
    )
    production = (ROOT / "openrouter-pr-review-pareto.yml").read_text(encoding="utf-8")
    assert "verified_finding_gate_state_review: true" in production
    assert "dcoir_review_required_runtime_patch_v50_selftest.py" in production
    assert "dcoir_review_required_runtime_patch_v50_publication_selftest.py" in production


def main() -> None:
    test_body_blocks_false_clean_without_duplicate_inline_publication()
    test_body_fails_closed_when_gate_state_cannot_persist()
    test_verifier_wrapper_preserves_v45_and_adds_gate_telemetry()
    test_completion_reporter_exposes_blocked_carried_state()
    test_completion_reporter_exposes_indeterminate_gate()
    test_completion_reporter_delegates_when_gate_is_clear()
    test_production_registration()
    print("dcoir_review_required_runtime_patch_v50_publication_selftest passed")


if __name__ == "__main__":
    main()
