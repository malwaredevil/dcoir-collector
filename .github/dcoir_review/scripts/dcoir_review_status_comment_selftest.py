#!/usr/bin/env python3
"""Stable contract checks for the canonical DCOIR Review status comment."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openrouter_pr_review as base
from dcoir_review.status import MutableReviewStatusComment, STATUS_MARKER


class FakeGitHub:
    def __init__(self, *, fail_writes: bool = False) -> None:
        self.repo = "example/dcoir"
        self.comments: list[dict[str, object]] = []
        self.create_count = 0
        self.update_count = 0
        self.fail_writes = fail_writes

    def request(self, method: str, path: str, body=None, accept: str = "application/vnd.github+json"):
        del body, accept
        assert method == "GET", (method, path)
        if "/comments?" in path:
            return list(self.comments)
        raise AssertionError(path)

    def create_issue_comment(self, number: int, body: str):
        del number
        if self.fail_writes:
            raise RuntimeError("synthetic create failure")
        self.create_count += 1
        comment = {
            "id": 1000 + self.create_count,
            "body": body,
            "user": {"login": "github-actions[bot]", "type": "Bot"},
        }
        self.comments.append(comment)
        return dict(comment)

    def update_issue_comment(self, comment_id: int, body: str):
        if self.fail_writes:
            raise RuntimeError("synthetic update failure")
        self.update_count += 1
        for comment in self.comments:
            if int(comment.get("id", 0) or 0) == int(comment_id):
                comment["body"] = body
                return dict(comment)
        raise AssertionError(comment_id)


def config() -> base.Config:
    return base.Config(
        commands=["/dcoir-review"],
        model="test/model",
        model_stack=["test/model"],
        max_prompt_chars=1000,
        max_files=10,
        max_inline_comments=5,
        request_changes_on_findings=False,
        minimum_confidence=0.7,
        validation_commands=[],
        guidance_files=[],
        ignored_authors=[],
        allowed_authors=[],
        post_summary_when_findings=False,
        include_confidence=False,
        redact_secret_literals=True,
        openrouter_max_attempts=1,
        openrouter_retry_max_seconds=1,
        ignored_providers=[],
        script_timeout_seconds=60,
        post_progress_comment=False,
        debug=False,
    )


def test_single_mutable_comment_and_rerun_reuse() -> None:
    gh = FakeGitHub()
    reporter = base.ProgressReporter(gh, 55, "/dcoir-review", config())
    reporter.start()
    assert gh.create_count == 1
    assert reporter.comment_id == 1001
    queued = str(gh.comments[0]["body"])
    assert STATUS_MARKER in queued
    assert "DCOIR Review — Queued" in queued
    assert "Exact reviewed commit: `pending`" in queued

    reporter.set_reviewed_commit("a" * 40)
    reporter.update("github", "fetching PR metadata")
    first_update_count = gh.update_count
    reporter.update("github", "fetching PR diff")
    assert gh.update_count == first_update_count, "same-stage updates must be bounded"

    reporter.set_formal_review(
        {
            "id": 444,
            "html_url": "https://github.com/example/dcoir/pull/55#pullrequestreview-444",
        }
    )
    reporter.complete("test/model", 2, "COMMENT")
    assert gh.create_count == 1
    completed = str(gh.comments[0]["body"])
    assert "DCOIR Review — Completed" in completed
    assert f"Exact reviewed commit: `{'a' * 40}`" in completed
    assert "pullrequestreview-444" in completed
    assert "authoritative review artifact" in completed

    rerun = base.ProgressReporter(gh, 55, "/dcoir-review", config())
    rerun.start()
    assert gh.create_count == 1, "rerun must reuse the canonical status comment"
    assert rerun.comment_id == 1001
    assert gh.update_count > first_update_count


def test_spoofed_user_marker_is_not_reused() -> None:
    gh = FakeGitHub()
    gh.comments.append(
        {
            "id": 9999,
            "body": f"{STATUS_MARKER}\nspoof",
            "user": {"login": "ordinary-user", "type": "User"},
        }
    )
    publisher = MutableReviewStatusComment(gh, 55)
    assert publisher.discover() == 0
    assert publisher.publish(f"{STATUS_MARKER}\nreal") is True
    assert publisher.comment_id != 9999
    assert gh.create_count == 1


def test_status_write_failures_are_observational() -> None:
    gh = FakeGitHub(fail_writes=True)
    publisher = MutableReviewStatusComment(gh, 55)
    assert publisher.publish(f"{STATUS_MARKER}\nqueued") is False
    assert publisher.comment_id == 0
    assert "synthetic create failure" in publisher.last_error

    reporter = base.ProgressReporter(gh, 55, "/dcoir-review", config())
    reporter.start()
    reporter.set_reviewed_commit("b" * 40)
    reporter.update("semantic", "running semantic pass")
    reporter.fail("synthetic review failure")
    assert reporter.comment_id == 0


def main() -> None:
    test_single_mutable_comment_and_rerun_reuse()
    test_spoofed_user_marker_is_not_reused()
    test_status_write_failures_are_observational()
    print("DCOIR mutable status comment self-test passed")


if __name__ == "__main__":
    main()
