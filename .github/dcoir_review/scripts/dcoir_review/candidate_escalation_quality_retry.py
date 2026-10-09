"""Bounded final-quality repair for candidate-escalation adjudication."""

from __future__ import annotations

import copy
from typing import Any

from dcoir_review import semantic_adjudication as adjudication
from dcoir_review import semantic_adjudication_normalization as normalization
from dcoir_review import semantic_adjudication_quality_retry as quality_retry


_PROVENANCE_KEYS = (
    "_semantic_adjudication_attempted",
    "_semantic_adjudication_model",
    "_semantic_adjudication_input_candidates",
    "_semantic_adjudication_context_scope",
)


def retry_candidate_escalation(
    module: Any, result: dict[str, Any], schema: dict[str, Any], config: Any,
    reporter: Any, risk_sentinels: Any, line_index: Any,
    evidence: str, context_scope: str,
) -> tuple[dict[str, Any], str | None, str | None]:
    """Check the *outer* v44 adjudicator, which bypasses the v35 retry stage.

    The shared post-adjudication owner handles exactly one provider call, prompt
    floor projection, model validation, abort propagation, and bounded merging.
    Neither speculative findings nor absent required sentinels become clean here.
    """
    config_retry = copy.copy(config)
    models = adjudication.adjudication_models(config)
    config_retry.model_stack = models
    config_retry.model = models[0]
    max_findings = int(getattr(
        config, "semantic_adjudication_max_findings",
        adjudication.DEFAULT_ADJUDICATION_MAX_FINDINGS,
    ))
    original_prompt = (
        adjudication.ADJUDICATION_BLOCK.format(max_findings=max_findings)
        + "\n\nFinal candidate-escalation evidence and scoped hypotheses: \n"
        + f"Context: {context_scope}\n"
        + str(evidence)
    )
    repaired, retry_model, retry_tier = quality_retry.retry_rejected_adjudication(
        module, result, config, risk_sentinels, line_index, original_prompt,
        schema, config_retry, reporter, max_findings,
        adjudication._cap_adjudicated_findings,
        normalization.normalize_adjudicator_result,
    )
    if not retry_model:
        return repaired, None, None
    repaired = dict(repaired)
    for key in _PROVENANCE_KEYS:
        if key in result:
            repaired[key] = result[key]
    repaired["_semantic_adjudication_output_findings"] = len(
        module.hardened.result_findings(repaired)
    )
    return repaired, retry_model, retry_tier
