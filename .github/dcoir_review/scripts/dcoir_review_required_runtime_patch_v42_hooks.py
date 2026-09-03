"""Runtime wrapper instrumentation for the DCOIR Review v42 semantic ledger."""

from __future__ import annotations

import copy
from typing import Any

from dcoir_review_required_runtime_patch_v42_contract import (
    SEMANTIC_LEDGER_ATTR,
    SEMANTIC_LEDGER_CONTRACT,
    SEMANTIC_LEDGER_MARKER_PREFIX,
)
from dcoir_review_required_runtime_patch_v42_ledger import (
    build_semantic_review_ledger,
)

_HYBRID_STORAGE = "_dcoir_v42_original_hybrid_first_pass"
_APPEND_CONTEXT_STORAGE = "_dcoir_v42_original_append_context_to_review_body"
_DEBUG_JSON_STORAGE = "_dcoir_v42_original_write_debug_json_artifact_safely"
_LAST_LEDGER: dict[str, Any] = {}
_LAST_REVIEW_CONTEXT: dict[str, Any] | None = None


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

    global _LAST_LEDGER, _LAST_REVIEW_CONTEXT
    _LAST_LEDGER = {}
    _LAST_REVIEW_CONTEXT = None

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
        global _LAST_REVIEW_CONTEXT
        if (
            relative_path == "metadata/review-context.json"
            and isinstance(value, dict)
        ):
            if not _LAST_LEDGER:
                _LAST_REVIEW_CONTEXT = copy.deepcopy(value)
            else:
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
        if _LAST_REVIEW_CONTEXT is not None:
            module.hardened.write_debug_json_artifact_safely(
                config,
                "metadata/review-context.json",
                copy.deepcopy(_LAST_REVIEW_CONTEXT),
            )

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
        rendered = original_append_context(body, review_mode, context_summary, config)
        if not _LAST_LEDGER:
            return rendered
        marker = _ledger_marker(_LAST_LEDGER)
        if marker in rendered:
            return rendered
        github_safe_body = getattr(
            getattr(module, "base", None), "github_safe_body", None
        )
        if callable(github_safe_body):
            safe_limit = max(0, 65000 - len(marker) - 200)
            safe_rendered = github_safe_body(rendered.rstrip(), limit=safe_limit)
            if not safe_rendered.strip():
                return marker
            return f"{safe_rendered.rstrip()}\n\n{marker}"
        return f"{rendered.rstrip()}\n\n{marker}" if rendered.strip() else marker

    module.hardened.write_debug_json_artifact_safely = write_debug_json_artifact_safely
    module.openrouter_review_with_hybrid_first_pass = (
        openrouter_review_with_hybrid_first_pass
    )
    module.append_context_to_review_body = append_context_to_review_body
    module.DCOIR_SEMANTIC_LEDGER_CONTRACT = SEMANTIC_LEDGER_CONTRACT
    module.DCOIR_SEMANTIC_LEDGER_MARKER_PREFIX = SEMANTIC_LEDGER_MARKER_PREFIX
    module.semantic_review_ledger_for_client = semantic_review_ledger_for_client


__all__ = ["apply_pareto_context_module", "semantic_review_ledger_for_client"]
