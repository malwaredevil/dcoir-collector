"""Trusted review-state parsing for the v41 runtime overlay."""

from __future__ import annotations

from typing import Any

VERSION = "v41"
ARCHITECTURE_CONTRACT = "architecture-b-v1"
ARCHITECTURE_CONTRACT_MARKER = f"DCOIR review contract: {ARCHITECTURE_CONTRACT}"
BASE_CONTRACT_PREFIX = "DCOIR review base: "
TRUSTED_REVIEW_AUTHORS = frozenset({"github-actions[bot]"})


def _review_markers(module: Any) -> tuple[str, ...]:
    return (module.base.MARKER, *getattr(module.base, "LEGACY_MARKERS", ()))


def _review_author_login(review: dict[str, Any]) -> str:
    user = review.get("user", {})
    if not isinstance(user, dict):
        return ""
    return str(user.get("login", "") or "").strip().lower()


def _review_base_sha(review: dict[str, Any]) -> str:
    body = str(review.get("body", "") or "")
    marker_index = body.rfind(BASE_CONTRACT_PREFIX)
    if marker_index < 0:
        return ""
    value_start = marker_index + len(BASE_CONTRACT_PREFIX)
    value = body[value_start : value_start + 40].strip().lower()
    if len(value) == 40 and all(character in "0123456789abcdef" for character in value):
        return value
    return ""


def latest_compatible_context_review(module: Any, gh: Any, pr_number: int) -> dict[str, Any] | None:
    """Return the newest trusted DCOIR context review compatible with v41."""
    markers = _review_markers(module)
    reviews = module.list_pr_reviews(gh, pr_number)
    for review in reversed(reviews):
        if _review_author_login(review) not in TRUSTED_REVIEW_AUTHORS:
            continue
        body = str(review.get("body", "") or "")
        commit_id = str(review.get("commit_id", "") or "").strip()
        if not commit_id:
            continue
        if not any(marker in body for marker in markers):
            continue
        context_index = body.rfind(module.CONTEXT_REVIEW_MARKER)
        if context_index < 0:
            continue
        trusted_context = body[context_index:]
        if ARCHITECTURE_CONTRACT_MARKER not in trusted_context:
            continue
        if not _review_base_sha({"body": trusted_context}):
            continue
        return review
    return None
