"""DCOIR Review v48 exact-scope supersession execution policy.

A run captures the exact PR head and base from its first production metadata
read. Before and after provider requests, and immediately before final GitHub
review publication, v48 verifies that the live PR remains open on that same
scope. A moved/closed scope terminates as ``superseded``; unavailable or
malformed live scope fails closed as a verification error.

The implementation is split so the connector-facing entry module stays small:
``dcoir_review_required_runtime_patch_v48_core`` owns exact-scope state and
verification, while ``dcoir_review_required_runtime_patch_v48_hooks`` owns the
production provider/publication hooks. Workflow concurrency is intentionally
unchanged and remains a separately governed workflow-YAML decision.
"""

from dcoir_review_required_runtime_patch_v48_core import (
    APPLIED_MARKER,
    ARTIFACT_PATH,
    GUARD_ATTR,
    SUPERSEDED_PREFIX,
    VERIFICATION_PREFIX,
    VERSION,
    ReviewHeadVerificationError,
    ReviewSupersededError,
    _guard,
    _mark_terminal,
    _normalize_sha,
    _terminal_exception,
    assert_current_review_scope,
    authorize_provider_request,
    clear_guard_context,
    install_guard_context,
)
from dcoir_review_required_runtime_patch_v48_hooks import apply_pareto_context_module

__all__ = [
    "VERSION",
    "APPLIED_MARKER",
    "GUARD_ATTR",
    "ARTIFACT_PATH",
    "SUPERSEDED_PREFIX",
    "VERIFICATION_PREFIX",
    "ReviewSupersededError",
    "ReviewHeadVerificationError",
    "install_guard_context",
    "clear_guard_context",
    "assert_current_review_scope",
    "authorize_provider_request",
    "apply_pareto_context_module",
]
