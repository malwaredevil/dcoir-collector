#!/usr/bin/env python3
"""Regression checks for DCOIR Architecture-B incremental review frontier (v41)."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from types import SimpleNamespace

from dcoir_review.entrypoint import DcoirReviewEntrypoint


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.patch_module_names[-1] == "dcoir_review_required_runtime_patch_v31"
    assert entrypoint.terminal_patch_module_names == (
        "dcoir_review_required_runtime_patch_v41",
        "dcoir_review_required_runtime_patch_v42",
        "dcoir_review_required_runtime_patch_v43",
    )

    applied_modules: list[str] = []

    class RecordingEntrypoint(DcoirReviewEntrypoint):
        def import_module(self, module_name: str):
            return SimpleNamespace(
                apply_pareto_context_module=lambda _review, name=module_name: applied_modules.append(name)
            )

    recording_entrypoint = RecordingEntrypoint()
    recording_entrypoint.apply_runtime_patches(object())
    assert applied_modules == [
        *recording_entrypoint.patch_module_names,
        *recording_entrypoint.terminal_patch_module_names,
    ]
    applied_modules.clear()
    recording_entrypoint.apply_runtime_patches(object(), ("test-explicit-subset",))
    assert applied_modules == ["test-explicit-subset"]

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    v41 = importlib.import_module("dcoir_review_required_runtime_patch_v41")
    assert v41.TRUSTED_REVIEW_AUTHORS == frozenset({"github-actions[bot]"})
    assert v41.TRUSTED_WORKFLOW_PATH == ".github/workflows/openrouter-pr-review.yml"
    assert v41.PROVENANCE_PREFIX == "DCOIR review provenance: "

    base_a = "1" * 40
    base_b = "2" * 40
    captured_debug: dict[str, object] = {}
    original_debug = review.hardened.write_debug_json_artifact_safely
    original_deep_context = review.build_deep_context_block
    review.hardened.write_debug_json_artifact_safely = (
        lambda _config, path, value: captured_debug.__setitem__(path, value)
    )
    review.build_deep_context_block = lambda *_args, **_kwargs: ("BLOCK", "base context")
    v41.apply_pareto_context_module(review)

    class FakeClient(review.base.GitHubClient):
        def __init__(self, reviews, compare_status="ahead", merge_base="aaa", current_base=base_a, run_conclusion="success"):
            super().__init__("token", "malwaredevil/dcoir-collector")
            self.reviews = list(reviews)
            self.compare_status = compare_status
            self.merge_base = merge_base
            self.current_base = current_base
            self.run_conclusion = run_conclusion
            self.calls = []

        def request(self, method, path, body=None, accept="application/vnd.github+json"):
            self.calls.append((method, path, accept))
            if path == "/repos/malwaredevil/dcoir-collector/pulls/7":
                if accept.endswith(".diff") or accept == "application/vnd.github.v3.diff":
                    return "FULL-DIFF"
                return {"number": 7, "head": {"sha": "ccc"}, "base": {"sha": self.current_base}}
            if path.startswith("/repos/malwaredevil/dcoir-collector/pulls/7/reviews?"):
                return list(self.reviews)
            if path.startswith("/repos/malwaredevil/dcoir-collector/pulls/7/files?"):
                return [{"filename": "full.py", "status": "modified", "changes": 20}]
            if path == "/repos/malwaredevil/dcoir-collector/compare/aaa...ccc?per_page=1&page=1":
                return {
                    "status": self.compare_status,
                    "merge_base_commit": {"sha": self.merge_base},
                    "files": [{"filename": "delta.py", "status": "modified", "changes": 2}],
                }
            if path == "/repos/malwaredevil/dcoir-collector/compare/aaa...ccc":
                assert accept == "application/vnd.github.v3.diff"
                return "INCREMENTAL-DIFF"
            if path == "/repos/malwaredevil/dcoir-collector/actions/runs/123456":
                return {
                    "id": 123456,
                    "name": "28 Review - DCOIR Review | PR #7 | malwaredevil",
                    "path": ".github/workflows/openrouter-pr-review.yml",
                    "event": "issue_comment",
                    "head_branch": "main",
                    "head_sha": "d" * 40,
                    "status": "completed",
                    "conclusion": self.run_conclusion,
                    "actor": {"login": "malwaredevil"},
                }
            raise AssertionError(f"unexpected fake GitHub request: {method} {path} accept={accept}")

    old_env = {name: os.environ.get(name) for name in ("TRIGGER_COMMENT_BODY", "OPENROUTER_API_KEY", "GITHUB_RUN_ID", "GITHUB_WORKFLOW")}
    os.environ["OPENROUTER_API_KEY"] = "v41-selftest-signing-secret"
    provenance = v41.build_review_provenance_marker(
        "malwaredevil/dcoir-collector", 7, base_a, "aaa", "123456", "28 Review - DCOIR Review"
    )
    assert provenance.startswith(v41.PROVENANCE_PREFIX)
    assert "signature=" in provenance

    marker = review.base.MARKER
    context_marker = review.CONTEXT_REVIEW_MARKER
    compatible_body = (
        f"{marker}\n{context_marker} `diff`\n"
        f"Context readback: prior; {v41.ARCHITECTURE_CONTRACT_MARKER}; "
        f"{v41.BASE_CONTRACT_PREFIX}{base_a}; {provenance}"
    )
    architecture_without_base_body = (
        f"{marker}\n{context_marker} `diff`\nContext readback: prior; {v41.ARCHITECTURE_CONTRACT_MARKER}"
    )
    old_contract_body = f"{marker}\n{context_marker} `diff`\nContext readback: legacy"
    trusted_user = {"login": "github-actions[bot]"}
    old_review = {"id": 1, "commit_id": "999", "body": old_contract_body, "user": trusted_user}
    architecture_without_base_review = {"id": 2, "commit_id": "998", "body": architecture_without_base_body, "user": trusted_user}
    compatible_review = {"id": 3, "commit_id": "aaa", "body": compatible_body, "user": trusted_user}
    spoofed_human_review = {"id": 4, "commit_id": "bbb", "body": compatible_body, "user": {"login": "malwaredevil"}}

    try:
        os.environ["TRIGGER_COMMENT_BODY"] = "/dcoir-review"
        gh = FakeClient([old_review, architecture_without_base_review, compatible_review, spoofed_human_review])
        assert review.latest_compatible_context_review(gh, 7)["commit_id"] == "aaa"
        assert review.has_prior_successful_context_review(gh, 7)
        assert gh.get_pr_diff(7) == "INCREMENTAL-DIFF"
        assert gh.list_files(7) == [{"filename": "delta.py", "status": "modified", "changes": 2}]
        scope = getattr(gh, v41.SCOPE_CACHE_ATTR)
        assert scope["source"] == "incremental-reviewed-head"
        assert scope["prior_reviewed_head_sha"] == "aaa"
        assert scope["current_head_sha"] == "ccc"
        assert scope["prior_reviewed_base_sha"] == base_a
        assert scope["current_base_sha"] == base_a
        assert scope["compare_status"] == "ahead"
        assert scope["fallback_reason"] == ""

        gh_spoof_only = FakeClient([spoofed_human_review])
        assert review.latest_compatible_context_review(gh_spoof_only, 7) is None
        assert gh_spoof_only.get_pr_diff(7) == "FULL-DIFF"
        assert "first-pass-deep" in getattr(gh_spoof_only, v41.SCOPE_CACHE_ATTR)["fallback_reason"]

        gh_failed_run = FakeClient([compatible_review], run_conclusion="failure")
        assert review.latest_compatible_context_review(gh_failed_run, 7) is None
        assert gh_failed_run.get_pr_diff(7) == "FULL-DIFF"

        assert gh.list_files(7) == [{"filename": "delta.py", "status": "modified", "changes": 2}]
        assert gh.get_pr_diff(7) == "FULL-DIFF"

        os.environ["GITHUB_RUN_ID"] = "654321"
        os.environ["GITHUB_WORKFLOW"] = "28 Review - DCOIR Review"
        _block, summary = review.build_deep_context_block(
            gh,
            {"number": 7, "base": {"sha": base_a}, "head": {"sha": "ccc"}},
            [],
            object(),
            "diff",
        )
        assert v41.ARCHITECTURE_CONTRACT_MARKER in summary
        assert f"{v41.BASE_CONTRACT_PREFIX}{base_a}" in summary
        assert "incremental reviewed-head aaa -> ccc" in summary
        assert "workflow-run=654321" in summary
        assert "reviewed-head=ccc" in summary
        assert "signature=" in summary

        config = type("Config", (), {"debug": True})()
        review.hardened.write_debug_json_artifact_safely(config, "metadata/review-context.json", {"existing": True})
        metadata = captured_debug["metadata/review-context.json"]
        assert metadata["existing"] is True
        assert metadata["review_contract"] == v41.ARCHITECTURE_CONTRACT
        assert metadata["review_scope_source"] == "incremental-reviewed-head"
        assert metadata["prior_reviewed_head_sha"] == "aaa"
        assert metadata["review_scope_current_head_sha"] == "ccc"
        assert metadata["prior_reviewed_base_sha"] == base_a
        assert metadata["review_scope_current_base_sha"] == base_a
        assert metadata["review_scope_file_count"] == 1

        gh_old = FakeClient([old_review, architecture_without_base_review])
        assert not review.has_prior_successful_context_review(gh_old, 7)
        assert gh_old.get_pr_diff(7) == "FULL-DIFF"
        assert gh_old.list_files(7)[0]["filename"] == "full.py"
        assert "first-pass-deep" in getattr(gh_old, v41.SCOPE_CACHE_ATTR)["fallback_reason"]

        os.environ["TRIGGER_COMMENT_BODY"] = "/dcoir-review deep"
        gh_deep = FakeClient([compatible_review])
        assert gh_deep.get_pr_diff(7) == "FULL-DIFF"
        assert getattr(gh_deep, v41.SCOPE_CACHE_ATTR)["review_mode"] == "deep-forced"

        os.environ["TRIGGER_COMMENT_BODY"] = "/dcoir-review"
        gh_diverged = FakeClient([compatible_review], compare_status="diverged", merge_base="zzz")
        assert gh_diverged.get_pr_diff(7) == "FULL-DIFF"
        diverged_scope = getattr(gh_diverged, v41.SCOPE_CACHE_ATTR)
        assert "compare status is diverged" in diverged_scope["fallback_reason"]
        assert not review.has_prior_successful_context_review(gh_diverged, 7)
        production_config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
        assert review.review_mode_for_command("/dcoir-review", "/dcoir-review", production_config, False) == "first-pass-deep"
        assert review.review_mode_for_command("/dcoir-review diff", "/dcoir-review", production_config, False) == "diff"

        gh_wrong_base = FakeClient([compatible_review], compare_status="ahead", merge_base="bbb")
        assert gh_wrong_base.get_pr_diff(7) == "FULL-DIFF"
        assert "not the exact compare merge base" in getattr(gh_wrong_base, v41.SCOPE_CACHE_ATTR)["fallback_reason"]

        gh_base_moved = FakeClient([compatible_review], current_base=base_b)
        assert gh_base_moved.get_pr_diff(7) == "FULL-DIFF"
        base_moved_scope = getattr(gh_base_moved, v41.SCOPE_CACHE_ATTR)
        assert base_moved_scope["prior_reviewed_base_sha"] == base_a
        assert base_moved_scope["current_base_sha"] == base_b
        assert "PR base moved since prior review" in base_moved_scope["fallback_reason"]
    finally:
        for name, value in old_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        review.hardened.write_debug_json_artifact_safely = original_debug
        review.build_deep_context_block = original_deep_context

    source_root = Path(".github/dcoir_review/scripts")
    source = "".join(
        (source_root / name).read_text(encoding="utf-8")
        for name in (
            "dcoir_review_required_runtime_patch_v41.py",
            "dcoir_review_required_runtime_patch_v41_review_state.py",
            "dcoir_review_required_runtime_patch_v41_scope.py",
            "dcoir_review_required_runtime_patch_v41_hooks.py",
        )
    )
    for required in (
        "incremental-reviewed-head",
        "merge_base_commit",
        "ARCHITECTURE_CONTRACT_MARKER",
        "BASE_CONTRACT_PREFIX",
        "INITIAL_DIFF_CONSUMED_KEY",
        "TRUSTED_REVIEW_AUTHORS",
        "build_review_provenance_marker",
        "hmac.compare_digest",
    ):
        assert required in source
    for forbidden in ("git push", "create_commit(", "update_file(", "merge_pull_request"):
        assert forbidden not in source

    print("dcoir_review_required_runtime_patch_v41_selftest passed")


if __name__ == "__main__":
    main()
