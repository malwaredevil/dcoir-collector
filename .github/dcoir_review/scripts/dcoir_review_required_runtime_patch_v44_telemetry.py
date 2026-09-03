"""Architecture-B v44 candidate-escalation telemetry helpers."""

from __future__ import annotations

from typing import Any

import dcoir_review_required_runtime_patch_v42_hooks as v42_hooks
import dcoir_review_required_runtime_patch_v44_scope as scope


def _candidate_decisions(
    module: Any,
    result: dict[str, Any],
    plan: dict[str, Any],
) -> list[dict[str, Any]]:
    escalated = [
        tuple(item)
        for item in plan.get("escalated_candidate_keys", [])
        if isinstance(item, list) and len(item) == 3
    ]
    mode = str(plan.get("mode", "") or "")
    reasons = list(plan.get("reasons", []))
    decisions = [
        {"key": list(key), "mode": mode, "reasons": reasons}
        for key in escalated
    ]
    seen = set(escalated)
    for item in scope.dedupe_exact_findings(module.hardened.result_findings(result)):
        key = scope.finding_key(item)
        if key in seen:
            continue
        broadly_escalated = mode in {"broader-context", "full-deep"}
        decisions.append(
            {
                "key": list(key),
                "mode": mode if broadly_escalated else "none",
                "reasons": reasons
                if broadly_escalated
                else ["not-selected-for-escalation"],
            }
        )
    return decisions


def apply(
    module: Any,
    gh: Any,
    config: Any,
    result: dict[str, Any],
    plan: dict[str, Any],
    context_scope: str,
    challenger_calls: int,
    adjudicator_calls: int,
    widened: bool,
) -> dict[str, Any]:
    metadata = {
        "contract": scope.CONTRACT,
        "mode": plan.get("mode", ""),
        "reasons": list(plan.get("reasons", [])),
        "candidate_count": int(plan.get("candidate_count", 0) or 0),
        "escalated_candidate_count": len(plan.get("escalated_candidate_keys", [])),
        "candidate_decisions": _candidate_decisions(module, result, plan),
        "selected_paths": list(plan.get("selected_paths", [])),
        "context_scope": context_scope,
        "challenger_call_count": challenger_calls,
        "adjudicator_call_count": adjudicator_calls,
        "widened": widened,
        "explicit_deep_forced": plan.get("mode") == "full-deep",
    }
    final = dict(result)
    final["_candidate_escalation"] = metadata
    ledger = getattr(gh, v42_hooks.SEMANTIC_LEDGER_ATTR, None)
    if isinstance(ledger, dict):
        ledger["escalation"] = metadata
        ledger_telemetry = ledger.setdefault("telemetry", {})
        ledger_telemetry.update(
            {
                "candidate_count": metadata["candidate_count"],
                "escalated_candidate_count": metadata["escalated_candidate_count"],
                "challenger_call_count": challenger_calls,
                "adjudicator_call_count": adjudicator_calls,
                "candidate_escalation_mode": metadata["mode"],
                "candidate_escalation_context_scope": context_scope,
                "candidate_escalation_widened": widened,
                "explicit_deep_forced": metadata["explicit_deep_forced"],
            }
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
    module.hardened.write_debug_json_artifact_safely(
        config, "metadata/v44-candidate-escalation.json", metadata
    )
    return final
