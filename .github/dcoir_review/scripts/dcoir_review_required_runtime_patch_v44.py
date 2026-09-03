"""Architecture-B v44 terminal overlay for candidate-scoped semantic escalation."""

from __future__ import annotations

import copy
from typing import Any

import dcoir_review_required_runtime_patch_v42_hooks as v42_hooks
import dcoir_review_required_runtime_patch_v44_execution as execution
import dcoir_review_required_runtime_patch_v44_scope as scope

VERSION = "v44"
_APPLIED_ATTR = "_dcoir_v44_applied"
_CONFIG_STORAGE = "_dcoir_v44_original_load_pareto_context_config"
_HYBRID_STORAGE = "_dcoir_v44_original_hybrid_first_pass"


def _positive_int(value: Any, fallback: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return fallback


def _unit_float(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if 0.0 <= parsed <= 1.0 else fallback


def _patch_config_loader(module: Any) -> None:
    original = getattr(module, _CONFIG_STORAGE, None)
    if original is None:
        original = getattr(module, "load_pareto_context_config", None)
        if callable(original):
            setattr(module, _CONFIG_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v44 could not locate load_pareto_context_config")

    def load_pareto_context_config(path: str):
        config = original(path)
        data = module.hardened.parse_yaml_like_data(path)
        config.candidate_scoped_escalation_review = module.hardened.bool_value(
            data, "candidate_scoped_escalation_review", True
        )
        config.candidate_escalation_confidence_margin = _unit_float(
            data.get("candidate_escalation_confidence_margin", scope.DEFAULT_CONFIDENCE_MARGIN),
            scope.DEFAULT_CONFIDENCE_MARGIN,
        )
        config.candidate_escalation_max_paths = _positive_int(
            data.get("candidate_escalation_max_paths", scope.DEFAULT_MAX_PATHS),
            scope.DEFAULT_MAX_PATHS,
        )
        config.candidate_escalation_file_chars = _positive_int(
            data.get("candidate_escalation_file_chars", scope.DEFAULT_FILE_CHARS),
            scope.DEFAULT_FILE_CHARS,
        )
        config.candidate_escalation_total_context_chars = _positive_int(
            data.get(
                "candidate_escalation_total_context_chars",
                scope.DEFAULT_TOTAL_CONTEXT_CHARS,
            ),
            scope.DEFAULT_TOTAL_CONTEXT_CHARS,
        )
        return config

    module.load_pareto_context_config = load_pareto_context_config


def _merge_scoped_result(
    module: Any,
    primary: dict[str, Any],
    passthrough: list[dict[str, Any]],
    adjudicated: dict[str, Any],
) -> dict[str, Any]:
    final = dict(primary)
    combined = passthrough + [
        item
        for item in module.hardened.result_findings(adjudicated)
        if isinstance(item, dict)
    ]
    final["findings"] = scope.dedupe_exact_findings(combined)
    final["_semantic_adjudication_attempted"] = True
    final["_semantic_adjudication_model"] = adjudicated.get(
        "_semantic_adjudication_model", ""
    )
    final["_semantic_adjudication_input_candidates"] = adjudicated.get(
        "_semantic_adjudication_input_candidates", 0
    )
    final["_semantic_adjudication_output_findings"] = len(final["findings"])
    final["_semantic_adjudication_context_scope"] = "candidate-scoped"
    return final


def _apply_escalation_metadata(
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
        "selected_paths": list(plan.get("selected_paths", [])),
        "context_scope": context_scope,
        "challenger_call_count": challenger_calls,
        "adjudicator_call_count": adjudicator_calls,
        "widened": widened,
    }
    final = dict(result)
    final["_candidate_escalation"] = metadata
    ledger = getattr(gh, v42_hooks.SEMANTIC_LEDGER_ATTR, None)
    if isinstance(ledger, dict):
        ledger["escalation"] = metadata
        telemetry = ledger.setdefault("telemetry", {})
        telemetry["candidate_count"] = metadata["candidate_count"]
        telemetry["escalated_candidate_count"] = metadata[
            "escalated_candidate_count"
        ]
        telemetry["challenger_call_count"] = challenger_calls
        telemetry["adjudicator_call_count"] = adjudicator_calls
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


def _scoped_hypotheses(
    module: Any,
    primary: dict[str, Any],
    challenger: dict[str, Any],
    selected_paths: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    primary_scoped, passthrough = scope.scoped_findings(
        primary["findings"], selected_paths
    )
    challenger_scoped = [
        item
        for item in module.hardened.result_findings(challenger)
        if isinstance(item, dict)
        and str(item.get("path", "") or "") in selected_paths
    ]
    return scope.dedupe_exact_findings(primary_scoped + challenger_scoped), passthrough


def _broad_hypotheses(
    module: Any,
    primary: dict[str, Any],
    challenger: dict[str, Any],
) -> list[dict[str, Any]]:
    return scope.dedupe_exact_findings(
        primary["findings"]
        + [
            item
            for item in module.hardened.result_findings(challenger)
            if isinstance(item, dict)
        ]
    )


def _patch_semantic_escalation(module: Any) -> None:
    original = getattr(module, _HYBRID_STORAGE, None)
    if original is None:
        original = getattr(module, "openrouter_review_with_hybrid_first_pass", None)
        if callable(original):
            setattr(module, _HYBRID_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v44 could not locate active hybrid review function")

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
        if (
            not bool(getattr(config, "candidate_scoped_escalation_review", True))
            or review_mode != "first-pass-deep"
        ):
            return original(
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

        primary_config = copy.copy(config)
        primary_config.adversarial_confirmation_review = False
        primary_config.semantic_adjudication_review = False
        primary, primary_model, primary_tier = original(
            pr,
            files,
            diff,
            schema,
            primary_config,
            reporter,
            risk_sentinels,
            line_index,
            deep_context_block,
            review_mode,
            context_summary,
            gh,
        )
        primary = dict(primary)
        primary["findings"] = scope.dedupe_exact_findings(
            [
                item
                for item in module.hardened.result_findings(primary)
                if isinstance(item, dict)
            ]
        )
        plan = scope.build_escalation_plan(
            module, primary, files, risk_sentinels, config, review_mode
        )
        mode = str(plan.get("mode", "") or "")
        if reporter:
            reporter.update(
                "candidate-escalation",
                (
                    f"mode={mode}; candidates={plan.get('candidate_count', 0)}; "
                    f"paths={len(plan.get('selected_paths', []))}; "
                    f"reasons={','.join(plan.get('reasons', []))}"
                ),
            )
        if mode == "none":
            final = _apply_escalation_metadata(
                module, gh, config, primary, plan, "primary-only", 0, 0, False
            )
            return final, primary_model, primary_tier

        selected_paths = set(plan.get("selected_paths", []))
        widened = mode == "broader-context"
        evidence = None
        if mode == "candidate-scoped":
            evidence, reason = scope.build_bounded_evidence(
                module,
                gh,
                pr,
                files,
                config,
                risk_sentinels,
                selected_paths,
            )
            if evidence is None:
                widened = True
                plan = dict(plan)
                plan["mode"] = "broader-context"
                plan["reasons"] = sorted(
                    set(plan.get("reasons", []))
                    | {reason or "bounded-context-unavailable"}
                )
            else:
                context_scope = "candidate-scoped"
        if widened:
            evidence = execution.broad_evidence(
                module,
                pr,
                files,
                diff,
                config,
                risk_sentinels,
                deep_context_block,
                review_mode,
                context_summary,
            )
            context_scope = "broader-context"
            selected_paths = {
                str(item.get("filename", "") or "").strip()
                for item in files
                if str(item.get("filename", "") or "").strip()
            }
        if evidence is None:
            raise module.hardened.ReviewQualityError(
                "DCOIR v44 could not build escalation evidence"
            )

        challenger, challenger_model, challenger_tier = execution.run_challenger(
            module, schema, config, reporter, evidence, context_scope
        )
        if context_scope == "candidate-scoped":
            hypotheses, passthrough = _scoped_hypotheses(
                module, primary, challenger, selected_paths
            )
        else:
            passthrough = []
            hypotheses = _broad_hypotheses(module, primary, challenger)
        adjudicated, adjudicator_model, adjudicator_tier = execution.run_adjudicator(
            module, schema, config, reporter, hypotheses, evidence, context_scope
        )
        final = (
            _merge_scoped_result(module, primary, passthrough, adjudicated)
            if context_scope == "candidate-scoped"
            else adjudicated
        )
        final = _apply_escalation_metadata(
            module,
            gh,
            config,
            final,
            plan,
            context_scope,
            1,
            1,
            widened,
        )
        model_label = (
            f"{primary_model}; candidate-challenger={challenger_model}; "
            f"candidate-adjudicator={adjudicator_model}"
        )
        tier_label = ", ".join(
            item
            for item in (
                str(primary_tier or "").strip(),
                str(challenger_tier or "").strip(),
                str(adjudicator_tier or "").strip(),
            )
            if item
        )
        return final, model_label, tier_label

    module.openrouter_review_with_hybrid_first_pass = openrouter_review_with_hybrid_first_pass


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, _APPLIED_ATTR, False):
        return
    _patch_config_loader(module)
    _patch_semantic_escalation(module)
    setattr(module, _APPLIED_ATTR, True)
