"""Fail-closed semantic-result reuse helpers for DCOIR v43."""

from __future__ import annotations

import hashlib
import inspect
import io
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v41_review_state as v41_state
import dcoir_review_required_runtime_patch_v42_fingerprints as v42_fp

VERSION = "v43"
REUSE_CONTRACT = "architecture-b-semantic-result-reuse-v1"
DEPENDENCY_CONTRACT = "dependency-context-v2"
DEPENDENCY_MODE = "exact-semantic-prompt-v1"
MANIFEST_PATH = "metadata/semantic-result-reuse-manifest.json"
ARTIFACT_DIR_ENV = "DCOIR_REVIEW_DEBUG_ARTIFACT_DIR"
ARTIFACT_DIR_DEFAULT = "dcoir-review-debug"
MAX_ARTIFACT_BYTES = 5_000_000


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


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


def persist_manifest(module: Any, config: Any, manifest: dict[str, Any]) -> bool:
    """Persist exact machine state only when the safety sanitizer is lossless."""
    sanitizer = getattr(getattr(module, "base", None), "sanitize_debug_json_value", None)
    if not callable(sanitizer):
        return False
    try:
        safe_manifest = sanitizer(manifest, config)
    except Exception:
        return False
    if safe_manifest != manifest:
        return False
    try:
        text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        if json.loads(text) != manifest:
            return False
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    if len(text.encode("utf-8")) > MAX_ARTIFACT_BYTES:
        return False
    raw_root = os.environ.get(ARTIFACT_DIR_ENV, "").strip() or ARTIFACT_DIR_DEFAULT
    root = Path(raw_root).resolve(strict=False)
    path = (root / MANIFEST_PATH).resolve(strict=False)
    if root not in path.parents:
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError:
        return False
    return True


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
    opener = urllib.request.build_opener(_NoRedirectHandler)
    try:
        response = opener.open(request, timeout=60)
    except urllib.error.HTTPError as exc:
        if exc.code not in {301, 302, 303, 307, 308}:
            raise
        location = exc.headers.get("Location", "")
        if not location:
            raise
        redirected = urllib.request.Request(
            urllib.parse.urljoin(url, location),
            method="GET",
            headers={"User-Agent": "dcoir-review"},
        )
        response = urllib.request.urlopen(redirected, timeout=60)
    with response:
        payload = response.read(MAX_ARTIFACT_BYTES + 1)
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise RuntimeError("prior DCOIR debug artifact exceeds reuse read limit")
    return payload


def manifest_from_zip(payload: bytes) -> dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        matches = [name for name in archive.namelist() if name.endswith(MANIFEST_PATH)]
        if len(matches) != 1:
            raise RuntimeError("trusted prior artifact does not contain exactly one reuse manifest")
        info = archive.getinfo(matches[0])
        if info.file_size > MAX_ARTIFACT_BYTES:
            raise RuntimeError("trusted prior reuse manifest exceeds read limit")
        raw = archive.read(info)
        if len(raw) > MAX_ARTIFACT_BYTES:
            raise RuntimeError("trusted prior reuse manifest exceeds read limit")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("trusted prior reuse manifest is not an object")
    return value


def validate_manifest(manifest: dict[str, Any], prior_head: str, run_id: str) -> str:
    """Return an empty string only for a complete, current-contract manifest."""
    checks = (
        (manifest.get("contract") == REUSE_CONTRACT, "trusted-prior-manifest-contract-mismatch"),
        (manifest.get("runtime_version") == VERSION, "trusted-prior-manifest-runtime-mismatch"),
        (
            str(manifest.get("reviewed_head", "") or "").strip().lower() == prior_head,
            "trusted-prior-manifest-head-mismatch",
        ),
        (
            str(manifest.get("workflow_run_id", "") or "").strip() == run_id,
            "trusted-prior-manifest-run-mismatch",
        ),
        (
            manifest.get("dependency_contract") == DEPENDENCY_CONTRACT,
            "trusted-prior-manifest-dependency-contract-mismatch",
        ),
        (
            manifest.get("dependency_mode") == DEPENDENCY_MODE,
            "trusted-prior-manifest-dependency-mode-mismatch",
        ),
        (manifest.get("outcome") == "complete", "trusted-prior-manifest-incomplete"),
        (isinstance(manifest.get("records"), list), "trusted-prior-manifest-records-invalid"),
    )
    for passed, reason in checks:
        if not passed:
            return reason
    seen: set[str] = set()
    for record in manifest["records"]:
        if not isinstance(record, dict):
            return "trusted-prior-manifest-record-invalid"
        path = str(record.get("path", "") or "").strip()
        if not path or path in seen:
            return "trusted-prior-manifest-record-path-invalid"
        seen.add(path)
        if record.get("contract") != REUSE_CONTRACT or record.get("outcome") != "complete":
            return "trusted-prior-manifest-record-contract-invalid"
        record_head = str(
            record.get("carried_forward_head", "")
            or record.get("origin_reviewed_head", "")
            or ""
        ).strip().lower()
        if record_head != prior_head:
            return "trusted-prior-manifest-record-head-mismatch"
        if not isinstance(record.get("result"), dict):
            return "trusted-prior-manifest-record-result-invalid"
    return ""


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
            item
            for item in artifacts
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
    invalid_reason = validate_manifest(manifest, prior_head, run_id)
    if invalid_reason:
        return None, "", invalid_reason
    return manifest, prior_head, "trusted-prior-manifest-loaded"
