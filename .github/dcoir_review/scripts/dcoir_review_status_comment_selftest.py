#!/usr/bin/env python3
"""Stable contract checks for the canonical DCOIR Review status comment."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openrouter_pr_review as base
from dcoir_review.status import (
    MutableReviewStatusComment,
    STATUS_MARKER,
    parse_status_metadata,
)


class FakeGitHub:
    def __init__(self, *, fail_writes: bool = False) -> None:
        self.repo = "example/dcoir"
        self.comments: list[dict[str, object]] = []
        self.review_comments: dict[int, list[dict[str, object]]] = {}
        self.create_count = 0
        self.update_count = 0
        self.fail_writes = fail_writes

    def request(self, method: str, path: str, body=None, accept: str = "application/vnd.github+json"):
        del body, accept
        if method == "GET" and "/issues/" in path and "/comments?" in path:
            return list(self.comments)
        if method == "GET" and "/reviews/" in path and "/comments?" in path:
            review_id = int(path.split("/reviews/", 1)[1].split("/", 1)[0])
            return list(self.review_comments.get(review_id, []))
        if method == "DELETE" and "/issues/comments/" in path:
            comment_id = int(path.rsplit("/", 1)[-1])
            self.comments = [c for c in self.comments if int(c.get("id", 0) or 0) != comment_id]
            return None
        raise AssertionError((method, path))

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


def config(*, debug: bool = False) -> base.Config:
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
        debug=debug,
    )


def prepare_completed_review(
    gh: FakeGitHub,
    *,
    head: str,
    findings: list[dict[str, object]],
    review_id: int,
    changed_files: list[dict[str, object]] | None = None,
) -> base.ProgressReporter:
    reporter = base.ProgressReporter(gh, 55, "/dcoir-review", config())
    reporter.start()
    reporter.set_reviewed_commit(head)
    reporter.set_context_mode("diff")
    reporter.set_changed_files(
        changed_files
        or [{"filename": "src/app.py", "status": "modified", "additions": 4, "deletions": 1}]
    )
    reporter.set_findings(findings)
    gh.review_comments[review_id] = [
        {
            "path": str(item.get("path", "")),
            "line": int(item.get("line", 0) or 0),
            "html_url": f"https://github.com/example/dcoir/pull/55#discussion_r{review_id}{index}",
        }
        for index, item in enumerate(findings, start=1)
    ]
    reporter.set_formal_review(
        {
            "id": review_id,
            "html_url": f"https://github.com/example/dcoir/pull/55#pullrequestreview-{review_id}",
        }
    )
    reporter.complete("test/model", len(findings), "COMMENT")
    return reporter


def test_single_mutable_comment_and_clean_overview() -> None:
    gh = FakeGitHub()
    reporter = base.ProgressReporter(gh, 55, "/dcoir-review", config())
    reporter.start()
    assert gh.create_count == 1
    assert reporter.comment_id == 1001
    queued = str(gh.comments[0]["body"])
    assert STATUS_MARKER in queued
    assert "Review queued" in queued
    assert "Detailed progress and diagnostics" not in queued

    reporter.set_reviewed_commit("a" * 40)
    reporter.set_context_mode("diff")
    reporter.set_changed_files(
        [{"filename": "src/app.py", "status": "modified", "additions": 2, "deletions": 1}]
    )
    reporter.update("github", "fetching PR metadata")
    first_update_count = gh.update_count
    reporter.update("github", "fetching PR diff")
    assert gh.update_count == first_update_count, "same-stage updates must be bounded"
    reporter.set_formal_review(
        {"id": 444, "html_url": "https://github.com/example/dcoir/pull/55#pullrequestreview-444"}
    )
    reporter.complete("test/model", 0, "COMMENT")

    completed = str(gh.comments[0]["body"])
    assert "DCOIR Review overview" in completed
    assert "🟢 Clean" in completed
    assert "**Review effort:** Lite" in completed
    assert "**Findings:** 0" in completed
    assert "What changed in this PR" in completed
    assert "Detailed progress and diagnostics" not in completed
    metadata = parse_status_metadata(completed)
    assert metadata["reviewed_head_sha"] == "a" * 40
    assert metadata["formal_review_id"] == 444
    assert metadata["context_mode"] == "diff"
    assert metadata["model_outcome"] == "test/model"

    rerun = base.ProgressReporter(gh, 55, "/dcoir-review", config())
    rerun.start()
    assert gh.create_count == 1, "rerun must reuse the canonical status comment"
    assert rerun.comment_id == 1001


def test_finding_links_severity_and_previously_missed() -> None:
    gh = FakeGitHub()
    head = "b" * 40
    first = [
        {"title": "First issue", "severity": "high", "path": "src/app.py", "line": 7},
    ]
    prepare_completed_review(gh, head=head, findings=first, review_id=500)
    body = str(gh.comments[0]["body"])
    assert "🟡 Changes recommended" in body
    assert "**Findings:** 1 high" in body
    assert "Open (1)" in body
    assert "discussion_r5001" in body

    second = first + [
        {"title": "Missed issue", "severity": "medium", "path": "src/lib.py", "line": 9},
    ]
    prepare_completed_review(gh, head=head, findings=second, review_id=501)
    body = str(gh.comments[0]["body"])
    assert gh.create_count == 1
    assert "Previously missed (1)" in body
    assert "Missed issue" in body
    assert "**Findings:** 1 high, 1 medium" in body


def test_resolved_since_last_review() -> None:
    gh = FakeGitHub()
    old_findings = [
        {"title": "Resolved issue", "severity": "medium", "path": "src/app.py", "line": 7},
        {"title": "Still open", "severity": "high", "path": "src/lib.py", "line": 9},
    ]
    prepare_completed_review(gh, head="c" * 40, findings=old_findings, review_id=600)
    prepare_completed_review(
        gh,
        head="d" * 40,
        findings=[old_findings[1]],
        review_id=601,
    )
    body = str(gh.comments[0]["body"])
    assert "Resolved since last review (1)" in body
    assert "Resolved issue" in body
    assert "Still open" in body


def test_failure_is_concise_and_debug_is_verbose() -> None:
    gh = FakeGitHub()
    reporter = base.ProgressReporter(gh, 55, "/dcoir-review", config())
    reporter.start()
    reporter.set_reviewed_commit("e" * 40)
    reporter.update("provider-attempt", "provider telemetry that must stay hidden")
    reporter.fail("synthetic provider failure detail")
    body = str(gh.comments[0]["body"])
    assert "🔴 Review failed" in body
    assert "provider telemetry that must stay hidden" not in body
    assert "synthetic provider failure detail" not in body
    assert "Detailed progress and diagnostics" not in body

    debug_gh = FakeGitHub()
    debug = base.ProgressReporter(debug_gh, 55, "/dcoir-review", config(debug=True))
    debug.start()
    debug.set_reviewed_commit("f" * 40)
    debug.set_context_mode("deep-forced")
    debug.update("provider-attempt", "provider telemetry retained for debug")
    debug.fail("synthetic debug failure detail")
    debug_body = str(debug_gh.comments[0]["body"])
    assert "Detailed progress and diagnostics" in debug_body
    assert "provider telemetry retained for debug" in debug_body
    assert "synthetic debug failure detail" in debug_body
    assert "Context mode: `deep-forced`" in debug_body


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


class RacingGitHub(FakeGitHub):
    def create_issue_comment(self, number: int, body: str):
        if not self.comments:
            self.comments.append(
                {
                    "id": 900,
                    "body": f"{STATUS_MARKER}\ncompeting",
                    "user": {"login": "github-actions[bot]", "type": "Bot"},
                }
            )
        return super().create_issue_comment(number, body)


def test_concurrent_creation_reconciles_to_earliest_comment() -> None:
    gh = RacingGitHub()
    publisher = MutableReviewStatusComment(gh, 55)
    assert publisher.publish(f"{STATUS_MARKER}\nqueued") is True
    canonical = [c for c in gh.comments if STATUS_MARKER in str(c.get("body", ""))]
    assert len(canonical) == 1, canonical
    assert publisher.comment_id == 900
    assert str(canonical[0]["body"]) == f"{STATUS_MARKER}\nqueued"


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
    test_single_mutable_comment_and_clean_overview()
    test_finding_links_severity_and_previously_missed()
    test_resolved_since_last_review()
    test_failure_is_concise_and_debug_is_verbose()
    test_spoofed_user_marker_is_not_reused()
    test_concurrent_creation_reconciles_to_earliest_comment()
    test_status_write_failures_are_observational()
    print("DCOIR Copilot-style mutable status comment self-test passed")


if __name__ == "__main__":
    main()
