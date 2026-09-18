#!/usr/bin/env python3
"""Offline publication/reporter regressions for verified-finding gate state verified_gate."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from dcoir_review import finding_verifier as v21
from dcoir_review import publication_disposition as publication
from dcoir_review import progress_reporting
from dcoir_review import verified_finding_gate as verified_gate
from dcoir_review import verified_finding_gate_prior as prior_io
from dcoir_review import verified_finding_gate_state as state
import dcoir_review_verified_finding_gate_selftest as core
from dcoir_review.entrypoint import DcoirReviewEntrypoint

ROOT = Path(__file__).resolve().parent.parent


def test_body_blocks_false_clean_without_duplicate_inline_publication() -> None:
    module = core.review_module()
    setattr(module, verified_gate._PRIOR_ATTR, core.blocked_prior())
    original_persist = prior_io.persist_gate_state
    try:
        prior_io.persist_gate_state = lambda *_args: True
        body = verified_gate.apply_gate_to_review_body(
            module, "v45 exact-head body", [], core.config(), core.NEW_HEAD
        )
    finally:
        prior_io.persist_gate_state = original_persist
    assert "v45 exact-head body" in body
    assert "Gate status: `BLOCKED`" in body
    assert "Carried unresolved prior verified findings: `1`" in body
    assert "src/b.py:20" in body
    active = getattr(module, verified_gate._STATE_ATTR)
    assert active["gate_status"] == "blocked"
    assert active["current_published_count"] == 0
    assert active["carried_unresolved_count"] == 1
    final = module.artifacts[state.FINAL_ARTIFACT_PATH]
    assert final["unresolved_finding_count"] == 1


def test_body_fails_closed_when_gate_state_cannot_persist() -> None:
    module = core.review_module()
    setattr(module, verified_gate._PRIOR_ATTR, core.blocked_prior())
    original_persist = prior_io.persist_gate_state
    try:
        prior_io.persist_gate_state = lambda *_args: False
        try:
            verified_gate.apply_gate_to_review_body(
                module, "v45 exact-head body", [], core.config(), core.NEW_HEAD
            )
        except core.ReviewQualityError as exc:
            assert "could not persist exact-head verified-finding gate state" in str(exc)
        else:
            raise AssertionError("gate-state persistence failure must block publication")
    finally:
        prior_io.persist_gate_state = original_persist
    assert not hasattr(module, verified_gate._STATE_ATTR)


def test_gate_stage_preserves_publication_disposition_and_adds_gate_telemetry() -> None:
    module = core.review_module()
    original_loader = prior_io.load_prior_gate_context
    updates: list[tuple[str, str]] = []
    item = core.current_finding("src/a.py", 10, "Current")
    publication.capture_verifier_disposition(
        module,
        [item],
        [item],
        {"head": {"sha": core.NEW_HEAD}},
    )
    try:
        prior_io.load_prior_gate_context = lambda *_args: core.blocked_prior()
        reporter = SimpleNamespace(update=lambda kind, text: updates.append((kind, text)))
        verified_gate.capture_prior_gate_context(
            module,
            SimpleNamespace(),
            {"head": {"sha": core.NEW_HEAD}},
            core.config(),
            reporter,
        )
        disposition = getattr(module, publication._DISPOSITION_ATTR)
        assert disposition["carried_unresolved_count"] == 1
        assert disposition["prior_gate_status"] == "blocked"
        assert disposition["incremental_gate_indeterminate"] is False
        assert updates and updates[-1][0] == "verified-gate-state"
        assert not hasattr(verified_gate, "_VERIFIER_STORAGE")
        assert not hasattr(verified_gate, "_BODY_STORAGE")
    finally:
        prior_io.load_prior_gate_context = original_loader

def test_completion_reporter_exposes_blocked_carried_state() -> None:
    module = core.review_module()
    progress_reporting.apply_pareto_context_module(module)
    setattr(
        module,
        verified_gate._STATE_ATTR,
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
    assert reporter.completed_at > 0
    assert reporter._last_published_stage == "completed"
    assert "Verified finding gate: `BLOCKED`." in reporter.updated_bodies[-1]
    assert "Carried unresolved prior verified findings: `2`." in reporter.updated_bodies[-1]


def test_completion_reporter_exposes_indeterminate_gate() -> None:
    module = core.review_module()
    progress_reporting.apply_pareto_context_module(module)
    setattr(
        module,
        verified_gate._STATE_ATTR,
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
    progress_reporting.apply_pareto_context_module(module)
    setattr(module, verified_gate._STATE_ATTR, {"gate_status": "clear"})
    reporter = module.ProgressReporter(core.config())
    reporter.complete("model", 0, "COMMENT")
    assert "legacy completion" in reporter.steps[-1][1]


def test_completion_reporter_patches_production_owner_aliases() -> None:
    module = core.review_module()
    original = module.ProgressReporter
    delattr(module, "ProgressReporter")
    module.base.ProgressReporter = original
    module.hardened.ProgressReporter = original
    progress_reporting.apply_pareto_context_module(module)
    assert module.base.ProgressReporter is module.hardened.ProgressReporter
    assert module.base.ProgressReporter is not original
    assert getattr(module.base.ProgressReporter, progress_reporting.OWNER_MARKER, False) is True
    setattr(
        module,
        verified_gate._STATE_ATTR,
        {
            "gate_status": "blocked",
            "carried_unresolved_count": 1,
            "indeterminate_prior_count": 0,
        },
    )
    reporter = module.base.ProgressReporter(core.config())
    reporter.complete("model", 0, "COMMENT")
    assert "gate BLOCKED by 1 carried unresolved prior verified finding" in reporter.steps[-1][1]


def test_production_registration() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.post_terminal_patch_module_names[-4:] == (
        "dcoir_review_required_runtime_patch_v44",
        "dcoir_review.publication_disposition",
        "dcoir_review_required_runtime_patch_v46",
        "dcoir_review.verified_finding_gate",
    )
    production = (ROOT / "openrouter-pr-review-pareto.yml").read_text(encoding="utf-8")
    assert "verified_finding_gate_state_review: true" in production
    assert "dcoir_review_verified_finding_gate_selftest.py" in production
    assert "dcoir_review_verified_finding_gate_publication_selftest.py" in production


def main() -> None:
    test_body_blocks_false_clean_without_duplicate_inline_publication()
    test_body_fails_closed_when_gate_state_cannot_persist()
    test_gate_stage_preserves_publication_disposition_and_adds_gate_telemetry()
    test_completion_reporter_exposes_blocked_carried_state()
    test_completion_reporter_exposes_indeterminate_gate()
    test_completion_reporter_delegates_when_gate_is_clear()
    test_completion_reporter_patches_production_owner_aliases()
    test_production_registration()
    print("dcoir_review_verified_finding_gate_publication_selftest passed")


if __name__ == "__main__":
    main()
