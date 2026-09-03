"""Architecture-B v43 terminal overlay for conservative semantic-result reuse."""

from __future__ import annotations

import os
import threading
from typing import Any

import dcoir_review_required_runtime_patch_v42_hooks as v42_hooks
import dcoir_review_required_runtime_patch_v43_reuse as reuse

VERSION = "v43"
_STATE_ATTR = "_dcoir_v43_reuse_state"
_APPLIED_ATTR = "_dcoir_v43_applied"


def _new_state(module: Any, gh: Any, pr: dict[str, Any]) -> dict[str, Any]:
    manifest, prior_head, load_reason = reuse.trusted_prior_manifest(module, gh, pr)
    records: dict[str, Any] = {}
    if manifest:
        for record in manifest.get("records", []):
            if isinstance(record, dict):
                path = str(record.get("path", "") or "").strip()
                if path and path not in records:
                    records[path] = record
    return {
        "prior_records": records,
        "trusted_prior_head": prior_head,
        "load_reason": load_reason,
        "decisions": {},
        "records": {},
        "lock": threading.Lock(),
    }


def _record(state: dict[str, Any], path: str, decision: dict[str, Any], record: dict[str, Any]) -> None:
    with state["lock"]:
        state["decisions"][path] = decision
        state["records"][path] = record


def _ledger_file_records(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    review_surface = ledger.get("review_surface")
    if isinstance(review_surface, dict):
        files = review_surface.get("files")
        if isinstance(files, list):
            return [item for item in files if isinstance(item, dict)]
    legacy = ledger.get("file_records")
    if isinstance(legacy, list):
        return [item for item in legacy if isinstance(item, dict)]
    return []


def _apply_ledger_telemetry(module: Any, gh: Any, config: Any, state: dict[str, Any]) -> None:
    ledger = getattr(gh, v42_hooks.SEMANTIC_LEDGER_ATTR, None)
    if not isinstance(ledger, dict):
        return
    decisions = state["decisions"]
    reused = sum(1 for item in decisions.values() if item.get("decision") == "reused")
    recomputed = sum(1 for item in decisions.values() if item.get("decision") == "recomputed")
    ledger["reuse"] = {
        "enabled": True,
        "eligible": reused > 0,
        "reason": "reused-eligible-results" if reused else state["load_reason"],
        "contract": reuse.REUSE_CONTRACT,
        "dependency_contract": reuse.DEPENDENCY_CONTRACT,
        "dependency_mode": reuse.DEPENDENCY_MODE,
    }
    telemetry = ledger.setdefault("telemetry", {})
    telemetry["reviewed_file_count"] = len(decisions)
    telemetry["reused_file_count"] = reused
    telemetry["recomputed_file_count"] = recomputed
    telemetry["reuse_invalidation_reason"] = "" if reused else state["load_reason"]
    ledger_decisions = [decisions[path] for path in sorted(decisions)]
    for file_record in _ledger_file_records(ledger):
        path = str(file_record.get("path", "") or "")
        decision = decisions.get(path)
        if decision:
            file_record["reuse_allowed"] = decision.get("decision") == "reused"
            file_record["semantic_result_reuse_key"] = decision.get("reuse_key", "")
            file_record["reuse_decision"] = decision.get("decision", "")
            file_record["reuse_reason"] = decision.get("reason", "")
        elif str(file_record.get("status", "") or "").lower() in {"removed", "deleted"}:
            file_record["reuse_allowed"] = False
            file_record["reuse_decision"] = "not-applicable"
            file_record["reuse_reason"] = "deleted-file"
            ledger_decisions.append(
                {
                    "path": path,
                    "decision": "not-applicable",
                    "reason": "deleted-file",
                    "reuse_key": "",
                }
            )
    ledger["reuse_decisions"] = sorted(
        ledger_decisions, key=lambda item: str(item.get("path", ""))
    )
    setattr(gh, v42_hooks.SEMANTIC_LEDGER_ATTR, ledger)
    v42_hooks._LAST_LEDGER = ledger
    module.hardened.write_debug_json_artifact_safely(
        config, "metadata/semantic-review-ledger.json", ledger
    )
    context = v42_hooks._LAST_REVIEW_CONTEXT
    if isinstance(context, dict):
        enriched = v42_hooks._review_context_payload_with_ledger(context, ledger)
        v42_hooks._LAST_REVIEW_CONTEXT = enriched
        module.hardened.write_debug_json_artifact_safely(
            config, "metadata/review-context.json", enriched
        )


def _write_manifest(module: Any, config: Any, pr: dict[str, Any], state: dict[str, Any]) -> bool:
    head = str(pr.get("head", {}).get("sha", "") or "").strip().lower()
    manifest = {
        "contract": reuse.REUSE_CONTRACT,
        "runtime_version": VERSION,
        "outcome": "complete",
        "reviewed_head": head,
        "workflow_run_id": str(os.environ.get("GITHUB_RUN_ID", "") or ""),
        "dependency_contract": reuse.DEPENDENCY_CONTRACT,
        "dependency_mode": reuse.DEPENDENCY_MODE,
        "records": [state["records"][path] for path in sorted(state["records"])],
    }
    return reuse.persist_manifest(module, config, manifest)


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, _APPLIED_ATTR, False):
        return
    original_hybrid = getattr(module, "openrouter_review_with_hybrid_first_pass", None)
    original_single = getattr(module, "review_single_file_context", None)
    if not callable(original_hybrid) or not callable(original_single):
        raise RuntimeError("DCOIR v43 could not locate active semantic review functions")

    def review_single_file_context(
        index, context, pr, diff, schema, config, risk_sentinels, review_mode
    ):
        state = getattr(module, _STATE_ATTR, None)
        if not isinstance(state, dict):
            return original_single(
                index, context, pr, diff, schema, config, risk_sentinels, review_mode
            )
        path = str(context.get("path", "") or "").strip()
        material = reuse.reuse_material(
            module, context, pr, diff, schema, config, risk_sentinels, review_mode
        )
        prior = state["prior_records"].get(path)
        eligible, reason = reuse.evaluate_reuse_candidate(
            material, prior, state["trusted_prior_head"]
        )
        current_head = str(pr.get("head", {}).get("sha", "") or "").strip().lower()
        if eligible:
            result = {
                "path": path,
                "prompt_chars": int(prior.get("prompt_chars") or material["prompt_chars"]),
                "result": prior["result"],
                "model_used": str(
                    prior.get("model_used", "") or getattr(config, "model", "")
                ),
                "service_tier": str(prior.get("service_tier", "") or ""),
            }
            record = {
                **material,
                **result,
                "contract": reuse.REUSE_CONTRACT,
                "outcome": "complete",
                "origin_reviewed_head": str(
                    prior.get("origin_reviewed_head", "") or state["trusted_prior_head"]
                ),
                "carried_forward_head": current_head,
            }
            _record(
                state,
                path,
                {
                    "path": path,
                    "decision": "reused",
                    "reason": reason,
                    "reuse_key": material["reuse_key"],
                },
                record,
            )
            return result

        result = original_single(
            index, context, pr, diff, schema, config, risk_sentinels, review_mode
        )
        record = {
            **material,
            **result,
            "contract": reuse.REUSE_CONTRACT,
            "outcome": "complete",
            "origin_reviewed_head": current_head,
            "carried_forward_head": current_head,
        }
        _record(
            state,
            path,
            {
                "path": path,
                "decision": "recomputed",
                "reason": reason,
                "reuse_key": material["reuse_key"],
            },
            record,
        )
        return result

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
        state = _new_state(module, gh, pr)
        setattr(module, _STATE_ATTR, state)
        result = original_hybrid(
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
        _apply_ledger_telemetry(module, gh, config, state)
        manifest_persisted = _write_manifest(module, config, pr, state)
        reused = sum(
            1 for item in state["decisions"].values() if item.get("decision") == "reused"
        )
        recomputed = sum(
            1
            for item in state["decisions"].values()
            if item.get("decision") == "recomputed"
        )
        reporter.update(
            "semantic-reuse",
            (
                f"reused={reused}; recomputed={recomputed}; prior={state['load_reason']}; "
                f"state={'persisted' if manifest_persisted else 'not-persisted'}"
            ),
        )
        return result

    module.review_single_file_context = review_single_file_context
    module.openrouter_review_with_hybrid_first_pass = openrouter_review_with_hybrid_first_pass
    setattr(module, _APPLIED_ATTR, True)
