"""Bounded final-quality repair for candidate-escalation adjudication."""

from __future__ import annotations

from typing import Any

from dcoir_review import candidate_escalation_execution as execution
from dcoir_review import semantic_adjudication as adjudication
from dcoir_review import semantic_adjudication_confidence as confidence
from dcoir_review import semantic_adjudication_normalization as normalization
from dcoir_review import semantic_adjudication_quality_retry as quality_retry


REPORT_STAGE = "candidate-escalation-adjudication-quality-retry"
# Only candidate-scoped retries have a bounded scope to escape.
OUT_OF_SCOPE_ARTIFACT_STAGE = "09-v44-candidate-adjudication"
_PROVENANCE_KEYS = (
    "_semantic_adjudication_attempted",
    "_semantic_adjudication_model",
    "_semantic_adjudication_input_candidates",
    "_semantic_adjudication_context_scope",
    # The first provider envelope; the retry envelope is recorded separately.
    adjudication.PROVIDER_RESULT_KEYS_ATTR,
)


def retry_candidate_escalation(
    module: Any, result: dict[str, Any], schema: dict[str, Any], config: Any,
    reporter: Any, risk_sentinels: Any, line_index: Any,
    hypotheses: list[dict[str, Any]], evidence: str, context_scope: str,
) -> tuple[dict[str, Any], str | None, str | None]:
    """Check the *outer* v44 adjudicator, which bypasses the v35 retry stage.

    ``result`` must be the v44 adjudication itself, never a merge with scoped
    passthrough findings: the retry re-adjudicates the same hypotheses from the
    exact prompt the adjudicator received. The shared post-adjudication owner
    handles exactly one provider call, prompt floor projection, model
    validation, abort propagation, and bounded merging. Neither speculative
    findings nor absent required sentinels become clean here.
    """
    max_findings = execution.adjudication_max_findings(config)

    def prompt() -> str:
        return execution.adjudicator_prompt(
            module, config, hypotheses, evidence, context_scope
        )

    repaired, retry_model, retry_tier = quality_retry.retry_rejected_adjudication(
        module, result, config, risk_sentinels, line_index, prompt,
        schema, execution.adjudicator_config(config), reporter, max_findings,
        adjudication._cap_adjudicated_findings,
        normalization.normalize_adjudicator_result,
        artifact_stage=f"09-v44-{execution.artifact_scope(context_scope)}-adjudication",
        report_stage=REPORT_STAGE,
    )
    if not retry_model:
        return repaired, None, None
    repaired = dict(repaired)
    for key in _PROVENANCE_KEYS:
        if key in result:
            repaired[key] = result[key]
    # The first v44 adjudication admits complete missing-confidence findings at
    # the floor, and no confidence stage runs after this one, so the retry
    # output must receive the same admission rather than failing closed.
    # Add to, never replace, any first-pass count the shared owner recorded.
    prior_count = int(repaired.get(confidence.NORMALIZATION_COUNT, 0) or 0)
    repaired, count, _floor = confidence._normalize_semantic_adjudication_confidence(
        module, repaired, config
    )
    if count:
        repaired[confidence.NORMALIZATION_COUNT] = prior_count + count
    repaired["_semantic_adjudication_output_findings"] = len(
        module.hardened.result_findings(repaired)
    )
    return repaired, retry_model, retry_tier


def reject_out_of_scope(
    module: Any, config: Any, reporter: Any, retry_model: str,
    retry_result: dict[str, Any],
) -> None:
    """Record a bounded-scope retry rejection; the caller keeps the first pass.

    The escaped findings are never merged. Like any failed optional retry, the
    pre-retry adjudication continues to the downstream fail-closed gates, so
    publishable passthrough findings are not lost to one stray retry finding.
    """
    module.hardened.write_debug_json_artifact_safely(
        config,
        f"responses/{OUT_OF_SCOPE_ARTIFACT_STAGE}-quality-retry-out-of-scope.json",
        {
            "retry_model": retry_model,
            "kept": "first-pass-adjudication",
            "rejected_result": retry_result,
        },
    )
    if reporter:
        reporter.update(
            REPORT_STAGE,
            "retry returned a finding outside the bounded scope; "
            "keeping the first-pass adjudication for downstream gates",
        )
