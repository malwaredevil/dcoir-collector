#!/usr/bin/env python3
"""Deterministic regression checks for DCOIR Review v48 supersession handling."""

from __future__ import annotations

import importlib
import os
from types import SimpleNamespace

from dcoir_review.entrypoint import DcoirReviewEntrypoint


REPO = "malwaredevil/dcoir-collector"
PR_NUMBER = 457
HEAD = "a" * 40
BASE = "b" * 40
NEW_HEAD = "c" * 40
NEW_BASE = "d" * 40


class FakeClient:
    def __init__(self, token: str = "token", repo: str = REPO) -> None:
        self.token = token
        self.repo = repo
        self.head = HEAD
        self.base = BASE
        self.state = "open"
        self.fail_reads = False
        self.get_pr_calls = 0
        self.review_posts = 0

    def get_pr(self, number: int):
        self.get_pr_calls += 1
        if self.fail_reads:
            raise RuntimeError("synthetic GitHub read failure")
        assert number == PR_NUMBER
        return {
            "number": number,
            "state": self.state,
            "head": {"sha": self.head},
            "base": {"sha": self.base},
        }

    def create_review(self, number, body, event, comments, commit_id):
        assert number == PR_NUMBER
        self.review_posts += 1
        return {"id": self.review_posts, "commit_id": commit_id}


class FakeCommentGitHub:
    def __init__(self) -> None:
        self.comments: dict[int, str] = {}
        self.next_id = 1

    def create_issue_comment(self, number: int, body: str):
        assert number == PR_NUMBER
        comment_id = self.next_id
        self.next_id += 1
        self.comments[comment_id] = body
        return {"id": comment_id}

    def update_issue_comment(self, comment_id: int, body: str):
        self.comments[comment_id] = body
        return {"id": comment_id}


class FakeReporter:
    def __init__(self, gh, issue_number, command, config) -> None:
        self.gh = gh
        self.issue_number = issue_number
        self.command = command
        self.config = config
        self.comment_id = 0
        self.steps: list[tuple[str, str]] = []
        self.generic_failures = 0

    def _record(self, stage: str, message: str) -> None:
        self.steps.append((stage, message))

    def _body(self, state: str, final_lines=None) -> str:
        lines = [f"DCOIR Review {state}."]
        if final_lines:
            lines.extend(final_lines)
        return "\n".join(lines)

    def fail(self, message: str) -> None:
        self.generic_failures += 1
        self._record("failed", message)


class FakeHardened:
    ProgressReporter = FakeReporter

    def __init__(self) -> None:
        self.paid_calls = 0
        self.on_request = None
        self.artifacts: dict[str, object] = {}

    def openrouter_request_once(self, prompt, schema, config, ignored_providers, model):
        self.paid_calls += 1
        if callable(self.on_request):
            self.on_request()
        return {"summary": "clean", "findings": []}, model, ""

    def write_debug_json_artifact_safely(self, _config, path, value) -> None:
        self.artifacts[path] = value

    def sanitize_github_output(self, text: str, _config) -> str:
        return str(text)


class FakeModule(SimpleNamespace):
    pass


def build_fake_module(v48):
    state = {"main_exception": None}
    hardened = FakeHardened()

    def hybrid(*_args, **_kwargs):
        raise RuntimeError("synthetic per-file coverage failure")

    def original_main():
        exc = state["main_exception"]
        if exc is not None:
            raise exc

    module = FakeModule(
        base=SimpleNamespace(GitHubClient=FakeClient),
        hardened=hardened,
        openrouter_review_with_hybrid_first_pass=hybrid,
        main=original_main,
    )
    v48.apply_pareto_context_module(module)
    return module, hardened, state


def expect_raises(error_type, callback):
    try:
        callback()
    except error_type as exc:
        return exc
    raise AssertionError(f"expected {error_type.__name__}")


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.post_terminal_patch_module_names == (
        "dcoir_review_required_runtime_patch_v44",
        "dcoir_review_required_runtime_patch_v45",
        "dcoir_review_required_runtime_patch_v46",
    )
    assert entrypoint.stage_local_patch_module_names == (
        "dcoir_review_required_runtime_patch_v47",
    )
    assert entrypoint.execution_policy_patch_module_names == (
        "dcoir_review_required_runtime_patch_v48",
    )

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v48 = importlib.import_module("dcoir_review_required_runtime_patch_v48")
    assert getattr(review, v48.APPLIED_MARKER, False) is True

    module, hardened, main_state = build_fake_module(v48)
    assert getattr(module, v48.APPLIED_MARKER, False) is True
    config = SimpleNamespace(debug=True)

    previous_repo = os.environ.get("GITHUB_REPOSITORY")
    previous_pr = os.environ.get("PR_NUMBER")
    os.environ["GITHUB_REPOSITORY"] = REPO
    os.environ["PR_NUMBER"] = str(PR_NUMBER)
    try:
        # The first production PR metadata read captures the immutable run scope.
        client = FakeClient()
        v48.clear_guard_context(module)
        first = client.get_pr(PR_NUMBER)
        context = getattr(module, v48.GUARD_ATTR)
        assert first["head"]["sha"] == HEAD
        assert context["expected_head_sha"] == HEAD
        assert context["expected_base_sha"] == BASE
        assert context["pr_number"] == PR_NUMBER

        # With no production guard installed, direct probes retain historical behavior.
        v48.clear_guard_context(module)
        before = hardened.paid_calls
        result, model, _tier = hardened.openrouter_request_once(
            "probe", {}, config, [], "anthropic/claude-sonnet-5"
        )
        assert result["findings"] == []
        assert model == "anthropic/claude-sonnet-5"
        assert hardened.paid_calls == before + 1

        # An unchanged exact scope permits the request and verifies both before and after.
        client = FakeClient()
        v48.install_guard_context(module, client, PR_NUMBER, HEAD, BASE)
        before = hardened.paid_calls
        hardened.openrouter_request_once("probe", {}, config, [], "anthropic/claude-sonnet-5")
        context = getattr(module, v48.GUARD_ATTR)
        assert hardened.paid_calls == before + 1
        assert context["check_count"] == 2
        assert context["terminal"] is None

        # If the head already moved, no provider request may start.
        client = FakeClient()
        client.head = NEW_HEAD
        v48.install_guard_context(module, client, PR_NUMBER, HEAD, BASE)
        before = hardened.paid_calls
        moved = expect_raises(
            v48.ReviewSupersededError,
            lambda: hardened.openrouter_request_once(
                "probe", {}, config, [], "anthropic/claude-sonnet-5"
            ),
        )
        assert v48.SUPERSEDED_PREFIX in str(moved)
        assert hardened.paid_calls == before
        artifact = hardened.artifacts[v48.ARTIFACT_PATH]
        assert artifact["result"] == "superseded"
        assert artifact["expected_head_sha"] == HEAD
        assert artifact["observed_head_sha"] == NEW_HEAD

        # A head move while a request is already in flight discards that result.
        client = FakeClient()
        v48.install_guard_context(module, client, PR_NUMBER, HEAD, BASE)
        hardened.on_request = lambda: setattr(client, "head", NEW_HEAD)
        before = hardened.paid_calls
        during = expect_raises(
            v48.ReviewSupersededError,
            lambda: hardened.openrouter_request_once(
                "probe", {}, config, [], "anthropic/claude-sonnet-5"
            ),
        )
        hardened.on_request = None
        assert v48.SUPERSEDED_PREFIX in str(during)
        assert hardened.paid_calls == before + 1
        assert getattr(module, v48.GUARD_ATTR)["terminal"]["kind"] == "superseded"

        # Once superseded, queued/later requests fail immediately without another provider call.
        before = hardened.paid_calls
        expect_raises(
            v48.ReviewSupersededError,
            lambda: hardened.openrouter_request_once(
                "probe-2", {}, config, [], "anthropic/claude-sonnet-5"
            ),
        )
        assert hardened.paid_calls == before

        # Base movement changes the effective PR diff even when the head is unchanged.
        client = FakeClient()
        client.base = NEW_BASE
        v48.install_guard_context(module, client, PR_NUMBER, HEAD, BASE)
        before = hardened.paid_calls
        base_move = expect_raises(
            v48.ReviewSupersededError,
            lambda: hardened.openrouter_request_once("probe", {}, config, [], "model"),
        )
        assert "PR base moved" in str(base_move)
        assert hardened.paid_calls == before

        # A closed PR is terminal and must not continue model work.
        client = FakeClient()
        client.state = "closed"
        v48.install_guard_context(module, client, PR_NUMBER, HEAD, BASE)
        before = hardened.paid_calls
        closed = expect_raises(
            v48.ReviewSupersededError,
            lambda: hardened.openrouter_request_once("probe", {}, config, [], "model"),
        )
        assert "no longer open" in str(closed)
        assert hardened.paid_calls == before

        # GitHub read failure is not guessed as stale; it fails closed distinctly.
        client = FakeClient()
        client.fail_reads = True
        v48.install_guard_context(module, client, PR_NUMBER, HEAD, BASE)
        before = hardened.paid_calls
        unreadable = expect_raises(
            v48.ReviewHeadVerificationError,
            lambda: hardened.openrouter_request_once("probe", {}, config, [], "model"),
        )
        assert v48.VERIFICATION_PREFIX in str(unreadable)
        assert hardened.paid_calls == before
        assert hardened.artifacts[v48.ARTIFACT_PATH]["result"] == "verification_failed"

        # The final GitHub review write is independently exact-head guarded.
        client = FakeClient()
        v48.install_guard_context(module, client, PR_NUMBER, HEAD, BASE)
        posted = client.create_review(PR_NUMBER, "body", "COMMENT", [], HEAD)
        assert posted["commit_id"] == HEAD
        assert client.review_posts == 1

        client = FakeClient()
        client.head = NEW_HEAD
        v48.install_guard_context(module, client, PR_NUMBER, HEAD, BASE)
        stale_publication = expect_raises(
            v48.ReviewSupersededError,
            lambda: client.create_review(PR_NUMBER, "body", "COMMENT", [], HEAD),
        )
        assert v48.SUPERSEDED_PREFIX in str(stale_publication)
        assert client.review_posts == 0

        client = FakeClient()
        v48.install_guard_context(module, client, PR_NUMBER, HEAD, BASE)
        wrong_commit = expect_raises(
            v48.ReviewHeadVerificationError,
            lambda: client.create_review(PR_NUMBER, "body", "COMMENT", [], NEW_HEAD),
        )
        assert "commit id" in str(wrong_commit)
        assert client.review_posts == 0

        # Per-file code may convert worker exceptions into a coverage error. The
        # boundary restores the stronger superseded terminal classification.
        client = FakeClient()
        client.head = NEW_HEAD
        v48.install_guard_context(module, client, PR_NUMBER, HEAD, BASE)
        expect_raises(
            v48.ReviewSupersededError,
            lambda: hardened.openrouter_request_once("probe", {}, config, [], "model"),
        )
        restored = expect_raises(
            v48.ReviewSupersededError,
            lambda: module.openrouter_review_with_hybrid_first_pass(),
        )
        assert v48.SUPERSEDED_PREFIX in str(restored)

        # Superseded status is explicit even when ordinary progress comments are disabled.
        comment_gh = FakeCommentGitHub()
        reporter = hardened.ProgressReporter(
            comment_gh,
            PR_NUMBER,
            "/dcoir-review",
            SimpleNamespace(post_progress_comment=False, debug=False),
        )
        reporter.fail(str(restored))
        assert reporter.generic_failures == 0
        assert reporter.comment_id in comment_gh.comments
        terminal_body = comment_gh.comments[reporter.comment_id]
        assert "DCOIR Review superseded." in terminal_body
        assert "Stale GitHub review publication: blocked." in terminal_body
        assert "New model requests after detection: blocked" in terminal_body
        assert HEAD in terminal_body
        assert NEW_HEAD in terminal_body

        # Supersession exits the process path cleanly; verification failure remains a failure.
        main_state["main_exception"] = v48.ReviewSupersededError(
            f"{v48.SUPERSEDED_PREFIX} synthetic main-path supersession"
        )
        assert module.main() is None
        main_state["main_exception"] = v48.ReviewHeadVerificationError(
            f"{v48.VERIFICATION_PREFIX} synthetic verification failure"
        )
        expect_raises(v48.ReviewHeadVerificationError, module.main)
    finally:
        if previous_repo is None:
            os.environ.pop("GITHUB_REPOSITORY", None)
        else:
            os.environ["GITHUB_REPOSITORY"] = previous_repo
        if previous_pr is None:
            os.environ.pop("PR_NUMBER", None)
        else:
            os.environ["PR_NUMBER"] = previous_pr

    print("DCOIR Review v48 stale-head supersession selftest passed")


if __name__ == "__main__":
    main()
