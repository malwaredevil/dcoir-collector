#!/usr/bin/env python3
"""Regression checks for complete PR validation-surface readback."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).with_name("read-pr-validation-state.py")
spec = importlib.util.spec_from_file_location("read_pr_validation_state", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def base_snapshot():
    return {
        "pr": {
            "number": 602,
            "state": "open",
            "draft": True,
            "mergeable": True,
            "mergeable_state": "clean",
            "head": {"sha": "abc123"},
        },
        "check_runs": [],
        "workflow_runs": [],
        "combined_status": {"state": "success", "statuses": []},
        "review_threads": {"nodes": [], "pageInfo": {"hasNextPage": False}},
        "gaps": [],
    }


def test_separate_ghas_failure_blocks_even_when_actions_codeql_is_green() -> None:
    snapshot = base_snapshot()
    snapshot["workflow_runs"] = [
        {"id": 1, "name": "CodeQL Security", "status": "completed", "conclusion": "success"}
    ]
    snapshot["check_runs"] = [
        {"id": 10, "name": "analyze / CodeQL (python)", "status": "completed", "conclusion": "success", "output": {}},
        {"id": 11, "name": "analyze / CodeQL (actions)", "status": "completed", "conclusion": "success", "output": {}},
        {"id": 12, "name": "CodeQL", "status": "completed", "conclusion": "failure", "output": {"title": "2 new alerts"}},
    ]
    result = mod.evaluate_snapshot(snapshot, "abc123")
    assert not result["ready"]
    assert any("CodeQL" in item and "2 new alerts" in item for item in result["blockers"]), result


def test_successful_codeql_check_with_new_alert_title_still_blocks() -> None:
    snapshot = base_snapshot()
    snapshot["check_runs"] = [
        {"id": 12, "name": "CodeQL", "status": "completed", "conclusion": "success", "output": {"title": "1 new alert"}}
    ]
    result = mod.evaluate_snapshot(snapshot, "abc123")
    assert not result["ready"], result
    assert any("reports new alerts" in item for item in result["blockers"]), result


def test_all_green_surfaces_pass() -> None:
    snapshot = base_snapshot()
    snapshot["workflow_runs"] = [
        {"id": 1, "name": "CodeQL Security", "status": "completed", "conclusion": "success"},
        {"id": 2, "name": "Code scanning AI findings", "status": "completed", "conclusion": "success"},
    ]
    snapshot["check_runs"] = [
        {"id": 10, "name": "CodeQL", "status": "completed", "conclusion": "success", "output": {}},
        {"id": 11, "name": "Dependency Review", "status": "completed", "conclusion": "success", "output": {}},
    ]
    result = mod.evaluate_snapshot(snapshot, "abc123")
    assert result["ready"], result


def test_empty_legacy_status_surface_is_not_pending() -> None:
    snapshot = base_snapshot()
    snapshot["check_runs"] = [
        {"id": 10, "name": "CodeQL", "status": "completed", "conclusion": "success", "output": {}}
    ]
    snapshot["combined_status"] = {"state": "pending", "total_count": 0, "statuses": []}
    result = mod.evaluate_snapshot(snapshot, "abc123")
    assert not result["pending"], result
    assert result["ready"], result


def test_all_blocking_check_conclusions_are_blockers() -> None:
    for conclusion in sorted(mod.BLOCKING_CONCLUSIONS):
        snapshot = base_snapshot()
        snapshot["check_runs"] = [
            {"id": 10, "name": f"probe-{conclusion}", "status": "completed", "conclusion": conclusion, "output": {}}
        ]
        result = mod.evaluate_snapshot(snapshot, "abc123")
        assert result["blockers"], (conclusion, result)
        assert not result["ready"], (conclusion, result)


def test_skipped_and_neutral_checks_are_visible_but_not_blockers() -> None:
    for conclusion in ("skipped", "neutral", "success"):
        snapshot = base_snapshot()
        snapshot["check_runs"] = [
            {"id": 10, "name": f"probe-{conclusion}", "status": "completed", "conclusion": conclusion, "output": {}}
        ]
        result = mod.evaluate_snapshot(snapshot, "abc123")
        assert not result["blockers"], (conclusion, result)
        assert not result["pending"], (conclusion, result)


def test_workflow_failure_legacy_failure_merge_conflict_and_pagination_gap_block_or_gap() -> None:
    snapshot = base_snapshot()
    snapshot["check_runs"] = [
        {"id": 10, "name": "CodeQL", "status": "completed", "conclusion": "success", "output": {}}
    ]
    snapshot["workflow_runs"] = [
        {"id": 20, "name": "Code scanning AI", "status": "completed", "conclusion": "failure"}
    ]
    snapshot["combined_status"] = {
        "state": "failure", "total_count": 1, "statuses": [{"context": "legacy-ci", "state": "failure"}]
    }
    snapshot["pr"]["mergeable"] = False
    snapshot["pr"]["mergeable_state"] = "dirty"
    snapshot["review_threads"] = {"nodes": [], "pageInfo": {"hasNextPage": True}}
    result = mod.evaluate_snapshot(snapshot, "abc123")
    assert any("workflow run failed" in item for item in result["blockers"]), result
    assert any("commit status failed" in item for item in result["blockers"]), result
    assert any("merge conflicts" in item for item in result["blockers"]), result
    assert any("pagination" in item for item in result["gaps"]), result
    assert not result["ready"], result


def test_missing_check_collection_is_a_gap() -> None:
    snapshot = base_snapshot()
    result = mod.evaluate_snapshot(snapshot, "abc123")
    assert any("no commit check runs" in item for item in result["gaps"]), result
    assert not result["ready"], result


def test_pending_status_thread_and_head_drift_are_not_green() -> None:
    snapshot = base_snapshot()
    snapshot["check_runs"] = [
        {"id": 10, "name": "CodeQL", "status": "in_progress", "conclusion": None, "output": {}}
    ]
    snapshot["combined_status"] = {"state": "pending", "statuses": [{"context": "legacy-ci", "state": "pending"}]}
    snapshot["review_threads"] = {"nodes": [{"id": "thread-1", "isResolved": False}], "pageInfo": {"hasNextPage": False}}
    result = mod.evaluate_snapshot(snapshot, "different")
    assert not result["ready"]
    assert any("head mismatch" in item for item in result["blockers"])
    assert any("unresolved review threads" in item for item in result["blockers"])
    assert result["pending"]


def main() -> None:
    test_separate_ghas_failure_blocks_even_when_actions_codeql_is_green()
    test_successful_codeql_check_with_new_alert_title_still_blocks()
    test_all_green_surfaces_pass()
    test_empty_legacy_status_surface_is_not_pending()
    test_all_blocking_check_conclusions_are_blockers()
    test_skipped_and_neutral_checks_are_visible_but_not_blockers()
    test_workflow_failure_legacy_failure_merge_conflict_and_pagination_gap_block_or_gap()
    test_missing_check_collection_is_a_gap()
    test_pending_status_thread_and_head_drift_are_not_green()
    print("dcoir_review_pr_validation_readback_selftest passed")


if __name__ == "__main__":
    main()
