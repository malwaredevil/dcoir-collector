"""Core exact-scope state and verification for DCOIR Review v48."""

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
        "request_ticket_count": 0,
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
        "request_tickets_issued": int(context.get("request_ticket_count", 0) or 0),
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


def _context_lock(context: dict[str, Any]) -> Any:
    lock = context.get("lock")
    if not hasattr(lock, "__enter__"):
        lock = threading.Lock()
        context["lock"] = lock
    return lock


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

    with _context_lock(context):
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
    """Fail closed if live PR head/base/state differs from the captured run scope."""

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

    head_data = live.get("head") if isinstance(live.get("head"), dict) else {}
    base_data = live.get("base") if isinstance(live.get("base"), dict) else {}
    current_head = _normalize_sha(head_data.get("sha", ""))
    current_base = _normalize_sha(base_data.get("sha", ""))
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
            reason=f"PR head moved before {stage}: {expected_head[:12]} -> {current_head[:12]}",
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
            reason=f"PR base moved before {stage}: {expected_base[:12]} -> {current_base[:12]}",
            observed_head_sha=current_head,
            observed_base_sha=current_base,
            observed_pr_state=state,
            config=config,
        )

    with _context_lock(context):
        # Another concurrent request may have established a terminal state while
        # this thread was performing its GitHub read. Do not return a stale pass.
        terminal = context.get("terminal")
        if isinstance(terminal, dict):
            raise _terminal_exception(terminal)
        context["check_count"] = int(context.get("check_count", 0) or 0) + 1
    return live


def authorize_provider_request(module: Any, config: Any = None) -> int | None:
    """Issue a request ticket only while no terminal supersession is known.

    The ticket closes the concurrency race between a successful live-scope check
    and the provider call. A request with a ticket is considered already in
    flight for terminal-reporting purposes; after a terminal is recorded, no new
    ticket can be issued.
    """

    context = _guard(module)
    if context is None:
        return None
    if config is not None:
        context["last_config"] = config
    with _context_lock(context):
        terminal = context.get("terminal")
        if isinstance(terminal, dict):
            raise _terminal_exception(terminal)
        ticket = int(context.get("request_ticket_count", 0) or 0) + 1
        context["request_ticket_count"] = ticket
        return ticket
