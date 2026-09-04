"""Canonical semantic-context package and local projection caches for v46."""

from __future__ import annotations

import copy
from typing import Any, Callable

import dcoir_review_required_runtime_patch_v41_scope as v41_scope
import dcoir_review_required_runtime_patch_v42_fingerprints as fingerprints
import dcoir_review_required_runtime_patch_v43_reuse as v43_reuse
from dcoir_review_required_runtime_patch_v46_contract import (
    CONTEXT_PACKAGE_CONTRACT,
    VERSION,
    valid_head,
)


def _head(pr: dict[str, Any]) -> str:
    head = pr.get("head", {}) if isinstance(pr, dict) else {}
    return str(head.get("sha", "") or "").strip().lower() if isinstance(head, dict) else ""


def _file_surface(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in files:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "path": str(item.get("filename", "") or "").replace("\\", "/").strip(),
                "previous_path": str(item.get("previous_filename", "") or "")
                .replace("\\", "/")
                .strip(),
                "status": str(item.get("status", "") or "").strip().lower(),
                "blob_sha": str(item.get("sha", "") or "").strip().lower(),
                "patch_sha256": fingerprints.text_digest(item.get("patch", "")),
            }
        )
    return sorted(rows, key=lambda row: (row["path"], row["status"], row["blob_sha"]))


def file_surface_signature(pr: dict[str, Any], files: list[dict[str, Any]]) -> str:
    return fingerprints.digest({"head": _head(pr), "files": _file_surface(files)})


def input_signature(
    pr: dict[str, Any],
    files: list[dict[str, Any]],
    diff: str,
    deep_context_block: str,
    review_mode: str,
    context_summary: str,
) -> str:
    return fingerprints.digest(
        {
            "head": _head(pr),
            "file_surface": file_surface_signature(pr, files),
            "diff_sha256": fingerprints.text_digest(diff),
            "deep_context_sha256": fingerprints.text_digest(deep_context_block),
            "review_mode": str(review_mode or ""),
            "semantic_context_summary_sha256": fingerprints.text_digest(
                fingerprints.semantic_context_summary(context_summary)
            ),
        }
    )


def _risk_digest(module: Any, risk_sentinels: list[Any]) -> str:
    digest_fn = getattr(getattr(module, "hardened", None), "risk_sentinel_digest", None)
    return str(digest_fn(risk_sentinels) or "") if callable(digest_fn) and risk_sentinels else ""


def build_context_runtime(
    module: Any,
    gh: Any,
    pr: dict[str, Any],
    files: list[dict[str, Any]],
    diff: str,
    schema: dict[str, Any],
    config: Any,
    risk_sentinels: list[Any],
    deep_context_block: str,
    review_mode: str,
    context_summary: str,
    original_build_file_contexts: Callable[..., list[dict[str, Any]]],
) -> dict[str, Any]:
    reviewed_head = _head(pr)
    if not valid_head(reviewed_head):
        raise module.hardened.ReviewQualityError(
            "DCOIR v46 requires an exact 40-character reviewed PR head"
        )

    scope = getattr(gh, v41_scope.SCOPE_CACHE_ATTR, {})
    if not isinstance(scope, dict):
        scope = {}
    # The composed hybrid pipeline requests file contexts in every review mode.
    # Capture that exact-head surface once so all later projections receive the
    # same records without a second GitHub content pass.
    contexts = original_build_file_contexts(gh, pr, files, config)
    context_records = []
    for context in contexts:
        if not isinstance(context, dict):
            continue
        context_records.append(
            {
                "path": str(context.get("path", "") or ""),
                "source_identity": v43_reuse.source_identity(context),
                "text_sha256": fingerprints.text_digest(context.get("text", "")),
                "text_chars": len(str(context.get("text", "") or "")),
            }
        )
    context_records.sort(key=lambda row: row["path"])
    metadata = {
        "contract": CONTEXT_PACKAGE_CONTRACT,
        "runtime_version": VERSION,
        "reviewed_head": reviewed_head,
        "review_mode": str(review_mode or ""),
        "scope_source": str(scope.get("source", "") or ""),
        "scope_compare_status": str(scope.get("compare_status", "") or ""),
        "scope_fallback_reason": str(scope.get("fallback_reason", "") or ""),
        "file_surface_signature": file_surface_signature(pr, files),
        "input_signature": input_signature(
            pr, files, diff, deep_context_block, review_mode, context_summary
        ),
        "schema_sha256": fingerprints.digest(schema),
        "config_sha256": fingerprints.digest(fingerprints.config_snapshot(config)),
        "diff_sha256": fingerprints.text_digest(diff),
        "diff_chars": len(str(diff or "")),
        "deep_context_sha256": fingerprints.text_digest(deep_context_block),
        "deep_context_chars": len(str(deep_context_block or "")),
        "semantic_context_summary_sha256": fingerprints.text_digest(
            fingerprints.semantic_context_summary(context_summary)
        ),
        "risk_sentinel_count": len(risk_sentinels),
        "risk_sentinel_digest": _risk_digest(module, risk_sentinels),
        "changed_file_count": len(_file_surface(files)),
        "file_context_records": context_records,
    }
    metadata["package_id"] = fingerprints.digest(metadata)
    return {
        "metadata": metadata,
        "file_contexts": copy.deepcopy(contexts),
        "per_file_prompt_cache": {},
        "broad_prompt_cache": {},
        "telemetry": {
            "context_package_build_count": 1,
            "file_context_fetch_pass_count": 1,
            "file_context_projection_reuse_count": 0,
            "per_file_prompt_build_count": 0,
            "per_file_prompt_reuse_count": 0,
            "broad_prompt_build_count": 0,
            "broad_prompt_reuse_count": 0,
            "fallback_projection_count": 0,
        },
    }


def public_payload(runtime: dict[str, Any]) -> dict[str, Any]:
    return {
        **copy.deepcopy(runtime.get("metadata", {})),
        "telemetry": copy.deepcopy(runtime.get("telemetry", {})),
    }


def matches_file_surface(
    runtime: dict[str, Any], pr: dict[str, Any], files: list[dict[str, Any]]
) -> bool:
    metadata = runtime.get("metadata", {})
    return bool(metadata) and metadata.get("file_surface_signature") == file_surface_signature(
        pr, files
    )


def per_file_prompt_key(
    module: Any,
    pr: dict[str, Any],
    item: dict[str, Any],
    file_text: str,
    diff: str,
    config: Any,
    path_sentinels: list[Any],
    review_mode: str,
) -> str:
    return fingerprints.digest(
        {
            "head": _head(pr),
            "path": str(item.get("filename", "") or ""),
            "blob_sha": str(item.get("sha", "") or ""),
            "file_text_sha256": fingerprints.text_digest(file_text),
            "patch_sha256": fingerprints.text_digest(item.get("patch", "")),
            "diff_sha256": fingerprints.text_digest(diff),
            "config_sha256": fingerprints.digest(fingerprints.config_snapshot(config)),
            "risk_sha256": _risk_digest(module, path_sentinels),
            "review_mode": str(review_mode or ""),
        }
    )


def broad_prompt_key(
    pr: dict[str, Any],
    files: list[dict[str, Any]],
    diff: str,
    config: Any,
    deep_context_block: str,
    review_mode: str,
    context_summary: str,
    risk_sentinels: list[Any],
    module: Any,
) -> str:
    return fingerprints.digest(
        {
            "input_signature": input_signature(
                pr, files, diff, deep_context_block, review_mode, context_summary
            ),
            "config_sha256": fingerprints.digest(fingerprints.config_snapshot(config)),
            "risk_sha256": _risk_digest(module, risk_sentinels),
        }
    )


__all__ = [
    "broad_prompt_key",
    "build_context_runtime",
    "file_surface_signature",
    "input_signature",
    "matches_file_surface",
    "per_file_prompt_key",
    "public_payload",
]
