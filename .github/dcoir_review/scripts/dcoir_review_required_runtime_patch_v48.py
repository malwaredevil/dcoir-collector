"""DCOIR Review v48 exact-scope supersession guard for issue #457.

The review workflow is intentionally serialized per pull request today.  A run
that started on an older PR head must therefore stop creating new provider cost
as soon as it can prove that its review scope is no longer current, and it must
never publish a stale GitHub review.

v48 is a source-only execution-policy overlay.  It captures the exact PR head
and base from the first production ``get_pr`` read, verifies that scope before
and after every provider request, and verifies it again immediately before
GitHub review publication.  A moved/closed PR terminates as ``superseded``;
an unavailable or malformed live scope fails closed as a verification error.
Already in-flight requests cannot be revoked by this source layer, but their
results are discarded and no new request is allowed after supersession is
detected.

No workflow concurrency setting is changed here.  That remains a separately
governed workflow-YAML decision.
"""

from __future__ import annotations

import os
import re
import sys
import threading
from typing import Any


VERSION = "v48"
APPLIED_MARKER = "_dcoir_review_v48_applied"
GUARD_ATTR = "_dcoir_review_v48_scope_guard"
ARTIFACT_PATH = "metadata/stale-head-supersession.json"
SUPERSEDED_PREFIX = "DCOIR_REVIEW_SUPERSEDED:"
VERIFICATION_PREFIX = "DCOIR_REVIEW_HEAD_VERIFICATION_FAILED:"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ReviewSupersededError(Exception):
    """Raised when the live PR review scope no longer matches the run scope."""


class ReviewHeadVerificationError(Exception):
    """Raised when the live PR scope cannot be verified safely."""


def _normalize_sha(value: Any) -> str:
    return str(value or "").strip().lower()


def _valid_sha(value: str) -> bool:
    return bool(_SHA_RE.fullmatch(value))


def _guard(module: Any) -> dict[str, Any] | None:
    value = getattr(module, GUARD_ATTR, None)
    return value if isinstance(value, dict) else None


def clear_guard_context(module: Any) -> None:
    if hasattr(module, GUARD_ATTR):
        delattr(module, GUARD_ATTR)


def install_guard_context(
    module: Any,
    github: Any,
    pr_number: int,
    expected_head_sha: str,
    expected_base_sha: str,
) -> dict[str, Any]:
    """Install one immutable expected review scope for the current process."""

    head = _normalize_sha(expected_head_sha)
    base_sha = _normalize_sha(expected_base_sha)
    if not _valid_sha(head) or not _valid_sha(base_sha):
        missing = []
        if not _valid_sha(head):
            missing.append("head")
        if not _valid_sha(base_sha):
            missing.append("base")
        raise ReviewHeadVerificationError(
            f"{VERIFICATION_PREFIX} initial PR metadata had invalid {'/'.join(missing)} SHA"
        )

    context: dict[str, Any] = {
        "github": github,
        "repo": str(getattr(github, "repo", "") or ""),
        "pr_number": int(pr_number),
        "expected_head_sha": head,
        "expected_base_sha": base_sha,
        "check_count": 0,
        "terminal": None,
        "last_config": None,
        "lock": threading.Lock(),
    }
    setattr(module, GUARD_ATTR, context)
    return context


def _terminal_exception(terminal: dict[str, Any]) -> Exception:
    message = str(terminal.get("message", "") or "")
    if terminal.get("kind") == "superseded":
        return ReviewSupersededError(message)
    return ReviewHeadVerificationError(message)


def _terminal_payload(context: dict[str, Any], terminal: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "dcoir_review_stale_head_guard_v1",
        "result": str(terminal.get("kind", "") or ""),
        "stage": str(terminal.get("stage", "") or ""),
        "reason": str(terminal.get("reason", "") or ""),
        "pr_number": int(context.get("pr_number", 0) or 0),
        "expected_head_sha": str(context.get("expected_head_sha", "") or ""),
        "observed_head_sha": str(terminal.get("observed_head_sha", "") or ""),
        "expected_base_sha": str(context.get("expected_base_sha", "") or ""),
        "observed_base_sha": str(terminal.get("observed_base_sha", "") or ""),
        "observed_pr_state": str(terminal.get("observed_pr_state", "") or ""),
        "checks_completed": int(context.get("check_count", 0) or 0),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID", "").strip(),
    }


def _write_terminal_artifact(module: Any, config: Any, terminal: dict[str, Any]) -> None:
    context = _guard(module)
    if context is None or config is None:
        return
    writer = getattr(module.hardened, "write_debug_json_artifact_safely", None)
    if not callable(writer):
        return
    try:
        writer(config, ARTIFACT_PATH, _terminal_payload(context, terminal))
    except Exception as exc:
        print(
            f"WARN: unable to write stale-head guard artifact: {exc}",
            file=sys.stderr,
            flush=True,
        )


def _mark_terminal(
    module: Any,
    *,
    kind: str,
    stage: str,
    reason: str,
    observed_head_sha: str = "",
    observed_base_sha: str = "",
    observed_pr_state: str = "",
    config: Any = None,
) -> Exception:
    context = _guard(module)
    if context is None:
        prefix = SUPERSEDED_PREFIX if kind == "superseded" else VERIFICATION_PREFIX
        error_cls = ReviewSupersededError if kind == "superseded" else ReviewHeadVerificationError
        return error_cls(f"{prefix} {reason}")

    lock = context.get("lock")
    if not hasattr(lock, "__enter__"):
        lock = threading.Lock()
        context["lock"] = lock
    with lock:
        terminal = context.get("terminal")
        if not isinstance(terminal, dict):
            prefix = SUPERSEDED_PREFIX if kind == "superseded" else VERIFICATION_PREFIX
            terminal = {
                "kind": kind,
                "stage": stage,
                "reason": reason,
                "observed_head_sha": _normalize_sha(observed_head_sha),
                "observed_base_sha": _normalize_sha(observed_base_sha),
                "observed_pr_state": str(observed_pr_state or "").strip().lower(),
                "message": f"{prefix} {reason}",
            }
            context["terminal"] = terminal
        if config is not None:
            context["last_config"] = config

    _write_terminal_artifact(module, config or context.get("last_config"), terminal)
    return _terminal_exception(terminal)


def assert_current_review_scope(module: Any, stage: str, config: Any = None) -> dict[str, Any] | None:
    """Fail closed if the live PR head/base/state differs from the run scope."""

    context = _guard(module)
    if context is None:
        # Direct unit/probe calls that never entered the production PR main path
        # intentionally retain their historical behavior.
        return None
    if config is not None:
        context["last_config"] = config

    terminal = context.get("terminal")
    if isinstance(terminal, dict):
        _write_terminal_artifact(module, config or context.get("last_config"), terminal)
        raise _terminal_exception(terminal)

    github = context.get("github")
    pr_number = int(context.get("pr_number", 0) or 0)
    try:
        live = github.get_pr(pr_number)
    except Exception as exc:
        raise _mark_terminal(
            module,
            kind="verification_failed",
            stage=stage,
            reason=f"could not verify live PR scope before {stage}: {str(exc)[:240]}",
            config=config,
        ) from exc

    if not isinstance(live, dict):
        raise _mark_terminal(
            module,
            kind="verification_failed",
            stage=stage,
            reason=f"live PR scope was not an object before {stage}",
            config=config,
        )

    current_head = _normalize_sha(live.get("head", {}).get("sha", "") if isinstance(live.get("head"), dict) else "")
    current_base = _normalize_sha(live.get("base", {}).get("sha", "") if isinstance(live.get("base"), dict) else "")
    state = str(live.get("state", "") or "").strip().lower()

    if not _valid_sha(current_head) or not _valid_sha(current_base):
        raise _mark_terminal(
            module,
            kind="verification_failed",
            stage=stage,
            reason=f"live PR metadata had an invalid head/base SHA before {stage}",
            observed_head_sha=current_head,
            observed_base_sha=current_base,
            observed_pr_state=state,
            config=config,
        )

    if state != "open":
        raise _mark_terminal(
            module,
            kind="superseded",
            stage=stage,
            reason=f"PR is no longer open before {stage}: state={state or 'missing'}",
            observed_head_sha=current_head,
            observed_base_sha=current_base,
            observed_pr_state=state,
            config=config,
        )

    expected_head = str(context.get("expected_head_sha", "") or "")
    expected_base = str(context.get("expected_base_sha", "") or "")
    if current_head != expected_head:
        raise _mark_terminal(
            module,
            kind="superseded",
            stage=stage,
            reason=(
                f"PR head moved before {stage}: "
                f"{expected_head[:12]} -> {current_head[:12]}"
            ),
            observed_head_sha=current_head,
            observed_base_sha=current_base,
            observed_pr_state=state,
            config=config,
        )
    if current_base != expected_base:
        raise _mark_terminal(
            module,
            kind="superseded",
            stage=stage,
            reason=(
                f"PR base moved before {stage}: "
                f"{expected_base[:12]} -> {current_base[:12]}"
            ),
            observed_head_sha=current_head,
            observed_base_sha=current_base,
            observed_pr_state=state,
            config=config,
        )

    lock = context.get("lock")
    if hasattr(lock, "__enter__"):
        with lock:
            context["check_count"] = int(context.get("check_count", 0) or 0) + 1
    else:
        context["check_count"] = int(context.get("check_count", 0) or 0) + 1
    return live


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
        if _guard(module) is None and _capture_is_production_target(self, number):
            head = _normalize_sha(pr.get("head", {}).get("sha", "") if isinstance(pr, dict) and isinstance(pr.get("head"), dict) else "")
            base_sha = _normalize_sha(pr.get("base", {}).get("sha", "") if isinstance(pr, dict) and isinstance(pr.get("base"), dict) else "")
            install_guard_context(module, self, int(number), head, base_sha)
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
        if _guard(module) is not None:
            assert_current_review_scope(module, f"model request ({model})", config)
        result = original(prompt, schema, config, ignored_providers, model)
        if _guard(module) is not None:
            assert_current_review_scope(module, f"model response ({model})", config)
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
            context = _guard(module)
            terminal = context.get("terminal") if isinstance(context, dict) else None
            if isinstance(terminal, dict):
                raise _terminal_exception(terminal)
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
        context = _guard(module)
        if (
            isinstance(context, dict)
            and str(getattr(self, "repo", "") or "") == str(context.get("repo", "") or "")
            and int(number) == int(context.get("pr_number", 0) or 0)
        ):
            expected_head = str(context.get("expected_head_sha", "") or "")
            if _normalize_sha(commit_id) != expected_head:
                raise _mark_terminal(
                    module,
                    kind="verification_failed",
                    stage="GitHub review publication",
                    reason="review commit id did not match the captured exact PR head",
                    observed_head_sha=_normalize_sha(commit_id),
                    config=context.get("last_config"),
                )
            assert_current_review_scope(
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
        superseded = SUPERSEDED_PREFIX in raw
        verification_failed = VERIFICATION_PREFIX in raw
        if not superseded and not verification_failed:
            original(self, message)
            return

        safe_message = module.hardened.sanitize_github_output(raw, self.config)
        state = "superseded" if superseded else "stopped"
        stage = "superseded" if superseded else "head-verification-failed"
        self._record(stage, safe_message[:500])

        context = _guard(module) or {}
        terminal = context.get("terminal") if isinstance(context.get("terminal"), dict) else {}
        final_lines = []
        if superseded:
            final_lines.extend(
                [
                    "- Result: review superseded because the live PR review scope changed during execution.",
                    "- Stale GitHub review publication: blocked.",
                    "- New model requests after detection: blocked; already in-flight responses are discarded.",
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
        except ReviewSupersededError:
            # Supersession is an expected terminal outcome, not an execution
            # failure. The patched reporter has already emitted the explicit
            # terminal status and stale publication is blocked.
            return
        finally:
            clear_guard_context(module)

    module.main = main


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    _patch_get_pr(module)
    _patch_provider_request(module)
    _patch_hybrid_boundary(module)
    _patch_review_publication(module)
    _patch_progress_reporter(module)
    _patch_main_terminal_semantics(module)
    setattr(module, APPLIED_MARKER, True)
