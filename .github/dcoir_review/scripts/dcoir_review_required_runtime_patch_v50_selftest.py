#!/usr/bin/env python3
"""Offline regressions for unresolved verified-finding gate state v50."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v21 as v21
import dcoir_review_required_runtime_patch_v45 as v45
import dcoir_review_required_runtime_patch_v50 as v50
import dcoir_review_required_runtime_patch_v50_prior as prior_io
import dcoir_review_required_runtime_patch_v50_state as state
from dcoir_review.entrypoint import DcoirReviewEntrypoint

ROOT = Path(__file__).resolve().parent.parent
OLD_HEAD = "a" * 40
NEW_HEAD = "b" * 40


class ReviewQualityError(RuntimeError):
    pass


def prior_record(path: str, line: int, tag: str) -> dict[str, object]:
    return {
        "fingerprint": state._finding_fingerprint(path, line, tag),
        "path": path,
        "line": line,
        "severity": "high",
        "origin_reviewed_head": OLD_HEAD,
        "last_confirmed_head": OLD_HEAD,
        "status": "prior-unresolved",
        "source": "test",
    }


def current_finding(path: str, line: int, title: str) -> dict[str, object]:
    return {
        "path": path,
        "line": line,
        "title": title,
        "severity": "high",
        v21.VERIFIER_MARKER: {"supported": True, "head_sha": NEW_HEAD, "line": line},
    }


def test_partial_resolution_keeps_unchanged_findings_gate_active() -> None:
    records = [
        prior_record("src/a.py", 10, "A"),
        prior_record("src/b.py", 20, "B"),
        prior_record("src/c.py", 30, "C"),
    ]
    carried = state.carry_records(records, {"src/a.py"}, NEW_HEAD)
    assert {(item["path"], item["line"]) for item in carried} == {
        ("src/b.py", 20),
        ("src/c.py", 30),
    }
    prior = {
        "status": "blocked",
        "carried_records": carried,
        "reason": "trusted-v50-gate-state",
        "source": "v50-state",
        "indeterminate_prior_count": 0,
    }
    composed = state.compose_state([], prior, NEW_HEAD, "123")
    assert composed["gate_status"] == "blocked"
    assert composed["current_published_count"] == 0
    assert composed["carried_unresolved_count"] == 2
    assert len(composed["unresolved_findings"]) == 2


def test_all_prior_findings_changed_can_clear_after_current_revalidation() -> None:
    records = [prior_record("src/a.py", 10, "A"), prior_record("src/b.py", 20, "B")]
    carried = state.carry_records(records, {"src/a.py", "src/b.py"}, NEW_HEAD)
    prior = {
        "status": "clear",
        "carried_records": carried,
        "reason": "trusted-v50-gate-state",
        "source": "v50-state",
        "indeterminate_prior_count": 0,
    }
    composed = state.compose_state([], prior, NEW_HEAD, "124")
    assert composed["gate_status"] == "clear"
    assert composed["unresolved_findings"] == []


def test_legacy_v45_migration_uses_published_inline_comments() -> None:
    disposition = {"reviewed_head_sha": OLD_HEAD, "published_finding_count": 3}
    comments = [
        {"path": "src/a.py", "line": 10, "body": "**HIGH: A**\nEvidence"},
        {"path": "src/b.py", "line": 20, "body": "**HIGH: B**\nEvidence"},
        {"path": "src/c.py", "line": 30, "body": "**HIGH: C**\nEvidence"},
    ]
    migrated = state.migrate_legacy_v45(
        disposition, comments, OLD_HEAD, {"src/a.py"}, NEW_HEAD
    )
    assert migrated["status"] == "blocked"
    assert migrated["source"] == "legacy-v45-github-review-comments"
    assert {item["path"] for item in migrated["carried_records"]} == {
        "src/b.py",
        "src/c.py",
    }


def test_legacy_nonzero_without_complete_inline_state_fails_closed() -> None:
    disposition = {"reviewed_head_sha": OLD_HEAD, "published_finding_count": 3}
    migrated = state.migrate_legacy_v45(
        disposition,
        [{"path": "src/a.py", "line": 10, "body": "A"}],
        OLD_HEAD,
        {"src/a.py"},
        NEW_HEAD,
    )
    assert migrated["status"] == "indeterminate"
    assert migrated["indeterminate_prior_count"] == 3
    composed = state.compose_state([], migrated, NEW_HEAD, "125")
    assert composed["gate_status"] == "indeterminate"


def test_legacy_zero_finding_disposition_migrates_cleanly() -> None:
    migrated = state.migrate_legacy_v45(
        {"reviewed_head_sha": OLD_HEAD, "published_finding_count": 0},
        [],
        OLD_HEAD,
        set(),
        NEW_HEAD,
    )
    assert migrated["status"] == "clear"
    assert migrated["carried_records"] == []


def review_module():
    artifacts: dict[str, object] = {}
    parsed = {"verified_finding_gate_state_review": True}
    module = SimpleNamespace()
    module.base = SimpleNamespace(
        github_safe_body=lambda value, limit=65535: str(value)[:limit]
    )
    module.hardened = SimpleNamespace(
        ReviewQualityError=ReviewQualityError,
        parse_yaml_like_data=lambda _path: parsed,
        bool_value=lambda data, key, default: data.get(key, default),
        write_debug_json_artifact_safely=lambda _cfg, path, value: artifacts.__setitem__(
            path, value
        ),
        build_review_body_with_unanchored=lambda *_args, **_kwargs: "v45 exact-head body",
    )
    module.load_pareto_context_config = lambda _path: SimpleNamespace()
    module.artifacts = artifacts
    return module


def config(enabled: bool = True):
    return SimpleNamespace(verified_finding_gate_state_review=enabled)


def test_body_blocks_false_clean_without_duplicate_inline_publication() -> None:
    module = review_module()
    prior = {
        "status": "blocked",
        "carried_records": [prior_record("src/b.py", 20, "B")],
        "reason": "trusted-v50-gate-state",
        "source": "v50-state",
        "indeterminate_prior_count": 0,
    }
    setattr(module, v50._PRIOR_ATTR, prior)
    v50._patch_review_body(module)
    body = module.hardened.build_review_body_with_unanchored(
        {"summary": ""}, [], [], "model", config(), NEW_HEAD
    )
    assert "v45 exact-head body" in body
    assert "Gate status: `BLOCKED`" in body
    assert "Carried unresolved prior verified findings: `1`" in body
    assert "src/b.py:20" in body
    saved = module.artifacts[state.STATE_ARTIFACT_PATH]
    assert saved["gate_status"] == "blocked"
    assert saved["current_published_count"] == 0
    assert saved["carried_unresolved_count"] == 1
    final = module.artifacts[state.FINAL_ARTIFACT_PATH]
    assert final["unresolved_finding_count"] == 1


def test_verifier_wrapper_preserves_v45_and_adds_gate_telemetry() -> None:
    module = review_module()
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
        prior_io.load_prior_gate_context = lambda *_args: {
            "status": "blocked",
            "carried_records": [prior_record("src/b.py", 20, "B")],
            "reason": "trusted-v50-gate-state",
            "source": "v50-state",
            "indeterminate_prior_count": 0,
        }
        v50._patch_verifier(module)
        reporter = SimpleNamespace(update=lambda kind, text: updates.append((kind, text)))
        item = current_finding("src/a.py", 10, "Current")
        verified = v21.verify_findings_for_publication(
            module,
            [item],
            SimpleNamespace(),
            {"head": {"sha": NEW_HEAD}},
            config(),
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


def main() -> None:
    test_partial_resolution_keeps_unchanged_findings_gate_active()
    test_all_prior_findings_changed_can_clear_after_current_revalidation()
    test_legacy_v45_migration_uses_published_inline_comments()
    test_legacy_nonzero_without_complete_inline_state_fails_closed()
    test_legacy_zero_finding_disposition_migrates_cleanly()
    test_body_blocks_false_clean_without_duplicate_inline_publication()
    test_verifier_wrapper_preserves_v45_and_adds_gate_telemetry()
    test_production_registration()
    print("dcoir_review_required_runtime_patch_v50_selftest passed")


if __name__ == "__main__":
    main()
