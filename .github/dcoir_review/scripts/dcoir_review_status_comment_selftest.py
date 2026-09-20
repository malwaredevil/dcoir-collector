#!/usr/bin/env python3
"""Stable contract checks for the canonical DCOIR Review status comment."""

from __future__ import annotations

from pathlib import Path
import hashlib
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openrouter_pr_review as base
from dcoir_review import status_overview, status_overview_support, status_snapshot
from dcoir_review import verified_finding_gate_state
from dcoir_review.status import MutableReviewStatusComment, STATUS_MARKER
from dcoir_review.status_overview import (
    MAX_STATUS_METADATA_ENCODED_CHARS,
    encode_status_metadata,
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


def test_large_reruns_keep_complete_identity_index() -> None:
    findings = [
        {
            "title": f"Finding {index}",
            "severity": "medium",
            "path": f"src/module_{index:02d}.py",
            "line": index + 1,
        }
        for index in range(20)
    ]

    same_head_gh = FakeGitHub()
    prepare_completed_review(
        same_head_gh,
        head="3" * 40,
        findings=findings,
        review_id=540,
    )
    first_body = str(same_head_gh.comments[0]["body"])
    first_metadata = parse_status_metadata(first_body)
    assert len(first_metadata["open_findings"]) == 12
    assert len(first_metadata["open_finding_identities"]) == 20
    assert first_metadata["finding_identity_index_complete"] is True

    prepare_completed_review(
        same_head_gh,
        head="3" * 40,
        findings=findings,
        review_id=541,
    )
    unchanged_body = str(same_head_gh.comments[0]["body"])
    assert "Previously missed" not in unchanged_body

    prepare_completed_review(
        same_head_gh,
        head="3" * 40,
        findings=[
            *findings,
            {
                "title": "New finding",
                "severity": "high",
                "path": "src/new.py",
                "line": 99,
            },
        ],
        review_id=542,
    )
    new_body = str(same_head_gh.comments[0]["body"])
    assert "Previously missed (1)" in new_body
    assert "New finding" in new_body

    changed_head_gh = FakeGitHub()
    prepare_completed_review(
        changed_head_gh,
        head="4" * 40,
        findings=findings,
        review_id=543,
    )
    prepare_completed_review(
        changed_head_gh,
        head="5" * 40,
        findings=findings[:-1],
        review_id=544,
    )
    changed_body = str(changed_head_gh.comments[0]["body"])
    assert "Resolved since last review (1)" in changed_body
    assert "1 additional resolved finding" in changed_body


def test_untrusted_markdown_is_rendered_safely() -> None:
    gh = FakeGitHub()
    prepare_completed_review(
        gh,
        head="1" * 40,
        findings=[
            {
                "title": "![Review approved](https://example.com/approved.svg) `\n\n### forged",
                "severity": "high",
                "path": "src/weird`\n\n### forged.py",
                "line": 7,
            },
        ],
        review_id=550,
        changed_files=[
            {
                "filename": "docs/![Review approved](https://example.com/approved.svg)`\n\n### forged.md",
                "status": "modified",
                "additions": 3,
                "deletions": 1,
            }
        ],
    )
    body = str(gh.comments[0]["body"])
    assert "![Review approved](https://example.com/approved.svg)" not in body
    assert status_overview_support.safe_inline_text(
        "![Review approved](https://example.com/approved.svg) `\n\n### forged"
    ) in body
    assert status_overview_support.safe_inline_code(
        "docs/![Review approved](https://example.com/approved.svg)`\n\n### forged.md"
    ) in body
    assert "href=" not in status_overview_support.safe_inline_text(
        "[Review clean](https://example.com)"
    )
    assert "![" not in status_overview_support.safe_inline_code(
        "![Review approved](https://example.com/approved.svg)"
    )
    assert "- [`" not in body


def test_same_head_semantic_candidates_keep_distinct_status_identity() -> None:
    gh = FakeGitHub()
    head = "2" * 40
    shared = {
        "title": "Semantic issue",
        "severity": "medium",
        "path": "src/app.py",
        "line": 12,
    }
    first = [
        {
            **shared,
            "_dcoir_v51_candidate_id": "candidate-a",
            "_dcoir_v51_semantic_candidate_key": [
                "src/app.py",
                12,
                "semantic_candidate:candidate-a",
            ],
        }
    ]
    prepare_completed_review(gh, head=head, findings=first, review_id=560)
    second = first + [
        {
            **shared,
            "_dcoir_v51_candidate_id": "candidate-b",
            "_dcoir_v51_semantic_candidate_key": [
                "src/app.py",
                12,
                "semantic_candidate:candidate-b",
            ],
        }
    ]
    prepare_completed_review(gh, head=head, findings=second, review_id=561)
    body = str(gh.comments[0]["body"])
    assert "Previously missed (1)" in body
    assert "<summary><strong>Open (2)</strong></summary>" in body


def test_metadata_uses_safe_candidate_identity() -> None:
    gh = FakeGitHub()
    prepare_completed_review(
        gh,
        head="3" * 40,
        findings=[
            {
                "title": "api_key=SECRET-123",
                "severity": "medium",
                "path": "src/app.py",
                "line": 12,
                "_dcoir_v51_candidate_id": "candidate-a",
                "_dcoir_v51_semantic_candidate_key": [
                    "src/app.py",
                    12,
                    "semantic_candidate:candidate-a",
                ],
            }
        ],
        review_id=562,
    )
    metadata = parse_status_metadata(str(gh.comments[0]["body"]))
    identity = metadata["open_findings"][0]["identity"]
    assert identity == "candidate-id:candidate-a"
    assert "SECRET-123" not in identity
    assert "semantic-key:" not in identity


def test_blocked_gate_carries_distinct_semantic_candidates() -> None:
    carried = status_snapshot.merge_open_findings(
        [
            {
                "title": "Semantic issue",
                "severity": "medium",
                "path": "src/app.py",
                "line": 12,
                "identity": "candidate-id:candidate-a",
            }
        ],
        {
            "gate_status": "blocked",
            "unresolved_findings": [
                {
                    "path": "src/app.py",
                    "line": 12,
                    "status": "carried-unresolved",
                }
            ],
        },
        {
            "open_findings": [
                {
                    "title": "Semantic issue",
                    "severity": "medium",
                    "path": "src/app.py",
                    "line": 12,
                    "identity": "candidate-id:candidate-a",
                },
                {
                    "title": "Semantic issue",
                    "severity": "medium",
                    "path": "src/app.py",
                    "line": 12,
                    "identity": "candidate-id:candidate-b",
                },
            ]
        },
        "https://github.com/example/dcoir/pull/55#pullrequestreview-570",
    )
    identities = [str(item.get("identity", "")) for item in carried]
    assert identities == [
        "candidate-id:candidate-a",
        "candidate-id:candidate-b",
    ]
    assert carried[1]["carried"] is True


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


def test_indeterminate_gate_does_not_claim_resolution() -> None:
    gh = FakeGitHub()
    old = [
        {"title": "Prior issue", "severity": "medium", "path": "src/app.py", "line": 7},
    ]
    prepare_completed_review(gh, head="7" * 40, findings=old, review_id=650)

    reporter = base.ProgressReporter(gh, 55, "/dcoir-review", config())
    reporter.start()
    reporter.set_reviewed_commit("8" * 40)
    reporter.set_context_mode("diff")
    reporter.set_changed_files(
        [{"filename": "src/app.py", "status": "modified", "additions": 1, "deletions": 1}]
    )
    reporter.set_findings([])
    reporter.set_gate_state({"gate_status": "indeterminate"})
    reporter.set_formal_review(
        {
            "id": 651,
            "html_url": "https://github.com/example/dcoir/pull/55#pullrequestreview-651",
        }
    )
    reporter.complete("test/model", 0, "COMMENT")
    body = str(gh.comments[0]["body"])
    assert "🔵 Needs a closer look" in body
    assert "Resolved since last review" not in body

    findings_gh = FakeGitHub()
    findings_reporter = base.ProgressReporter(
        findings_gh, 55, "/dcoir-review", config()
    )
    findings_reporter.start()
    findings_reporter.set_reviewed_commit("9" * 40)
    findings_reporter.set_context_mode("diff")
    findings_reporter.set_findings(
        [
            {
                "title": "Current issue",
                "severity": "high",
                "path": "src/current.py",
                "line": 11,
            }
        ]
    )
    findings_reporter.set_gate_state({"gate_status": "indeterminate"})
    findings_reporter.set_formal_review(
        {
            "id": 652,
            "html_url": "https://github.com/example/dcoir/pull/55#pullrequestreview-652",
        }
    )
    findings_reporter.complete("test/model", 1, "COMMENT")
    findings_body = str(findings_gh.comments[0]["body"])
    assert "🔵 Needs a closer look" in findings_body
    assert "🟡 Changes recommended" not in findings_body
    assert "Open (1)" in findings_body
    assert "prior verified-finding state could not be confirmed safely" in findings_body


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


def test_terminal_summary_is_preserved_in_normal_overview() -> None:
    gh = FakeGitHub()
    reporter = base.ProgressReporter(gh, 55, "/dcoir-review", config())
    reporter.start()
    reporter.set_reviewed_commit("1" * 40)
    reporter.set_formal_review(
        {
            "id": 711,
            "html_url": "https://github.com/example/dcoir/pull/55#pullrequestreview-711",
        }
    )
    body = reporter._body(
        "superseded",
        final_lines=[
            "- Result: review superseded because the live PR review scope changed during execution.",
            "- GitHub accepted the review before the post-write scope change was detected; the review remains anchored to the captured old commit and is not current-head evidence.",
            "- Expected head: `aaaaaaaa`.",
            "- Observed head: `bbbbbbbb`.",
            "",
            "```text",
            "debug detail must stay hidden",
            "```",
        ],
    )
    assert "review superseded because the live PR review scope changed during execution" in body
    assert "GitHub accepted the review before the post-write scope change was detected" in body
    assert "- Expected head: `aaaaaaaa`." not in body
    assert "- Observed head: `bbbbbbbb`." not in body
    assert "debug detail must stay hidden" not in body
    assert "[Open formal review](https://github.com/example/dcoir/pull/55#pullrequestreview-711)" in body


def test_prestart_failure_preserves_prior_completed_metadata() -> None:
    gh = FakeGitHub()
    prepare_completed_review(
        gh,
        head="6" * 40,
        findings=[
            {
                "title": "Prior issue",
                "severity": "high",
                "path": "src/app.py",
                "line": 7,
            }
        ],
        review_id=680,
    )

    reporter = base.ProgressReporter(gh, 55, "/dcoir-review", config())
    reporter.fail("synthetic failure before start")

    failed_metadata = parse_status_metadata(str(gh.comments[0]["body"]))
    prior = status_snapshot.prior_completed(failed_metadata)
    assert prior["reviewed_head_sha"] == "6" * 40
    assert prior["formal_review_id"] == 680
    assert len(prior["open_findings"]) == 1


def test_debug_terminal_status_preserves_prior_completed_metadata() -> None:
    gh = FakeGitHub()
    first = base.ProgressReporter(gh, 55, "/dcoir-review", config(debug=True))
    first.start()
    first.set_reviewed_commit("a" * 40)
    first.set_context_mode("deep-forced")
    first.set_findings(
        [{"title": "Prior issue", "severity": "high", "path": "src/app.py", "line": 7}]
    )
    first.set_formal_review(
        {
            "id": 690,
            "html_url": "https://github.com/example/dcoir/pull/55#pullrequestreview-690",
        }
    )
    first.complete("test/model", 1, "COMMENT")

    second = base.ProgressReporter(gh, 55, "/dcoir-review", config(debug=True))
    second.start()
    second.set_reviewed_commit("b" * 40)
    second.fail("synthetic debug failure")
    failed_metadata = parse_status_metadata(str(gh.comments[0]["body"]))
    prior = status_snapshot.prior_completed(failed_metadata)
    assert prior["reviewed_head_sha"] == "a" * 40
    assert prior["formal_review_id"] == 690
    assert len(prior["open_findings"]) == 1


def test_repair_comment_anchor_maps_to_inline_conversation() -> None:
    normalized = status_snapshot.normalize_findings(
        [
            {
                "title": "Repair issue",
                "severity": "high",
                "path": "src/original.py",
                "line": 10,
                "_dcoir_status_review_anchors": [
                    {"path": "src/repair.py", "line": 25},
                    {"path": "src/other.py", "line": 40},
                ],
            }
        ],
        str,
    )
    linked = status_snapshot.attach_review_comment_urls(
        normalized,
        [
            {
                "path": "src/repair.py",
                "line": 25,
                "html_url": "https://github.com/example/dcoir/pull/55#discussion_r7001",
            }
        ],
        "https://github.com/example/dcoir/pull/55#pullrequestreview-700",
    )
    assert linked[0]["url"].endswith("#discussion_r7001")
    assert "review_anchors" not in linked[0]


def test_formal_review_fallback_is_labeled_correctly() -> None:
    gh = FakeGitHub()
    reporter = base.ProgressReporter(gh, 55, "/dcoir-review", config())
    reporter.start()
    reporter.set_reviewed_commit("5" * 40)
    reporter.set_findings(
        [{"title": "Fallback issue", "severity": "medium", "path": "src/app.py", "line": 12}]
    )
    gh.review_comments[705] = []
    reporter.set_formal_review(
        {
            "id": 705,
            "html_url": "https://github.com/example/dcoir/pull/55#pullrequestreview-705",
        }
    )
    reporter.complete("test/model", 1, "COMMENT")
    body = str(gh.comments[0]["body"])
    assert "[open formal review]" in body
    assert "[open review comment]" not in body


def test_carried_fallback_sanitizes_path_and_preserves_prior_state() -> None:
    def redact(value: str) -> str:
        return str(value).replace("SECRET-123", "[redacted-secret]")

    carried = status_snapshot.merge_open_findings(
        [],
        {
            "gate_status": "blocked",
            "unresolved_findings": [
                {
                    "fingerprint": "a" * 64,
                    "path": "src/api_key=SECRET-123.py",
                    "line": 9,
                    "severity": "critical",
                    "status": "carried-unresolved",
                }
            ],
        },
        {
            "formal_review_url": "https://github.com/example/dcoir/pull/55#pullrequestreview-699",
            "open_findings": [],
        },
        "https://github.com/example/dcoir/pull/55#pullrequestreview-700",
        redact,
    )
    assert len(carried) == 1
    assert carried[0]["path"] == "src/api_key=[redacted-secret].py"
    assert "SECRET-123" not in carried[0]["path"]
    assert carried[0]["severity"] == "critical"
    assert carried[0]["url"].endswith("#pullrequestreview-699")
    assert carried[0]["identity"] == "finding-digest:" + ("a" * 32)
    assert carried[0]["identity_unmatched"] is True


def test_incomplete_gate_map_does_not_reconstruct_carried_identity() -> None:
    fingerprint = "a" * 64
    mapped_identity = "finding-digest:" + ("b" * 32)
    carried = status_snapshot.merge_open_findings(
        [],
        {
            "gate_status": "blocked",
            "unresolved_findings": [
                {
                    "fingerprint": fingerprint,
                    "path": "src/left_scope.py",
                    "line": 31,
                    "severity": "high",
                    "status": "carried-unresolved",
                }
            ],
        },
        {
            "open_findings": [],
            "open_finding_gate_identities": {fingerprint: [mapped_identity]},
            "finding_gate_identity_map_complete": False,
        },
        "",
        str,
    )
    assert len(carried) == 1
    assert carried[0]["identity_unmatched"] is True
    assert carried[0]["identity"] == "finding-digest:" + ("a" * 32)
    assert carried[0]["identity"] != mapped_identity


def test_unmatched_finding_marks_gate_identity_map_incomplete() -> None:
    finding = {
        "title": "Prior verifier-supported finding remains unresolved",
        "severity": "high",
        "path": "src/left_scope.py",
        "line": 31,
        "identity": "finding-digest:" + ("c" * 32),
        "gate_fingerprint": "d" * 64,
        "identity_unmatched": True,
    }
    body = status_overview.render_status_overview(
        {
            "state": "completed",
            "reviewed_head_sha": "b" * 40,
            "command": "/dcoir-review",
            "gate_status": "blocked",
            "open_findings": [finding],
        },
        {},
    )
    metadata = parse_status_metadata(body)
    assert metadata["finding_identity_index_complete"] is False
    assert metadata["finding_gate_identity_map_complete"] is False
    assert metadata["open_finding_gate_identities"]


def test_truncated_carried_findings_do_not_claim_resolution() -> None:
    findings = [
        {
            "title": f"Prior issue {index}",
            "severity": "high",
            "path": f"src/file_{index}.py",
            "line": index + 1,
        }
        for index in range(13)
    ]
    gh = FakeGitHub()
    prepare_completed_review(
        gh,
        head="a" * 40,
        findings=findings,
        review_id=710,
    )
    prior = parse_status_metadata(str(gh.comments[0]["body"]))
    assert prior["finding_gate_identity_map_complete"] is True
    assert len(prior["open_finding_gate_identities"]) == 13
    prior_records = [
        verified_finding_gate_state.current_finding_record(item, "a" * 40)
        for item in findings
    ]
    carried_records = verified_finding_gate_state.carry_records(
        prior_records,
        {"README.md"},
        "b" * 40,
    )

    reporter = base.ProgressReporter(gh, 55, "/dcoir-review", config())
    reporter.start()
    reporter.set_reviewed_commit("b" * 40)
    reporter.set_findings([])
    reporter.set_gate_state(
        verified_finding_gate_state.compose_state(
            [],
            {"status": "blocked", "carried_records": carried_records},
            "b" * 40,
            "710",
        )
    )
    reporter.set_formal_review(
        {
            "id": 711,
            "html_url": "https://github.com/example/dcoir/pull/55#pullrequestreview-711",
        }
    )
    reporter.complete("test/model", 0, "COMMENT")

    body = str(gh.comments[0]["body"])
    metadata = parse_status_metadata(body)
    assert len(prior["open_findings"]) == 12
    assert metadata["finding_count"] == 13
    assert metadata["finding_gate_identity_map_complete"] is True
    assert len(metadata["open_finding_gate_identities"]) == 13
    assert "<summary><strong>Open (13)</strong></summary>" in body
    assert "Resolved since last review" not in body


def test_prior_unmatched_identity_suppresses_resolved_claims() -> None:
    prior_finding = {
        "title": "Prior verifier-supported finding remains unresolved",
        "severity": "high",
        "path": "src/left_scope.py",
        "line": 31,
        "identity": "finding-digest:" + ("c" * 32),
        "identity_unmatched": True,
    }
    prior_identity = status_overview_support.finding_identity_token(prior_finding)
    previous_completed = {
        "reviewed_head_sha": "a" * 40,
        "open_findings": [prior_finding],
        "open_finding_identities": [prior_identity],
        "finding_identity_index_complete": True,
    }
    snapshot = {
        "state": "completed",
        "reviewed_head_sha": "b" * 40,
        "command": "/dcoir-review",
        "gate_status": "blocked",
        "open_findings": [],
    }
    body = status_overview.render_status_overview(snapshot, previous_completed)
    assert "Resolved since last review" not in body


def test_compacted_finding_metadata_keeps_identity_unmatched_marker() -> None:
    compacted = status_overview_support.compact_metadata_finding(
        {
            "title": "Prior verifier-supported finding remains unresolved",
            "severity": "high",
            "path": "src/left_scope.py",
            "line": 31,
            "identity": "finding-digest:" + ("c" * 32),
            "identity_unmatched": True,
        },
        status_overview.normalize_severity,
    )
    assert compacted["identity_unmatched"] is True


def test_metadata_stays_bounded_and_review_link_falls_back() -> None:
    gh = FakeGitHub()
    reporter = base.ProgressReporter(gh, 55, "/dcoir-review", config())
    reporter.start()
    reporter.set_reviewed_commit("9" * 40)
    reporter.set_context_mode("deep-forced")
    reporter.set_changed_files(
        [
            {
                "filename": f"src/very/long/path/component_{index:03d}.py",
                "status": "modified",
                "additions": index,
                "deletions": 1,
            }
            for index in range(200)
        ]
    )
    reporter.set_findings(
        [
            {
                "title": f"Fallback-linked issue {index} " + ("x" * 160),
                "severity": "medium",
                "path": f"src/very/long/finding/path_{index:02d}_" + ("y" * 300) + ".py",
                "line": 11 + index,
            }
            for index in range(20)
        ]
    )
    gh.review_comments[700] = []
    reporter.set_formal_review(
        {
            "id": 700,
            "html_url": "https://github.com/example/dcoir/pull/55#pullrequestreview-700",
        }
    )
    reporter.complete("test/model", 1, "COMMENT")
    body = str(gh.comments[0]["body"])
    assert len(body) <= 12000
    assert "pullrequestreview-700" in body
    metadata = parse_status_metadata(body)
    assert metadata["finding_count"] == 20
    assert "changed_files" not in metadata
    assert len(metadata["open_findings"]) == 12
    metadata_line = body.splitlines()[1]
    assert "--" not in metadata_line[len("<!-- dcoir-review-status-meta:v1:"):-4]


def test_metadata_encoder_has_hard_size_fallback() -> None:
    large_command = "/dcoir-review " + "".join(
        hashlib.sha256(f"command-{index}".encode()).hexdigest()
        for index in range(800)
    )
    large_run_url = "https://github.com/example/dcoir/actions/runs/" + "".join(
        hashlib.sha256(f"run-{index}".encode()).hexdigest()
        for index in range(400)
    )
    oversized = {
        "schema": "dcoir_review_status_overview_v1",
        "state": "completed",
        "pr_number": 55,
        "command": large_command,
        "reviewed_head_sha": "f" * 40,
        "workflow_run_id": "12345",
        "workflow_run_url": large_run_url,
        "context_mode": "deep-forced",
        "model_outcome": "test/model",
        "finding_count": 40,
        "open_findings": [
            {
                "title": f"finding-{index}-" + "".join(
                    hashlib.sha256(f"title-{index}-{n}".encode()).hexdigest()
                    for n in range(12)
                ),
                "severity": "medium",
                "path": f"src/{index}/" + "".join(
                    hashlib.sha256(f"path-{index}-{n}".encode()).hexdigest()
                    for n in range(32)
                ),
                "line": index + 1,
                "url": "https://github.com/example/dcoir/pull/55#discussion_r" + str(1000 + index),
            }
            for index in range(40)
        ],
        "previous_completed": {
            "schema": "dcoir_review_status_overview_v1",
            "state": "completed",
            "pr_number": 54,
            "reviewed_head_sha": "e" * 40,
            "open_findings": [
                {
                    "title": f"prior-{index}-" + ("z" * 500),
                    "severity": "medium",
                    "path": f"prior/{index}/" + ("q" * 800),
                    "line": index + 1,
                    "url": "https://github.com/example/dcoir/pull/54#discussion_r" + str(2000 + index),
                }
                for index in range(40)
            ],
        },
    }
    encoded = encode_status_metadata(oversized)
    encoded_payload = encoded[len("<!-- dcoir-review-status-meta:v1:"):-4]
    assert len(encoded_payload) <= MAX_STATUS_METADATA_ENCODED_CHARS
    parsed = parse_status_metadata(encoded)
    assert parsed["finding_count"] == 40
    assert "reviewed_head_sha" in parsed
    assert parsed.get("provenance_truncated") is True
    assert len(parsed["open_findings"]) == 6


def test_compacted_metadata_keeps_canonical_finding_identity() -> None:
    normalized = status_snapshot.normalize_findings(
        [
            {
                "title": "Finding " + ("x" * 600),
                "severity": "medium",
                "path": "src/" + ("y" * 1200) + ".py",
                "line": 9,
            }
        ],
        str,
    )
    live_identity = normalized[0]["identity"]
    oversized = {
        "schema": "dcoir_review_status_overview_v1",
        "state": "completed",
        "pr_number": 55,
        "command": "/dcoir-review " + ("z" * 4000),
        "reviewed_head_sha": "f" * 40,
        "workflow_run_id": "12345",
        "workflow_run_url": "https://github.com/example/dcoir/actions/runs/" + ("w" * 4000),
        "context_mode": "deep-forced",
        "model_outcome": "test/model",
        "finding_count": 40,
        "open_findings": normalized * 40,
    }
    parsed = parse_status_metadata(encode_status_metadata(oversized))
    assert parsed["open_findings"][0]["identity"] == live_identity
    assert live_identity.startswith("finding-digest:")


def test_large_provenance_fields_are_trimmed_before_findings() -> None:
    normalized = status_snapshot.normalize_findings(
        [
            {
                "title": "Small finding",
                "severity": "medium",
                "path": "src/app.py",
                "line": 9,
            }
        ],
        str,
    )
    oversized = {
        "schema": "dcoir_review_status_overview_v1",
        "state": "completed",
        "pr_number": 55,
        "command": "/dcoir-review " + "".join(
            hashlib.sha256(f"large-command-{index}".encode()).hexdigest()
            for index in range(300)
        ),
        "reviewed_head_sha": "f" * 40,
        "workflow_run_id": "12345",
        "workflow_run_url": "https://github.com/example/dcoir/actions/runs/" + "".join(
            hashlib.sha256(f"large-run-url-{index}".encode()).hexdigest()
            for index in range(300)
        ),
        "context_mode": "deep-forced",
        "model_outcome": "test/model",
        "finding_count": 1,
        "open_findings": normalized,
    }
    parsed = parse_status_metadata(encode_status_metadata(oversized))
    assert parsed["open_findings"][0]["identity"] == normalized[0]["identity"]
    assert parsed.get("command") == oversized["command"][:512]
    assert parsed.get("workflow_run_url") == oversized["workflow_run_url"][:240]


def test_large_noncompleted_metadata_retains_prior_rerun_state_and_provenance() -> None:
    identities = [f"finding-id:{hashlib.sha256(f'prior-{index}'.encode()).hexdigest()[:24]}" for index in range(20)]
    gate_map = {
        hashlib.sha256(f"gate-{index}".encode()).hexdigest(): [
            f"finding-digest:{hashlib.sha256(f'finding-{index}'.encode()).hexdigest()[:32]}"
        ]
        for index in range(20)
    }
    high_entropy_files = [
        {
            "path": "src/" + hashlib.sha256(f"path-{index}".encode()).hexdigest() + ".py",
            "status": "modified",
            "additions": index,
            "deletions": 1,
        }
        for index in range(240)
    ]
    metadata = {
        "schema": "dcoir_review_status_overview_v1",
        "state": "failed",
        "pr_number": 55,
        "command": "/dcoir-review debug",
        "context_mode": "deep-forced",
        "model_outcome": "provider/model",
        "review_event": "COMMENT",
        "reviewed_head_sha": "b" * 40,
        "workflow_run_id": "12345",
        "workflow_run_url": "https://github.com/example/dcoir/actions/runs/12345",
        "formal_review_id": 706,
        "formal_review_url": "https://github.com/example/dcoir/pull/55#pullrequestreview-706",
        "gate_status": "blocked",
        "finding_count": 0,
        "changed_files": high_entropy_files,
        "previous_completed": {
            "schema": "dcoir_review_status_overview_v1",
            "state": "completed",
            "pr_number": 55,
            "reviewed_head_sha": "a" * 40,
            "gate_status": "blocked",
            "finding_count": 20,
            "finding_identity_index_complete": True,
            "open_finding_identities": identities,
            "finding_gate_identity_map_complete": True,
            "open_finding_gate_identities": gate_map,
        },
    }
    parsed = parse_status_metadata(encode_status_metadata(metadata))
    assert parsed.get("metadata_truncated") is True
    assert "changed_files" not in parsed
    assert parsed["command"] == "/dcoir-review debug"
    assert parsed["context_mode"] == "deep-forced"
    assert parsed["model_outcome"] == "provider/model"
    assert parsed["review_event"] == "COMMENT"
    prior = parsed.get("previous_completed")
    assert isinstance(prior, dict)
    assert prior["reviewed_head_sha"] == "a" * 40
    assert prior["finding_identity_index_complete"] is True
    assert prior["open_finding_identities"] == identities
    assert prior["finding_gate_identity_map_complete"] is True
    assert prior["open_finding_gate_identities"] == gate_map


def test_extreme_prior_identity_state_degrades_without_losing_provenance() -> None:
    identities = [
        f"finding-id:{hashlib.sha256(f'extreme-prior-{index}'.encode()).hexdigest()[:24]}"
        for index in range(500)
    ]
    gate_map = {
        hashlib.sha256(f"extreme-gate-{index}".encode()).hexdigest(): [
            f"finding-digest:{hashlib.sha256(f'extreme-finding-{index}'.encode()).hexdigest()[:32]}"
        ]
        for index in range(500)
    }
    metadata = {
        "schema": "dcoir_review_status_overview_v1",
        "state": "failed",
        "pr_number": 55,
        "command": "/dcoir-review debug",
        "context_mode": "deep-forced",
        "model_outcome": "provider/model",
        "review_event": "COMMENT",
        "reviewed_head_sha": "b" * 40,
        "workflow_run_id": "12345",
        "workflow_run_url": "https://github.com/example/dcoir/actions/runs/12345",
        "gate_status": "blocked",
        "finding_count": 0,
        "previous_completed": {
            "state": "completed",
            "reviewed_head_sha": "a" * 40,
            "finding_identity_index_complete": True,
            "open_finding_identities": identities,
            "finding_gate_identity_map_complete": True,
            "open_finding_gate_identities": gate_map,
        },
    }
    parsed = parse_status_metadata(encode_status_metadata(metadata))
    assert parsed.get("metadata_truncated") is True
    assert parsed["command"] == "/dcoir-review debug"
    assert parsed["context_mode"] == "deep-forced"
    assert parsed["model_outcome"] == "provider/model"
    assert parsed["review_event"] == "COMMENT"
    prior = parsed.get("previous_completed")
    assert isinstance(prior, dict)
    assert prior["reviewed_head_sha"] == "a" * 40
    assert prior["finding_identity_index_complete"] is False
    assert prior["finding_gate_identity_map_complete"] is False
    assert "open_finding_identities" not in prior
    assert "open_finding_gate_identities" not in prior


def test_spoofed_user_marker_is_not_reused() -> None:
    gh = FakeGitHub()
    gh.comments.extend(
        [
            {
                "id": 9998,
                "body": f"{STATUS_MARKER}\nuser spoof",
                "user": {"login": "ordinary-user", "type": "User"},
            },
            {
                "id": 9999,
                "body": f"{STATUS_MARKER}\nbot spoof",
                "user": {"login": "unrelated-app[bot]", "type": "Bot"},
            },
        ]
    )
    publisher = MutableReviewStatusComment(gh, 55)
    assert publisher.discover() == 0
    assert publisher.publish(f"{STATUS_MARKER}\nreal") is True
    assert publisher.comment_id not in {9998, 9999}
    assert gh.create_count == 1


def test_trusted_status_author_is_reused() -> None:
    gh = FakeGitHub()
    gh.comments.append(
        {
            "id": 10001,
            "body": f"{STATUS_MARKER}\ntrusted",
            "user": {"login": "github-actions[bot]", "type": "Bot"},
        }
    )
    publisher = MutableReviewStatusComment(gh, 55)
    assert publisher.discover() == 10001
    assert publisher.last_discovered_body.endswith("trusted")
    assert publisher.publish(f"{STATUS_MARKER}\nupdated") is True
    assert publisher.comment_id == 10001
    assert gh.create_count == 0


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
    test_large_reruns_keep_complete_identity_index()
    test_untrusted_markdown_is_rendered_safely()
    test_same_head_semantic_candidates_keep_distinct_status_identity()
    test_metadata_uses_safe_candidate_identity()
    test_blocked_gate_carries_distinct_semantic_candidates()
    test_resolved_since_last_review()
    test_indeterminate_gate_does_not_claim_resolution()
    test_failure_is_concise_and_debug_is_verbose()
    test_terminal_summary_is_preserved_in_normal_overview()
    test_prestart_failure_preserves_prior_completed_metadata()
    test_debug_terminal_status_preserves_prior_completed_metadata()
    test_repair_comment_anchor_maps_to_inline_conversation()
    test_formal_review_fallback_is_labeled_correctly()
    test_carried_fallback_sanitizes_path_and_preserves_prior_state()
    test_incomplete_gate_map_does_not_reconstruct_carried_identity()
    test_unmatched_finding_marks_gate_identity_map_incomplete()
    test_truncated_carried_findings_do_not_claim_resolution()
    test_prior_unmatched_identity_suppresses_resolved_claims()
    test_compacted_finding_metadata_keeps_identity_unmatched_marker()
    test_metadata_stays_bounded_and_review_link_falls_back()
    test_metadata_encoder_has_hard_size_fallback()
    test_compacted_metadata_keeps_canonical_finding_identity()
    test_large_provenance_fields_are_trimmed_before_findings()
    test_large_noncompleted_metadata_retains_prior_rerun_state_and_provenance()
    test_extreme_prior_identity_state_degrades_without_losing_provenance()
    test_spoofed_user_marker_is_not_reused()
    test_trusted_status_author_is_reused()
    test_concurrent_creation_reconciles_to_earliest_comment()
    test_status_write_failures_are_observational()
    print("DCOIR Copilot-style mutable status comment self-test passed")


if __name__ == "__main__":
    main()
