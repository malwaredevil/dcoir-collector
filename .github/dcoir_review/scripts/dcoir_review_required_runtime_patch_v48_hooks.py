"""Execution and publication hooks for DCOIR Review v48."""

from __future__ import annotations

import os
import sys
from typing import Any

import dcoir_review_required_runtime_patch_v48_core as core


def _capture_is_production_target(client: Any, number: int) -> bool:
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    pr_number = os.environ.get("PR_NUMBER", "").strip()
    if not repo or not pr_number:
        return False
    try:
        expected_number = int(pr_number)
    except ValueError:
        return False
    return str(getattr(client, "repo", "") or "") == repo and int(number) == expected_number


def _patch_get_pr(module: Any) -> None:
    client_cls = module.base.GitHubClient
    storage = "_dcoir_review_v48_original_get_pr"
    original = getattr(client_cls, storage, None)
    if original is None:
        original = getattr(client_cls, "get_pr", None)
        if callable(original):
            setattr(client_cls, storage, original)
    if not callable(original):
        raise RuntimeError("DCOIR v48 could not locate GitHubClient.get_pr")

    def get_pr(self, number: int):
        pr = original(self, number)
        if core._guard(module) is None and _capture_is_production_target(self, number):
            head_data = pr.get("head") if isinstance(pr, dict) and isinstance(pr.get("head"), dict) else {}
            base_data = pr.get("base") if isinstance(pr, dict) and isinstance(pr.get("base"), dict) else {}
            core.install_guard_context(
                module,
                self,
                int(number),
                core._normalize_sha(head_data.get("sha", "")),
                core._normalize_sha(base_data.get("sha", "")),
            )
        return pr

    client_cls.get_pr = get_pr


def _patch_provider_request(module: Any) -> None:
    hardened = module.hardened
    storage = "_dcoir_review_v48_original_openrouter_request_once"
    original = getattr(hardened, storage, None)
    if original is None:
        original = getattr(hardened, "openrouter_request_once", None)
        if callable(original):
            setattr(hardened, storage, original)
    if not callable(original):
        raise RuntimeError("DCOIR v48 could not locate hardened openrouter_request_once")

    def openrouter_request_once(prompt, schema, config, ignored_providers, model):
        if core._guard(module) is not None:
            core.assert_current_review_scope(module, f"model request ({model})", config)
            core.authorize_provider_request(module, config)
        result = original(prompt, schema, config, ignored_providers, model)
        if core._guard(module) is not None:
            core.assert_current_review_scope(module, f"model response ({model})", config)
        return result

    hardened.openrouter_request_once = openrouter_request_once
    if hasattr(module, "openrouter_request_once"):
        module.openrouter_request_once = openrouter_request_once


def _patch_hybrid_boundary(module: Any) -> None:
    storage = "_dcoir_review_v48_original_hybrid_first_pass"
    original = getattr(module, storage, None)
    if original is None:
        original = getattr(module, "openrouter_review_with_hybrid_first_pass", None)
        if callable(original):
            setattr(module, storage, original)
    if not callable(original):
        return

    def openrouter_review_with_hybrid_first_pass(*args, **kwargs):
        try:
            return original(*args, **kwargs)
        except Exception:
            context = core._guard(module)
            terminal = context.get("terminal") if isinstance(context, dict) else None
            if isinstance(terminal, dict):
                raise core._terminal_exception(terminal)
            raise

    module.openrouter_review_with_hybrid_first_pass = openrouter_review_with_hybrid_first_pass


def _patch_review_publication(module: Any) -> None:
    client_cls = module.base.GitHubClient
    storage = "_dcoir_review_v48_original_create_review"
    original = getattr(client_cls, storage, None)
    if original is None:
        original = getattr(client_cls, "create_review", None)
        if callable(original):
            setattr(client_cls, storage, original)
    if not callable(original):
        raise RuntimeError("DCOIR v48 could not locate GitHubClient.create_review")

    def create_review(self, number, body, event, comments, commit_id):
        context = core._guard(module)
        if (
            isinstance(context, dict)
            and str(getattr(self, "repo", "") or "") == str(context.get("repo", "") or "")
            and int(number) == int(context.get("pr_number", 0) or 0)
        ):
            expected_head = str(context.get("expected_head_sha", "") or "")
            if core._normalize_sha(commit_id) != expected_head:
                raise core._mark_terminal(
                    module,
                    kind="verification_failed",
                    stage="GitHub review publication",
                    reason="review commit id did not match the captured exact PR head",
                    observed_head_sha=core._normalize_sha(commit_id),
                    config=context.get("last_config"),
                )
            core.assert_current_review_scope(
                module,
                "GitHub review publication",
                context.get("last_config"),
            )
        return original(self, number, body, event, comments, commit_id)

    client_cls.create_review = create_review


def _patch_progress_reporter(module: Any) -> None:
    reporter_cls = module.hardened.ProgressReporter
    storage = "_dcoir_review_v48_original_fail"
    original = getattr(reporter_cls, storage, None)
    if original is None:
        original = getattr(reporter_cls, "fail", None)
        if callable(original):
            setattr(reporter_cls, storage, original)
    if not callable(original):
        return

    def fail(self, message: str) -> None:
        raw = str(message or "")
        superseded = core.SUPERSEDED_PREFIX in raw
        verification_failed = core.VERIFICATION_PREFIX in raw
        if not superseded and not verification_failed:
            original(self, message)
            return

        safe_message = module.hardened.sanitize_github_output(raw, self.config)
        state = "superseded" if superseded else "stopped"
        stage = "superseded" if superseded else "head-verification-failed"
        self._record(stage, safe_message[:500])

        context = core._guard(module) or {}
        terminal = context.get("terminal") if isinstance(context.get("terminal"), dict) else {}
        final_lines = []
        if superseded:
            final_lines.extend(
                [
                    "- Result: review superseded because the live PR review scope changed during execution.",
                    "- Stale GitHub review publication: blocked.",
                    "- New model requests after detection: blocked; already authorized/in-flight responses are discarded.",
                ]
            )
        else:
            final_lines.extend(
                [
                    "- Result: review stopped because the live PR review scope could not be verified safely.",
                    "- GitHub review publication after the guard failure: blocked.",
                    "- New model requests after the guard failure: blocked.",
                ]
            )

        expected_head = str(context.get("expected_head_sha", "") or "")
        expected_base = str(context.get("expected_base_sha", "") or "")
        observed_head = str(terminal.get("observed_head_sha", "") or "")
        observed_base = str(terminal.get("observed_base_sha", "") or "")
        if expected_head:
            final_lines.append(f"- Expected head: `{expected_head}`.")
        if observed_head:
            final_lines.append(f"- Observed head: `{observed_head}`.")
        if expected_base:
            final_lines.append(f"- Expected base: `{expected_base}`.")
        if observed_base:
            final_lines.append(f"- Observed base: `{observed_base}`.")
        final_lines.extend(["", "```text", safe_message[:4000], "```"])
        body = self._body(state, final_lines=final_lines)
        try:
            if self.comment_id:
                self.gh.update_issue_comment(self.comment_id, body)
            else:
                comment = self.gh.create_issue_comment(self.issue_number, body)
                self.comment_id = int(comment.get("id", 0))
        except Exception as exc:
            print(
                f"WARN: unable to publish stale-head terminal status: {exc}",
                file=sys.stderr,
                flush=True,
            )

    reporter_cls.fail = fail


def _patch_main_terminal_semantics(module: Any) -> None:
    storage = "_dcoir_review_v48_original_main"
    original = getattr(module, storage, None)
    if original is None:
        original = getattr(module, "main", None)
        if callable(original):
            setattr(module, storage, original)
    if not callable(original):
        raise RuntimeError("DCOIR v48 could not locate review main")

    def main() -> None:
        try:
            original()
        except core.ReviewSupersededError:
            # Supersession is an expected terminal outcome, not an execution
            # failure. The patched reporter has already emitted the explicit
            # terminal status and stale publication is blocked.
            return
        finally:
            core.clear_guard_context(module)

    module.main = main


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, core.APPLIED_MARKER, False):
        return
    _patch_get_pr(module)
    _patch_provider_request(module)
    _patch_hybrid_boundary(module)
    _patch_review_publication(module)
    _patch_progress_reporter(module)
    _patch_main_terminal_semantics(module)
    setattr(module, core.APPLIED_MARKER, True)
