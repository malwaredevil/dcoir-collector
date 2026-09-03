"""Fail-closed semantic-result reuse helpers for DCOIR v43."""

from __future__ import annotations

import hashlib
import inspect
import io
import json
import urllib.error
import urllib.request
import zipfile
from typing import Any

import dcoir_review_required_runtime_patch_v41_review_state as v41_state
import dcoir_review_required_runtime_patch_v42_fingerprints as v42_fp

VERSION = "v43"
REUSE_CONTRACT = "architecture-b-semantic-result-reuse-v1"
DEPENDENCY_CONTRACT = "dependency-context-v2"
DEPENDENCY_MODE = "exact-semantic-prompt-v1"
MANIFEST_PATH = "metadata/semantic-result-reuse-manifest.json"
MAX_ARTIFACT_BYTES = 5_000_000


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def source_identity(context: dict[str, Any]) -> str:
    item = context.get("item", {})
    if isinstance(item, dict):
        sha = str(item.get("sha", "") or "").strip().lower()
        if len(sha) == 40 and all(char in "0123456789abcdef" for char in sha):
            return f"blob:{sha}"
    return f"text-sha256:{sha_text(str(context.get('text', '') or ''))}"


def reviewer_fingerprint(module: Any) -> str:
    try:
        source = inspect.getsource(module.build_per_file_review_prompt)
    except (OSError, TypeError):
        source = repr(module.build_per_file_review_prompt)
    return sha_text(source)


def path_risk_digest(module: Any, risk_sentinels: list[Any], path: str) -> str:
    selected = [sentinel for sentinel in risk_sentinels if getattr(sentinel, "path", None) == path]
    return str(module.hardened.risk_sentinel_digest(selected) or "") if selected else ""


def reuse_material(
    module: Any,
    context: dict[str, Any],
    pr: dict[str, Any],
    diff: str,
    schema: dict[str, Any],
    config: Any,
    risk_sentinels: list[Any],
    review_mode: str,
) -> dict[str, Any]:
    path = str(context.get("path", "") or "").strip()
    path_sentinels = [sentinel for sentinel in risk_sentinels if getattr(sentinel, "path", None) == path]
    prompt = module.build_per_file_review_prompt(
        pr, context["item"], context["text"], diff, config, path_sentinels, review_mode
    )
    prompt_sha = sha_text(prompt)
    dependency_context = {
        "contract": DEPENDENCY_CONTRACT,
        "mode": DEPENDENCY_MODE,
        "expanded_paths": [],
        "semantic_prompt_sha256": prompt_sha,
    }
    material = {
        "contract": REUSE_CONTRACT,
        "runtime_version": VERSION,
        "architecture_contract": getattr(v41_state, "ARCHITECTURE_CONTRACT", "architecture-b-v1"),
        "path": path,
        "source_identity": source_identity(context),
        "semantic_prompt_sha256": prompt_sha,
        "reviewer_fingerprint": reviewer_fingerprint(module),
        "schema_sha256": v42_fp.digest(schema),
        "config_sha256": v42_fp.digest(v42_fp.config_snapshot(config)),
        "dependency_context": dependency_context,
        "dependency_sha256": v42_fp.digest(dependency_context),
        "risk_fingerprint": path_risk_digest(module, risk_sentinels, path),
        "review_mode": str(review_mode or ""),
    }
    material["reuse_key"] = v42_fp.digest(material)
    material["prompt_chars"] = len(prompt)
    return material


def evaluate_reuse_candidate(
    material: dict[str, Any],
    prior_record: Any,
    trusted_prior_head: str,
) -> tuple[bool, str]:
    """Return a fail-closed decision for one exact semantic-input record."""
    if not isinstance(prior_record, dict):
        return False, "prior-record-missing"
    if prior_record.get("contract") != REUSE_CONTRACT:
        return False, "reuse-contract-mismatch"
    if str(prior_record.get("outcome", "") or "") != "complete":
        return False, "prior-result-incomplete"
    if not trusted_prior_head:
        return False, "trusted-prior-head-missing"
    recorded_head = str(
        prior_record.get("carried_forward_head", "")
        or prior_record.get("origin_reviewed_head", "")
        or ""
    )
    if recorded_head != trusted_prior_head:
        return False, "prior-head-mismatch"
    field_reasons = (
        ("source_identity", "source-changed"),
        ("runtime_version", "reviewer-runtime-changed"),
        ("reviewer_fingerprint", "reviewer-changed"),
        ("schema_sha256", "schema-changed"),
        ("config_sha256", "config-changed"),
        ("dependency_sha256", "dependency-context-changed"),
        ("risk_fingerprint", "risk-invariant-changed"),
        ("review_mode", "review-mode-changed"),
        ("semantic_prompt_sha256", "semantic-prompt-changed"),
    )
    for field, reason in field_reasons:
        if prior_record.get(field) != material.get(field):
            return False, reason
    if str(prior_record.get("reuse_key", "") or "") != str(material.get("reuse_key", "") or ""):
        return False, "reuse-key-mismatch"
    if not isinstance(prior_record.get("result"), dict):
        return False, "prior-result-invalid"
    return True, "exact-semantic-input-match"


def parse_run_id(review: dict[str, Any]) -> str:
    provenance = v41_state._review_provenance(review)
    return str(provenance.get("workflow-run", "") or "").strip()


def artifact_zip_bytes(gh: Any, artifact_id: int) -> bytes:
    url = f"https://api.github.com/repos/{gh.repo}/actions/artifacts/{artifact_id}/zip"
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {gh.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "dcoir-review",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read(MAX_ARTIFACT_BYTES + 1)
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise RuntimeError("prior DCOIR debug artifact exceeds reuse read limit")
    return payload


def manifest_from_zip(payload: bytes) -> dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        matches = [name for name in archive.namelist() if name.endswith(MANIFEST_PATH)]
        if len(matches) != 1:
            raise RuntimeError("trusted prior artifact does not contain exactly one reuse manifest")
        raw = archive.read(matches[0])
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("trusted prior reuse manifest is not an object")
    return value


def trusted_prior_manifest(
    module: Any,
    gh: Any,
    pr: dict[str, Any],
) -> tuple[dict[str, Any] | None, str, str]:
    pr_number = int(pr.get("number") or 0)
    current_head = str(pr.get("head", {}).get("sha", "") or "").strip().lower()
    if not pr_number or not current_head:
        return None, "", "current-review-identity-missing"
    review = v41_state.latest_compatible_context_review(module, gh, pr_number)
    if not review:
        return None, "", "trusted-prior-review-missing"
    prior_head = str(review.get("commit_id", "") or "").strip().lower()
    run_id = parse_run_id(review)
    if not prior_head or not run_id:
        return None, "", "trusted-prior-provenance-incomplete"
    try:
        comparison = gh.request("GET", f"/repos/{gh.repo}/compare/{prior_head}...{current_head}")
    except Exception:
        return None, "", "prior-ancestry-unverified"
    if str(comparison.get("status", "") or "") not in {"ahead", "identical"}:
        return None, "", "prior-head-not-ancestor"
    try:
        listing = gh.request("GET", f"/repos/{gh.repo}/actions/runs/{run_id}/artifacts?per_page=100")
        artifacts = listing.get("artifacts", []) if isinstance(listing, dict) else []
        expected = f"dcoir-review-debug-{pr_number}-{run_id}"
        candidates = [
            item for item in artifacts
            if isinstance(item, dict)
            and item.get("name") == expected
            and not bool(item.get("expired"))
        ]
        if len(candidates) != 1:
            return None, "", "trusted-prior-artifact-missing-or-expired"
        manifest = manifest_from_zip(artifact_zip_bytes(gh, int(candidates[0]["id"])))
    except (
        KeyError,
        ValueError,
        RuntimeError,
        OSError,
        urllib.error.URLError,
        zipfile.BadZipFile,
        json.JSONDecodeError,
    ):
        return None, "", "trusted-prior-manifest-unreadable"
    if manifest.get("contract") != REUSE_CONTRACT:
        return None, "", "trusted-prior-manifest-contract-mismatch"
    if str(manifest.get("reviewed_head", "") or "").strip().lower() != prior_head:
        return None, "", "trusted-prior-manifest-head-mismatch"
    if str(manifest.get("outcome", "") or "") != "complete":
        return None, "", "trusted-prior-manifest-incomplete"
    return manifest, prior_head, "trusted-prior-manifest-loaded"
