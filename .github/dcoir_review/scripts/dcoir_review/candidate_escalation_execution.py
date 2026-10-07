"""Canonical candidate-escalation challenger/adjudicator execution helpers."""

from __future__ import annotations

import copy
from typing import Any

from dcoir_review import adversarial_confirmation
from dcoir_review import semantic_adjudication as adjudication
from dcoir_review import semantic_adjudication_normalization as normalization
from dcoir_review import semantic_adjudication_confidence as confidence
from dcoir_review import candidate_escalation_scope as scope


def prompt_with_budget(text: str, config: Any, marker: str) -> str:
    maximum = max(0, int(getattr(config, "max_prompt_chars", 120000)))
    if len(text) <= maximum:
        return text
    if maximum <= len(marker):
        return marker[:maximum]
    return text[: maximum - len(marker)] + marker


def run_challenger(
    module: Any,
    schema: dict[str, Any],
    config: Any,
    reporter: Any,
    evidence: str,
    context_scope: str,
) -> tuple[dict[str, Any], str, str]:
    staged = copy.copy(config)
    models = adversarial_confirmation.confirmation_models(config)
    staged.model_stack = models
    staged.model = models[0]
    prompt = prompt_with_budget(
        f"{adversarial_confirmation.INDEPENDENT_CONFIRMATION_BLOCK}\n\n{evidence}",
        staged,
        "\n\n[v44 challenger evidence truncated by reviewer budget]",
    )
    artifact_scope = "candidate" if context_scope == "candidate-scoped" else "broad"
    module.hardened.write_debug_text_artifact_safely(
        config, f"prompts/08-v44-{artifact_scope}-challenger.txt", prompt
    )
    if reporter:
        reporter.update(
            "candidate-escalation-challenger",
            f"scope={context_scope}; independent challenger={models[0]}",
        )
    result, model, tier = module.hardened.openrouter_review(
        prompt, schema, staged, reporter
    )
    module.hardened.write_debug_json_artifact_safely(
        config,
        f"responses/08-v44-{artifact_scope}-challenger.json",
        {
            "context_scope": context_scope,
            "model_used": model,
            "service_tier": tier,
            "result": result,
        },
    )
    return result, model, tier


def run_adjudicator(
    module: Any,
    schema: dict[str, Any],
    config: Any,
    reporter: Any,
    hypotheses: list[dict[str, Any]],
    evidence: str,
    context_scope: str,
) -> tuple[dict[str, Any], str, str]:
    staged = copy.copy(config)
    models = adjudication.adjudication_models(config)
    staged.model_stack = models
    staged.model = models[0]
    max_findings = int(
        getattr(
            config,
            "semantic_adjudication_max_findings",
            adjudication.DEFAULT_ADJUDICATION_MAX_FINDINGS,
        )
    )
    digest_chars = int(
        getattr(
            config,
            "semantic_adjudication_candidate_digest_chars",
            adjudication.DEFAULT_CANDIDATE_DIGEST_CHARS,
        )
    )
    digest = scope.candidate_digest(hypotheses, digest_chars)
    instruction = adjudication.ADJUDICATION_BLOCK.format(max_findings=max_findings)
    prompt = prompt_with_budget(
        (
            f"{instruction}\n\n"
            "Candidate hypotheses from the bounded primary/challenger evidence:\n"
            f"```json\n{module.base.sanitize_text(digest, config)}\n```\n\n"
            f"Escalation context scope: {context_scope}.\n"
            "Adjudicate only what the supplied exact-head evidence can prove.\n\n"
            f"{evidence}"
        ),
        staged,
        "\n\n[v44 adjudication evidence truncated by reviewer budget]",
    )
    artifact_scope = "candidate" if context_scope == "candidate-scoped" else "broad"
    module.hardened.write_debug_text_artifact_safely(
        config, f"prompts/09-v44-{artifact_scope}-adjudication.txt", prompt
    )
    if reporter:
        reporter.update(
            "candidate-escalation-adjudication",
            f"scope={context_scope}; hypotheses={len(hypotheses)}; adjudicator={models[0]}",
        )
    raw, model, tier = module.hardened.openrouter_review(
        prompt, schema, staged, reporter
    )
    normalized = normalization.normalize_adjudicator_result(module, raw)
    capped = adjudication._cap_adjudicated_findings(module, normalized, max_findings)
    capped["_semantic_adjudication_attempted"] = True
    capped["_semantic_adjudication_model"] = model
    capped["_semantic_adjudication_input_candidates"] = len(hypotheses)
    capped["_semantic_adjudication_context_scope"] = context_scope
    capped, normalized_count, floor = confidence._normalize_semantic_adjudication_confidence(
        module, capped, config
    )
    capped["_semantic_adjudication_output_findings"] = len(
        module.hardened.result_findings(capped)
    )
    module.hardened.write_debug_json_artifact_safely(
        config,
        f"responses/09-v44-{artifact_scope}-adjudication.json",
        {
            "context_scope": context_scope,
            "model_used": model,
            "service_tier": tier,
            "input_candidate_count": len(hypotheses),
            "confidence_normalized_count": normalized_count,
            "confidence_admission_floor": floor,
            "result": capped,
        },
    )
    return capped, model, tier


def broad_evidence(
    module: Any,
    pr: dict[str, Any],
    files: list[dict[str, Any]],
    diff: str,
    config: Any,
    risk_sentinels: list[Any],
    deep_context_block: str,
    review_mode: str,
    context_summary: str,
) -> str:
    return module.build_prompt(
        pr,
        files,
        diff,
        config,
        risk_sentinels,
        deep_context_block,
        review_mode,
        context_summary,
    )
