"""Canonical semantic-review ledger builder for DCOIR Review v42."""

from __future__ import annotations

from typing import Any

from dcoir_review_required_runtime_patch_v41_review_state import ARCHITECTURE_CONTRACT
from dcoir_review_required_runtime_patch_v41_scope import SCOPE_CACHE_ATTR
from dcoir_review_required_runtime_patch_v42_contract import (
    SEMANTIC_LEDGER_CONTRACT,
    VERSION,
)
from dcoir_review_required_runtime_patch_v42_fingerprints import (
    config_snapshot,
    digest,
    file_record,
    line_index_digest,
    semantic_context_summary,
    text_digest,
)


def build_semantic_review_ledger(
    module: Any,
    pr: dict[str, Any],
    files: list[dict[str, Any]],
    diff: str,
    schema: dict[str, Any],
    config: Any,
    risk_sentinels: list[Any],
    line_index: dict[tuple[str, int], int],
    deep_context_block: str,
    review_mode: str,
    context_summary: str,
    gh: Any,
) -> dict[str, Any]:
    """Build one canonical, deterministic package describing semantic input."""

    scope = getattr(gh, SCOPE_CACHE_ATTR, {})
    if not isinstance(scope, dict):
        scope = {}

    config_sha256 = digest(config_snapshot(config))
    schema_sha256 = digest(schema)
    dependency_context = {
        "contract": "dependency-context-v1",
        "mode": "not-expanded-v42",
        "expanded_paths": [],
    }
    dependency_sha256 = digest(dependency_context)
    file_records = sorted(
        (
            file_record(
                item,
                schema_sha256=schema_sha256,
                config_sha256=config_sha256,
                dependency_sha256=dependency_sha256,
            )
            for item in files
            if isinstance(item, dict)
        ),
        key=lambda record: (
            str(record.get("path", "") or "").replace("\\", "/"),
            str(record.get("status", "") or ""),
            str(record.get("blob_sha", "") or ""),
            str(record.get("content_identity", "") or ""),
            str(record.get("previous_path", "") or ""),
        ),
    )

    risk_digest_fn = getattr(
        getattr(module, "hardened", None), "risk_sentinel_digest", None
    )
    risk_digest = str(
        risk_digest_fn(risk_sentinels)
        if callable(risk_digest_fn) and risk_sentinels
        else ""
    )
    pr_body = str(pr.get("body", "") or "") if isinstance(pr, dict) else ""
    pr_base = pr.get("base", {}) if isinstance(pr, dict) else {}
    pr_head = pr.get("head", {}) if isinstance(pr, dict) else {}
    pr_context = {
        "number": int(pr.get("number", 0) or 0) if isinstance(pr, dict) else 0,
        "title_sha256": text_digest(
            pr.get("title", "") if isinstance(pr, dict) else ""
        ),
        "body_sha256": text_digest(pr_body),
        "base_ref": str(pr_base.get("ref", "") or "")
        if isinstance(pr_base, dict)
        else "",
        "base_sha": str(pr_base.get("sha", "") or "").lower()
        if isinstance(pr_base, dict)
        else "",
        "head_ref": str(pr_head.get("ref", "") or "")
        if isinstance(pr_head, dict)
        else "",
        "head_sha": str(pr_head.get("sha", "") or "").lower()
        if isinstance(pr_head, dict)
        else "",
    }
    review_surface = {
        "scope_source": str(scope.get("source", "") or ""),
        "prior_reviewed_head_sha": str(
            scope.get("prior_reviewed_head_sha", "") or ""
        ),
        "current_head_sha": str(
            scope.get("current_head_sha", "") or pr_context["head_sha"]
        ),
        "prior_reviewed_base_sha": str(
            scope.get("prior_reviewed_base_sha", "") or ""
        ),
        "current_base_sha": str(
            scope.get("current_base_sha", "") or pr_context["base_sha"]
        ),
        "compare_status": str(scope.get("compare_status", "") or ""),
        "fallback_reason": str(scope.get("fallback_reason", "") or ""),
        "review_mode": str(review_mode or ""),
        "files": file_records,
        "diff_sha256": text_digest(diff),
        "diff_chars": len(str(diff or "")),
    }

    raw_context_summary = str(context_summary or "").strip()
    canonical_summary = semantic_context_summary(raw_context_summary)
    canonical_context_inputs = {
        "deep_context_sha256": text_digest(deep_context_block),
        "deep_context_chars": len(str(deep_context_block or "")),
        "semantic_context_summary_sha256": text_digest(canonical_summary),
        "semantic_context_summary_chars": len(canonical_summary),
        "risk_sentinel_count": len(risk_sentinels),
        "risk_sentinel_digest": risk_digest,
        "line_index_entries": len(line_index),
        "line_index_sha256": line_index_digest(line_index),
    }
    runtime_context_observation = {
        "raw_context_summary_sha256": text_digest(raw_context_summary),
        "raw_context_summary_chars": len(raw_context_summary),
        "transient_provenance_present": raw_context_summary != canonical_summary,
    }
    fingerprint_base = {
        "semantic_ledger_contract": SEMANTIC_LEDGER_CONTRACT,
        "architecture_contract": ARCHITECTURE_CONTRACT,
        "runtime_overlay": VERSION,
        "pr_context": pr_context,
        "review_surface": review_surface,
        "schema_sha256": schema_sha256,
        "config_sha256": config_sha256,
        "dependency_sha256": dependency_sha256,
    }
    context_fingerprint = digest(
        {**fingerprint_base, "context_inputs": canonical_context_inputs}
    )
    runtime_context_fingerprint = digest(
        {
            **fingerprint_base,
            "context_inputs": canonical_context_inputs,
            "runtime_context_observation": runtime_context_observation,
        }
    )

    missing_content_identity = [
        item["path"]
        for item in file_records
        if not bool(item.get("content_identity_available"))
    ]
    return {
        "semantic_ledger_contract": SEMANTIC_LEDGER_CONTRACT,
        "architecture_contract": ARCHITECTURE_CONTRACT,
        "runtime_overlay": VERSION,
        "context_fingerprint": context_fingerprint,
        "runtime_context_fingerprint": runtime_context_fingerprint,
        "schema_sha256": schema_sha256,
        "config_sha256": config_sha256,
        "dependency_context": dependency_context,
        "dependency_sha256": dependency_sha256,
        "pr_context": pr_context,
        "review_surface": review_surface,
        "context_inputs": canonical_context_inputs,
        "runtime_context_observation": runtime_context_observation,
        "reuse": {
            "enabled": False,
            "eligible": False,
            "reason": "semantic-result reuse is intentionally disabled in the v42 foundation",
            "missing_content_identity_paths": missing_content_identity,
        },
        "telemetry": {
            "reviewed_file_count": len(file_records),
            "reused_file_count": 0,
            "recomputed_file_count": len(file_records),
            "dependency_expanded_file_count": 0,
            "invalidation_reason": "semantic-result reuse not enabled in v42",
            "outcome": "prepared",
            "result_finding_count": None,
            "model_used": "",
            "service_tier": "",
        },
    }


__all__ = ["build_semantic_review_ledger"]
