"""Trusted prior-review readback for Architecture-B verified gate state v50."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

import dcoir_review_required_runtime_patch_v41_review_state as v41_state
import dcoir_review_required_runtime_patch_v41_scope as v41_scope
import dcoir_review_required_runtime_patch_v43_reuse as v43_reuse
import dcoir_review_required_runtime_patch_v45 as v45
import dcoir_review_required_runtime_patch_v50_state as state


def _artifact_json(payload: bytes, suffix: str) -> dict[str, Any] | None:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        matches = [name for name in archive.namelist() if name.endswith(suffix)]
        if not matches:
            return None
        if len(matches) != 1:
            raise RuntimeError(f"multiple trusted prior {suffix} entries")
        info = archive.getinfo(matches[0])
        if info.file_size > v43_reuse.MAX_ARTIFACT_BYTES:
            raise RuntimeError(f"trusted prior {suffix} exceeds read limit")
        raw = archive.read(info)
        if len(raw) > v43_reuse.MAX_ARTIFACT_BYTES:
            raise RuntimeError(f"trusted prior {suffix} exceeds read limit")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"trusted prior {suffix} is not an object")
    return value


def _debug_artifact_payload(gh: Any, pr_number: int, run_id: str) -> bytes:
    listing = gh.request("GET", f"/repos/{gh.repo}/actions/runs/{run_id}/artifacts?per_page=100")
    artifacts = listing.get("artifacts", []) if isinstance(listing, dict) else []
    expected = f"dcoir-review-debug-{pr_number}-{run_id}"
    candidates = [
        item
        for item in artifacts
        if isinstance(item, dict) and item.get("name") == expected and not bool(item.get("expired"))
    ]
    if len(candidates) != 1:
        raise RuntimeError("trusted prior DCOIR debug artifact missing, expired, or ambiguous")
    return v43_reuse.artifact_zip_bytes(gh, int(candidates[0]["id"]))


def _indeterminate(reason: str, prior_count: int = 0) -> dict[str, Any]:
    return state._indeterminate(reason, prior_count)


def load_prior_gate_context(module: Any, gh: Any, pr: dict[str, Any]) -> dict[str, Any]:
    scope = getattr(gh, v41_scope.SCOPE_CACHE_ATTR, None)
    current_head = state._clean_path(pr.get("head", {}).get("sha", "")).lower()
    if not state.incremental_scope(scope):
        return {
            "status": "clear",
            "carried_records": [],
            "reason": "full-review-seeds-current-gate-state",
            "source": "current-full-review",
            "indeterminate_prior_count": 0,
        }
    prior_head = state._clean_path(scope.get("prior_reviewed_head_sha")).lower()
    if state._clean_path(scope.get("current_head_sha")).lower() != current_head:
        return _indeterminate("incremental-scope-current-head-mismatch")
    changed = state.changed_paths(scope)
    pr_number = int(pr.get("number") or 0)
    if not pr_number or not prior_head:
        return _indeterminate("incremental-prior-identity-missing")
    try:
        review = v41_state.latest_compatible_context_review(module, gh, pr_number)
        if not isinstance(review, dict):
            return _indeterminate("trusted-prior-review-missing")
        if state._clean_path(review.get("commit_id")).lower() != prior_head:
            return _indeterminate("trusted-prior-review-head-mismatch")
        run_id = v43_reuse.parse_run_id(review)
        if not run_id:
            return _indeterminate("trusted-prior-review-run-missing")
        payload = _debug_artifact_payload(gh, pr_number, run_id)
        prior_state = _artifact_json(payload, state.STATE_ARTIFACT_PATH)
        if prior_state is not None:
            invalid = state.validate_state(prior_state, prior_head, run_id)
            if invalid:
                return _indeterminate(invalid)
            if str(prior_state.get("gate_status", "") or "") == "indeterminate":
                return _indeterminate(
                    str(prior_state.get("prior_state_reason", "") or "prior-state-indeterminate"),
                    int(prior_state.get("indeterminate_prior_count", 0) or 0),
                )
            carried = state.carry_records(
                [item for item in prior_state.get("unresolved_findings", []) if isinstance(item, dict)],
                changed,
                current_head,
            )
            return {
                "status": "blocked" if carried else "clear",
                "carried_records": carried,
                "reason": "trusted-v50-gate-state",
                "source": "v50-state",
                "indeterminate_prior_count": 0,
            }
        legacy = _artifact_json(payload, v45.ARTIFACT_PATH)
        if legacy is None:
            return _indeterminate("trusted-prior-gate-artifact-missing")
        published = int(legacy.get("published_finding_count", 0) or 0)
        comments: list[dict[str, Any]] = []
        if published > 0:
            review_id = int(review.get("id") or 0)
            if not review_id:
                return _indeterminate("legacy-v45-review-id-missing", published)
            response = gh.request(
                "GET", f"/repos/{gh.repo}/pulls/{pr_number}/reviews/{review_id}/comments?per_page=100"
            )
            if isinstance(response, list):
                comments = [item for item in response if isinstance(item, dict)]
            elif isinstance(response, dict) and isinstance(response.get("comments"), list):
                comments = [item for item in response["comments"] if isinstance(item, dict)]
            else:
                return _indeterminate("legacy-v45-review-comments-invalid", published)
        return state.migrate_legacy_v45(legacy, comments, prior_head, changed, current_head)
    except Exception as exc:
        return _indeterminate(f"trusted-prior-gate-readback-failed:{type(exc).__name__}")
