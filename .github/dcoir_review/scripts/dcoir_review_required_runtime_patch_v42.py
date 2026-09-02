"""Architecture-B semantic ledger and context-fingerprint foundation (v42).

This terminal overlay is intentionally semantic-behavior preserving: it does not
change prompts, model/provider selection, routing, escalation, verification, or
repair. It records one deterministic review-context package for later reuse and
benchmark work while leaving semantic-result reuse disabled.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from dcoir_review_required_runtime_patch_v41_review_state import (
    ARCHITECTURE_CONTRACT,
    PROVENANCE_PREFIX,
)
from dcoir_review_required_runtime_patch_v41_scope import SCOPE_CACHE_ATTR

VERSION = "v42"
SEMANTIC_LEDGER_CONTRACT = "architecture-b-semantic-ledger-v1"
SEMANTIC_LEDGER_MARKER_PREFIX = "DCOIR semantic ledger: "
SEMANTIC_LEDGER_ATTR = "_dcoir_v42_semantic_review_ledger"

_HYBRID_STORAGE = "_dcoir_v42_original_hybrid_first_pass"
_APPEND_CONTEXT_STORAGE = "_dcoir_v42_original_append_context_to_review_body"
_DEBUG_JSON_STORAGE = "_dcoir_v42_original_write_debug_json_artifact_safely"
_LAST_LEDGER: dict[str, Any] = {}


def _normalized(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _normalized(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalized(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_normalized(item) for item in value]
        return sorted(
            items,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        )
    return str(value)


def _digest(value: Any) -> str:
    payload = json.dumps(
        _normalized(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _text_digest(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _config_snapshot(config: Any) -> dict[str, Any]:
    try:
        raw = vars(config)
    except TypeError:
        raw = {}
    return {
        str(key): _normalized(value)
        for key, value in sorted(raw.items())
        if not str(key).startswith("_") and not callable(value)
    }


def _valid_blob_sha(value: str) -> bool:
    candidate = value.strip().lower()
    return len(candidate) in {40, 64} and all(
        character in "0123456789abcdef" for character in candidate
    )


def _semantic_context_summary(value: Any) -> str:
    """Remove v41's per-run publication receipt from semantic identity.

    v41 appends an HMAC provenance marker containing GITHUB_RUN_ID to the context
    summary. That receipt is required for trusted review-state publication, but it
    is transport/provenance metadata rather than semantic PR context. The current
    reviewer still receives the untouched summary; v42 only excludes the receipt
    from the reusable canonical fingerprint and separately records the exact raw
    runtime-context fingerprint.
    """

    text = str(value or "").strip()
    marker_index = text.rfind(PROVENANCE_PREFIX)
    if marker_index < 0:
        return text
    return text[:marker_index].rstrip(" ;")


def _file_record(
    item: dict[str, Any],
    *,
    schema_sha256: str,
    config_sha256: str,
    dependency_sha256: str,
) -> dict[str, Any]:
    path = str(item.get("filename", "") or "").replace("\\", "/").strip()
    status = str(item.get("status", "") or "").strip().lower()
    blob_sha = str(item.get("sha", "") or "").strip().lower()
    deleted = status in {"removed", "deleted"}
    content_identity_available = deleted or _valid_blob_sha(blob_sha)
    content_identity = (
        f"deleted:{path}"
        if deleted
        else (f"github-blob:{blob_sha}" if _valid_blob_sha(blob_sha) else "")
    )
    base_record = {
        "path": path,
        "previous_path": str(item.get("previous_filename", "") or "")
        .replace("\\", "/")
        .strip(),
        "status": status,
        "blob_sha": blob_sha if _valid_blob_sha(blob_sha) else "",
        "content_identity_available": content_identity_available,
        "content_identity": content_identity,
        "additions": item.get("additions"),
        "deletions": item.get("deletions"),
        "changes": item.get("changes"),
        "patch_sha256": _text_digest(item.get("patch", ""))
        if item.get("patch")
        else "",
    }
    record = dict(base_record)
    record["surface_fingerprint"] = _digest(base_record)
    record["prospective_reuse_key"] = (
        _digest(
            {
                "contract": SEMANTIC_LEDGER_CONTRACT,
                "architecture": ARCHITECTURE_CONTRACT,
                "schema_sha256": schema_sha256,
                "config_sha256": config_sha256,
                "dependency_sha256": dependency_sha256,
                "path": path,
                "content_identity": content_identity,
            }
        )
        if content_identity_available
        else ""
    )
    # v42 defines and measures the key but deliberately does not consume prior
    # semantic results. Dependency-aware invalidation is not enabled yet.
    record["reuse_allowed"] = False
    return record


def _line_index_digest(line_index: dict[tuple[str, int], int]) -> str:
    rows = [
        [str(path), int(line), int(position)]
        for (path, line), position in sorted(
            line_index.items(), key=lambda pair: (str(pair[0][0]), int(pair[0][1]))
        )
    ]
    return _digest(rows)


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

    config_snapshot = _config_snapshot(config)
    config_sha256 = _digest(config_snapshot)
    schema_sha256 = _digest(schema)
    dependency_context = {
        "contract": "dependency-context-v1",
        "mode": "not-expanded-v42",
        "expanded_paths": [],
    }
    dependency_sha256 = _digest(dependency_context)
    file_records = sorted(
        (
            _file_record(
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
        "title_sha256": _text_digest(
            pr.get("title", "") if isinstance(pr, dict) else ""
        ),
        "body_sha256": _text_digest(pr_body),
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
        "diff_sha256": _text_digest(diff),
        "diff_chars": len(str(diff or "")),
    }

    raw_context_summary = str(context_summary or "").strip()
    semantic_context_summary = _semantic_context_summary(raw_context_summary)
    canonical_context_inputs = {
        "deep_context_sha256": _text_digest(deep_context_block),
        "deep_context_chars": len(str(deep_context_block or "")),
        "semantic_context_summary_sha256": _text_digest(semantic_context_summary),
        "semantic_context_summary_chars": len(semantic_context_summary),
        "risk_sentinel_count": len(risk_sentinels),
        "risk_sentinel_digest": risk_digest,
        "line_index_entries": len(line_index),
        "line_index_sha256": _line_index_digest(line_index),
    }
    runtime_context_observation = {
        "raw_context_summary_sha256": _text_digest(raw_context_summary),
        "raw_context_summary_chars": len(raw_context_summary),
        "transient_provenance_present": raw_context_summary
        != semantic_context_summary,
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
    context_fingerprint = _digest(
        {**fingerprint_base, "context_inputs": canonical_context_inputs}
    )
    runtime_context_fingerprint = _digest(
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


def semantic_review_ledger_for_client(gh: Any) -> dict[str, Any]:
    value = getattr(gh, SEMANTIC_LEDGER_ATTR, {})
    return copy.deepcopy(value) if isinstance(value, dict) else {}


def _ledger_marker(ledger: dict[str, Any]) -> str:
    telemetry = (
        ledger.get("telemetry", {})
        if isinstance(ledger.get("telemetry"), dict)
        else {}
    )
    reuse = ledger.get("reuse", {}) if isinstance(ledger.get("reuse"), dict) else {}
    return (
        f"{SEMANTIC_LEDGER_MARKER_PREFIX}contract={SEMANTIC_LEDGER_CONTRACT}; "
        f"fingerprint={str(ledger.get('context_fingerprint', '') or '')}; "
        f"reviewed-files={int(telemetry.get('reviewed_file_count', 0) or 0)}; "
        f"reused-files={int(telemetry.get('reused_file_count', 0) or 0)}; "
        f"recomputed-files={int(telemetry.get('recomputed_file_count', 0) or 0)}; "
        f"dependency-expanded-files={int(telemetry.get('dependency_expanded_file_count', 0) or 0)}; "
        f"reuse-enabled={str(bool(reuse.get('enabled', False))).lower()}"
    )


def apply_pareto_context_module(module: Any) -> None:
    """Attach behavior-preserving Architecture-B semantic-ledger instrumentation."""

    global _LAST_LEDGER
    _LAST_LEDGER = {}

    original_hybrid = getattr(module, _HYBRID_STORAGE, None)
    if original_hybrid is None:
        original_hybrid = getattr(module, "openrouter_review_with_hybrid_first_pass", None)
        if not callable(original_hybrid):
            raise RuntimeError("DCOIR v42 could not locate the active hybrid review function")
        setattr(module, _HYBRID_STORAGE, original_hybrid)

    original_append_context = getattr(module, _APPEND_CONTEXT_STORAGE, None)
    if original_append_context is None:
        original_append_context = getattr(module, "append_context_to_review_body", None)
        if not callable(original_append_context):
            raise RuntimeError("DCOIR v42 could not locate append_context_to_review_body")
        setattr(module, _APPEND_CONTEXT_STORAGE, original_append_context)

    original_debug_json = getattr(module, _DEBUG_JSON_STORAGE, None)
    if original_debug_json is None:
        original_debug_json = module.hardened.write_debug_json_artifact_safely
        setattr(module, _DEBUG_JSON_STORAGE, original_debug_json)

    def write_debug_json_artifact_safely(
        config: Any, relative_path: str, value: Any
    ) -> None:
        if (
            relative_path == "metadata/review-context.json"
            and isinstance(value, dict)
            and _LAST_LEDGER
        ):
            enriched = dict(value)
            telemetry = _LAST_LEDGER.get("telemetry", {})
            enriched.update(
                {
                    "semantic_ledger_contract": SEMANTIC_LEDGER_CONTRACT,
                    "semantic_context_fingerprint": str(
                        _LAST_LEDGER.get("context_fingerprint", "") or ""
                    ),
                    "semantic_runtime_context_fingerprint": str(
                        _LAST_LEDGER.get("runtime_context_fingerprint", "") or ""
                    ),
                    "semantic_reviewed_file_count": int(
                        telemetry.get("reviewed_file_count", 0) or 0
                    ),
                    "semantic_reused_file_count": int(
                        telemetry.get("reused_file_count", 0) or 0
                    ),
                    "semantic_recomputed_file_count": int(
                        telemetry.get("recomputed_file_count", 0) or 0
                    ),
                    "semantic_dependency_expanded_file_count": int(
                        telemetry.get("dependency_expanded_file_count", 0) or 0
                    ),
                    "semantic_invalidation_reason": str(
                        telemetry.get("invalidation_reason", "") or ""
                    ),
                }
            )
            value = enriched
        original_debug_json(config, relative_path, value)

    def openrouter_review_with_hybrid_first_pass(
        pr,
        files,
        diff,
        schema,
        config,
        reporter,
        risk_sentinels,
        line_index,
        deep_context_block,
        review_mode,
        context_summary,
        gh,
    ):
        global _LAST_LEDGER
        ledger = build_semantic_review_ledger(
            module,
            pr,
            files,
            diff,
            schema,
            config,
            risk_sentinels,
            line_index,
            deep_context_block,
            review_mode,
            context_summary,
            gh,
        )
        _LAST_LEDGER = ledger
        setattr(gh, SEMANTIC_LEDGER_ATTR, copy.deepcopy(ledger))

        reporter_update = getattr(reporter, "update", None)
        if callable(reporter_update):
            reporter_update(
                "semantic-ledger",
                (
                    f"prepared {ledger['context_fingerprint'][:12]}: "
                    f"reviewed={ledger['telemetry']['reviewed_file_count']} reused=0 "
                    f"recomputed={ledger['telemetry']['recomputed_file_count']} dependencies=0"
                ),
            )
        module.hardened.write_debug_json_artifact_safely(
            config,
            "metadata/semantic-review-ledger.json",
            copy.deepcopy(ledger),
        )

        try:
            result, model_used, service_tier = original_hybrid(
                pr,
                files,
                diff,
                schema,
                config,
                reporter,
                risk_sentinels,
                line_index,
                deep_context_block,
                review_mode,
                context_summary,
                gh,
            )
        except Exception as exc:
            ledger["telemetry"]["outcome"] = "failed"
            ledger["telemetry"]["failure_type"] = type(exc).__name__
            setattr(gh, SEMANTIC_LEDGER_ATTR, copy.deepcopy(ledger))
            module.hardened.write_debug_json_artifact_safely(
                config,
                "metadata/semantic-review-ledger.json",
                copy.deepcopy(ledger),
            )
            raise

        findings_fn = getattr(module.hardened, "result_findings", None)
        finding_count = None
        if callable(findings_fn):
            try:
                finding_count = len(findings_fn(result))
            except Exception:
                finding_count = None
        ledger["telemetry"].update(
            {
                "outcome": "completed",
                "result_finding_count": finding_count,
                "model_used": str(model_used or ""),
                "service_tier": str(service_tier or ""),
            }
        )
        _LAST_LEDGER = ledger
        setattr(gh, SEMANTIC_LEDGER_ATTR, copy.deepcopy(ledger))
        module.hardened.write_debug_json_artifact_safely(
            config,
            "metadata/semantic-review-ledger.json",
            copy.deepcopy(ledger),
        )
        return result, model_used, service_tier

    def append_context_to_review_body(
        body: str, review_mode: str, context_summary: str, config: Any
    ) -> str:
        rendered = original_append_context(
            body, review_mode, context_summary, config
        )
        if not _LAST_LEDGER:
            return rendered
        marker = _ledger_marker(_LAST_LEDGER)
        if marker in rendered:
            return rendered
        augmented = f"{rendered.rstrip()}\n\n{marker}" if rendered.strip() else marker
        github_safe_body = getattr(
            getattr(module, "base", None), "github_safe_body", None
        )
        if callable(github_safe_body):
            return github_safe_body(augmented)
        return augmented

    module.hardened.write_debug_json_artifact_safely = write_debug_json_artifact_safely
    module.openrouter_review_with_hybrid_first_pass = openrouter_review_with_hybrid_first_pass
    module.append_context_to_review_body = append_context_to_review_body
    module.DCOIR_SEMANTIC_LEDGER_CONTRACT = SEMANTIC_LEDGER_CONTRACT
    module.DCOIR_SEMANTIC_LEDGER_MARKER_PREFIX = SEMANTIC_LEDGER_MARKER_PREFIX
    module.semantic_review_ledger_for_client = semantic_review_ledger_for_client
