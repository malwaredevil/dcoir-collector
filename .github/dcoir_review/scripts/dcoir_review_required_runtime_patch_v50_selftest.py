#!/usr/bin/env python3
"""Offline state/readback regressions for verified-finding gate state v50."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

import dcoir_review_required_runtime_patch_v21 as v21
import dcoir_review_required_runtime_patch_v43_reuse as v43_reuse
import dcoir_review_required_runtime_patch_v50_prior as prior_io
import dcoir_review_required_runtime_patch_v50_state as state

OLD_HEAD = "a" * 40
NEW_HEAD = "b" * 40


class ReviewQualityError(RuntimeError):
    pass


class FakeProgressReporter:
    def __init__(self, config):
        self.config = config
        self.steps: list[tuple[str, str]] = []
        self.updated_bodies: list[str] = []

    def complete(self, _model_used: str, findings_count: int, review_event: str) -> None:
        self._record(
            "completed",
            f"legacy completion; {findings_count} inline findings; event={review_event}",
        )
        self._update_comment(self._body("completed", final_lines=["legacy completion"]))

    def _record(self, stage: str, message: str) -> None:
        self.steps.append((stage, message))

    def _body(self, state_name: str, final_lines: list[str] | None = None) -> str:
        return "\n".join([state_name, *(final_lines or [])])

    def _update_comment(self, body: str) -> None:
        self.updated_bodies.append(body)


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


def review_module():
    artifacts: dict[str, object] = {}
    parsed = {"verified_finding_gate_state_review": True}
    module = SimpleNamespace()
    module.base = SimpleNamespace(
        github_safe_body=lambda value, limit=65535: str(value)[:limit],
        sanitize_debug_json_value=lambda value, _cfg: value,
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
    module.ProgressReporter = FakeProgressReporter
    module.artifacts = artifacts
    return module


def config(enabled: bool = True):
    return SimpleNamespace(verified_finding_gate_state_review=enabled, debug=False)


def blocked_prior() -> dict[str, object]:
    return {
        "status": "blocked",
        "carried_records": [prior_record("src/b.py", 20, "B")],
        "reason": "trusted-v50-gate-state",
        "source": "v50-state",
        "indeterminate_prior_count": 0,
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


def test_gate_state_persists_when_debug_is_disabled() -> None:
    module = review_module()
    value = state.compose_state([], blocked_prior(), NEW_HEAD, "126")
    previous = os.environ.get(v43_reuse.ARTIFACT_DIR_ENV)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ[v43_reuse.ARTIFACT_DIR_ENV] = tmp
            assert prior_io.persist_gate_state(module, config(), value) is True
            persisted = Path(tmp) / state.STATE_ARTIFACT_PATH
            assert persisted.is_file()
            assert json.loads(persisted.read_text(encoding="utf-8")) == value
    finally:
        if previous is None:
            os.environ.pop(v43_reuse.ARTIFACT_DIR_ENV, None)
        else:
            os.environ[v43_reuse.ARTIFACT_DIR_ENV] = previous


def main() -> None:
    test_partial_resolution_keeps_unchanged_findings_gate_active()
    test_all_prior_findings_changed_can_clear_after_current_revalidation()
    test_legacy_v45_migration_uses_published_inline_comments()
    test_legacy_nonzero_without_complete_inline_state_fails_closed()
    test_legacy_zero_finding_disposition_migrates_cleanly()
    test_gate_state_persists_when_debug_is_disabled()
    print("dcoir_review_required_runtime_patch_v50_selftest passed")


if __name__ == "__main__":
    main()
