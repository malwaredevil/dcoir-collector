"""Canonical candidate-scoped semantic escalation stage for DCOIR Review."""

from __future__ import annotations

import copy
from typing import Any

from dcoir_review import semantic_adjudication as adjudication
from dcoir_review import candidate_escalation_execution as execution
from dcoir_review import candidate_escalation_scope as scope
from dcoir_review import candidate_escalation_telemetry as telemetry
from dcoir_review import candidate_escalation_quality_retry as quality_retry
from dcoir_review import semantic_adjudication_quality_retry as retry_policy


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
    for key in (
        adjudication.FINAL_ADJUDICATION_COMPLETION_ATTR,
        adjudication.PROVIDER_RESULT_KEYS_ATTR,
    ):
        if key in adjudicated:
            final[key] = adjudicated[key]
    if not passthrough:
        # The adjudication is the whole disposition: its summary and its own
        # quality-retry record (if any) replace the primary's.
        final["summary"] = adjudicated.get("summary", final.get("summary", ""))
        for key in retry_policy.QUALITY_RETRY_RESULT_KEYS:
            final.pop(key, None)
    if adjudicated.get("_quality_retry_attempted") is True:
        for key in retry_policy.QUALITY_RETRY_RESULT_KEYS & set(adjudicated):
            final[key] = adjudicated[key]
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


def _outside_scope(
    module: Any,
    result: dict[str, Any],
    selected_paths: set[str],
) -> bool:
    for item in module.hardened.result_findings(result):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "") or "").strip()
        if not path or path not in selected_paths:
            return True
    return False


def _widen_plan(plan, reason, findings):
    widened = dict(plan)
    widened["mode"] = "broader-context"
    widened["reasons"] = sorted(set(plan.get("reasons", [])) | {reason})
    widened["escalated_candidate_keys"] = [list(scope.finding_key(x)) for x in findings]
    return widened


def build_candidate_scoped_escalation_stage(module: Any, next_review: Any) -> Any:
    original = next_review
    if not callable(original):
        raise RuntimeError("DCOIR candidate escalation requires a callable hybrid review stage")

    def candidate_scoped_escalation_stage(
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
        enabled = bool(getattr(config, "candidate_scoped_escalation_review", True))
        stages_enabled = bool(
            getattr(config, "adversarial_confirmation_review", True)
        ) and bool(getattr(config, "semantic_adjudication_review", True))
        if (
            not enabled
            or review_mode not in {"first-pass-deep", "deep-forced"}
            or not stages_enabled
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

        if review_mode == "deep-forced":
            result, model, tier = original(
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
            plan = scope.build_escalation_plan(
                module, result, files, risk_sentinels, config, review_mode
            )
            final = telemetry.apply(
                module,
                gh,
                config,
                result,
                plan,
                "full-deep",
                int(bool(getattr(config, "adversarial_confirmation_review", True))),
                int(bool(getattr(config, "semantic_adjudication_review", True))),
                False,
            )
            return final, model, tier

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
            final = telemetry.apply(
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
                plan = _widen_plan(
                    plan, reason or "bounded-context-unavailable", primary["findings"]
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
            plan = {**plan, "selected_paths": sorted(selected_paths)}
        if evidence is None:
            raise module.hardened.ReviewQualityError(
                "DCOIR candidate escalation could not build escalation evidence"
            )

        challenger, challenger_model, challenger_tier = execution.run_challenger(
            module, schema, config, reporter, evidence, context_scope
        )
        challenger_calls = 1
        if context_scope == "candidate-scoped" and _outside_scope(
            module, challenger, selected_paths
        ):
            widened = True
            plan = _widen_plan(
                plan, "challenger-outside-bounded-scope", primary["findings"]
            )
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
            plan = {**plan, "selected_paths": sorted(selected_paths)}
            challenger, challenger_model, challenger_tier = execution.run_challenger(
                module, schema, config, reporter, evidence, context_scope
            )
            challenger_calls += 1
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
        adjudicator_calls = 1
        if context_scope == "candidate-scoped" and _outside_scope(
            module, adjudicated, selected_paths
        ):
            widened = True
            plan = _widen_plan(
                plan, "adjudicator-outside-bounded-scope", primary["findings"]
            )
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
            plan = {**plan, "selected_paths": sorted(selected_paths)}
            challenger, challenger_model, challenger_tier = execution.run_challenger(
                module, schema, config, reporter, evidence, context_scope
            )
            challenger_calls += 1
            hypotheses = _broad_hypotheses(module, primary, challenger)
            adjudicated, adjudicator_model, adjudicator_tier = execution.run_adjudicator(
                module, schema, config, reporter, hypotheses, evidence, context_scope
            )
            adjudicator_calls += 1
        # Retry only the adjudication; scoped passthrough findings stay outside
        # it and are merged back afterwards. A retry that escapes the bounded
        # scope is rejected like any failed optional retry.
        retry_sentinels = (
            [item for item in risk_sentinels or [] if getattr(item, "path", "") in selected_paths]
            if context_scope == "candidate-scoped"
            else risk_sentinels
        )
        pre_retry = adjudicated
        adjudicated, retry_model, retry_tier = quality_retry.retry_candidate_escalation(
            module, adjudicated, schema, config, reporter, retry_sentinels,
            line_index, hypotheses, evidence, context_scope,
        )
        if retry_model:
            adjudicator_calls += 1
        if retry_model and context_scope == "candidate-scoped" and _outside_scope(
            module, adjudicated, selected_paths
        ):
            quality_retry.reject_out_of_scope(module, config, reporter, retry_model, adjudicated)
            adjudicated, retry_model, retry_tier = pre_retry, None, None
        final = (
            _merge_scoped_result(module, primary, passthrough, adjudicated)
            if context_scope == "candidate-scoped"
            else adjudicated
        )
        if context_scope != "candidate-scoped" or not passthrough:
            # The adjudication is the whole disposition, so an all-sub-floor
            # result may take the terminal clean disposition like v35.
            final[adjudication.FINAL_ADJUDICATION_COMPLETION_ATTR] = (
                adjudication.FINAL_ADJUDICATION_COMPLETION_TOKEN
            )
        final = telemetry.apply(
            module,
            gh,
            config,
            final,
            plan,
            context_scope,
            challenger_calls,
            adjudicator_calls,
            widened,
        )
        model_label = (
            f"{primary_model}; candidate-challenger={challenger_model}; "
            f"candidate-adjudicator={adjudicator_model}"
            + (f"; candidate-adjudicator-retry={retry_model}" if retry_model else "")
        )
        tier_label = ", ".join(
            item
            for item in (
                str(primary_tier or "").strip(),
                str(challenger_tier or "").strip(),
                str(adjudicator_tier or "").strip(),
                str(retry_tier or "").strip(),
            )
            if item
        )
        return final, model_label, tier_label

    return candidate_scoped_escalation_stage
