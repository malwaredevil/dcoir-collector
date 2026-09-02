"""Trusted review-state parsing for the v41 runtime overlay."""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

VERSION = "v41"
ARCHITECTURE_CONTRACT = "architecture-b-v1"
ARCHITECTURE_CONTRACT_MARKER = f"DCOIR review contract: {ARCHITECTURE_CONTRACT}"
BASE_CONTRACT_PREFIX = "DCOIR review base: "
PROVENANCE_PREFIX = "DCOIR review provenance: "
TRUSTED_REVIEW_AUTHORS = frozenset({"github-actions[bot]"})
TRUSTED_WORKFLOW_NAME = "28 Review - DCOIR Review"
TRUSTED_WORKFLOW_PATH = ".github/workflows/openrouter-pr-review.yml"
TRUSTED_WORKFLOW_EVENT = "issue_comment"
TRUSTED_DEFAULT_BRANCH = "main"
TRUSTED_TRIGGER_ACTORS = frozenset({"malwaredevil"})
SIGNATURE_FIELD = "signature"


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


def _review_provenance(review: dict[str, Any]) -> dict[str, str]:
    body = str(review.get("body", "") or "")
    marker_index = body.rfind(PROVENANCE_PREFIX)
    if marker_index < 0:
        return {}
    value = body[marker_index + len(PROVENANCE_PREFIX) :].splitlines()[0].strip()
    provenance: dict[str, str] = {}
    for segment in value.split(";"):
        item = segment.strip()
        if not item or "=" not in item:
            continue
        key, separator, raw_value = item.partition("=")
        if separator:
            provenance[key.strip().lower()] = raw_value.strip()
    return provenance


def _signing_secrets() -> tuple[bytes, ...]:
    """Return available signing secrets, preferring a dedicated future key.

    The current workflow already scopes OPENROUTER_API_KEY to the DCOIR review
    reusable workflow, so it is a safe migration fallback for HMAC derivation.
    A dedicated DCOIR_REVIEW_STATE_HMAC_KEY can be introduced later without
    invalidating receipts created with the fallback because verification accepts
    either available key.
    """
    values: list[bytes] = []
    for name in ("DCOIR_REVIEW_STATE_HMAC_KEY", "OPENROUTER_API_KEY"):
        raw = str(os.environ.get(name, "") or "")
        if not raw:
            continue
        encoded = raw.encode("utf-8")
        if encoded not in values:
            values.append(encoded)
    return tuple(values)


def _frontier_signature_payload(
    repo: str,
    pr_number: int,
    reviewed_base: str,
    reviewed_head: str,
    run_id: str,
) -> bytes:
    return "\n".join(
        (
            "dcoir-review-frontier-v1",
            f"repo={repo.strip().lower()}",
            f"pr={int(pr_number)}",
            f"base={reviewed_base.strip().lower()}",
            f"head={reviewed_head.strip().lower()}",
            f"run={run_id.strip()}",
            f"contract={ARCHITECTURE_CONTRACT}",
            f"workflow={TRUSTED_WORKFLOW_PATH}",
        )
    ).encode("utf-8")


def build_review_provenance_marker(
    repo: str,
    pr_number: int,
    reviewed_base: str,
    reviewed_head: str,
    run_id: str,
    workflow_name: str,
) -> str:
    """Build an HMAC-bound receipt for one DCOIR-reviewed PR head."""
    if workflow_name != TRUSTED_WORKFLOW_NAME:
        return ""
    if not repo or not pr_number or not reviewed_base or not reviewed_head or not run_id:
        return ""
    secrets = _signing_secrets()
    if not secrets:
        return ""
    payload = _frontier_signature_payload(repo, pr_number, reviewed_base, reviewed_head, run_id)
    signature = hmac.new(secrets[0], payload, hashlib.sha256).hexdigest()
    return (
        f"{PROVENANCE_PREFIX}workflow-run={run_id}; workflow-name={workflow_name}; "
        f"pr-number={int(pr_number)}; reviewed-head={reviewed_head.strip().lower()}; "
        f"{SIGNATURE_FIELD}={signature}"
    )


def _has_valid_signature(
    gh: Any,
    pr_number: int,
    review_base: str,
    review_head: str,
    provenance: dict[str, str],
) -> bool:
    signature = str(provenance.get(SIGNATURE_FIELD, "") or "").strip().lower()
    run_id = str(provenance.get("workflow-run", "") or "").strip()
    marker_pr = str(provenance.get("pr-number", "") or "").strip()
    marker_head = str(provenance.get("reviewed-head", "") or "").strip().lower()
    if len(signature) != 64 or any(character not in "0123456789abcdef" for character in signature):
        return False
    if marker_pr != str(int(pr_number)) or marker_head != review_head:
        return False
    repo = str(getattr(gh, "repo", "") or "").strip()
    if not repo or not run_id or not review_base or not review_head:
        return False
    payload = _frontier_signature_payload(repo, pr_number, review_base, review_head, run_id)
    return any(
        hmac.compare_digest(signature, hmac.new(secret, payload, hashlib.sha256).hexdigest())
        for secret in _signing_secrets()
    )


def _has_verified_run_provenance(
    gh: Any,
    pr_number: int,
    review: dict[str, Any],
    review_base: str,
    provenance: dict[str, str],
) -> bool:
    run_id = str(provenance.get("workflow-run", "") or "").strip()
    workflow_name = str(provenance.get("workflow-name", "") or "").strip()
    review_head = str(review.get("commit_id", "") or "").strip().lower()
    if workflow_name != TRUSTED_WORKFLOW_NAME or not run_id or not review_head:
        return False
    if not _has_valid_signature(gh, pr_number, review_base, review_head, provenance):
        return False
    repo = str(getattr(gh, "repo", "") or "").strip()
    if not repo:
        return False
    try:
        run = gh.request("GET", f"/repos/{repo}/actions/runs/{run_id}")
    except Exception:
        return False
    if not isinstance(run, dict):
        return False
    expected_run_name = f"{TRUSTED_WORKFLOW_NAME} | PR #{int(pr_number)} | malwaredevil"
    actor = run.get("actor", {})
    actor_login = str(actor.get("login", "") or "").strip().lower() if isinstance(actor, dict) else ""
    return all(
        (
            str(run.get("id", "") or "").strip() == run_id,
            str(run.get("path", "") or "").strip() == TRUSTED_WORKFLOW_PATH,
            str(run.get("event", "") or "").strip().lower() == TRUSTED_WORKFLOW_EVENT,
            str(run.get("status", "") or "").strip().lower() == "completed",
            str(run.get("conclusion", "") or "").strip().lower() == "success",
            str(run.get("head_branch", "") or "").strip() == TRUSTED_DEFAULT_BRANCH,
            actor_login in TRUSTED_TRIGGER_ACTORS,
            str(run.get("name", "") or "").strip() == expected_run_name,
        )
    )


def latest_compatible_context_review(module: Any, gh: Any, pr_number: int) -> dict[str, Any] | None:
    """Return the newest cryptographically bound DCOIR context review for v41."""
    markers = _review_markers(module)
    reviews = module.list_pr_reviews(gh, pr_number)
    for review in reversed(reviews):
        if _review_author_login(review) not in TRUSTED_REVIEW_AUTHORS:
            continue
        body = str(review.get("body", "") or "")
        commit_id = str(review.get("commit_id", "") or "").strip()
        if not commit_id or not any(marker in body for marker in markers):
            continue
        context_index = body.rfind(module.CONTEXT_REVIEW_MARKER)
        if context_index < 0:
            continue
        trusted_context = body[context_index:]
        if ARCHITECTURE_CONTRACT_MARKER not in trusted_context:
            continue
        review_base = _review_base_sha({"body": trusted_context})
        if not review_base:
            continue
        provenance = _review_provenance({"body": trusted_context})
        if not provenance or not _has_verified_run_provenance(
            gh, pr_number, review, review_base, provenance
        ):
            continue
        return review
    return None
