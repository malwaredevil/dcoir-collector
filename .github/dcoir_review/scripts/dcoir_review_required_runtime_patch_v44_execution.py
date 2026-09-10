"""Architecture-B v44 challenger/adjudicator execution helpers."""

from __future__ import annotations

import copy
from typing import Any

import dcoir_review_required_runtime_patch_v32 as v32
import dcoir_review_required_runtime_patch_v33 as v33
import dcoir_review_required_runtime_patch_v35 as v35
import dcoir_review_required_runtime_patch_v37 as v37
import dcoir_review_required_runtime_patch_v39 as v39
import dcoir_review_required_runtime_patch_v44_scope as scope


ADJUDICATOR_SHAPE_RECOVERY_MARKER = "_semantic_adjudication_shape_recovery"
ADJUDICATOR_SHAPE_RECOVERY_VERSION = "issue-524-v1"
_V37_SHAPE_ERROR_PREFIX = (
    "DCOIR v37 adjudicator returned neither a findings envelope nor a complete flat single finding"
)


def prompt_with_budget(text: str, config: Any, marker: str) -> str:
    maximum = int(getattr(config, "max_prompt_chars", 120000))
    if len(text) <= maximum:
        return text
    return text[: max(0, maximum - len(marker))] + marker


def _recoverable_adjudicator_shape_failure(raw: Any, exc: Exception) -> bool:
    """Return true only for the exact valid-object v37 compatibility gap."""

    if not isinstance(raw, dict):
        return False
    if "findings" in raw:
        # Canonical-envelope validation remains owned by v35/v37. A malformed
        # findings value must stay fail-closed rather than entering this fallback.
        return False
    if v37._is_complete_flat_finding(raw):
        return False
    return str(exc).startswith(_V37_SHAPE_ERROR_PREFIX)


def _recover_upstream_hypotheses(
    module: Any,
    hypotheses: list[dict[str, Any]],
    config: Any,
) -> dict[str, Any] | None:
    """Bound same-escalation structured hypotheses for independent verification.

    The rejected adjudicator object is never interpreted or persisted here. Only
    already-structured upstream findings that are complete enough for the normal
    v37 publication shape are eligible. The active production ranker remains the
    selection authority so required-risk reservation and v51 candidate identity
    protections stay in force, then v33's verifier ceiling provides the hard cap.
    """

    usable = [
        dict(item)
        for item in hypotheses
        if isinstance(item, dict) and v37._is_complete_flat_finding(item)
    ]
    if not usable:
        return None

    deduped = scope.dedupe_exact_findings(usable)
    ranked = module.rank_findings_for_required_budget(deduped, config)
    verifier_capacity = v33.verifier_candidate_limit(config)
    selected = [
        dict(item)
        for item in ranked
        if isinstance(item, dict)
    ][:verifier_capacity]
    if not selected:
        return None

    marker = {
        "version": ADJUDICATOR_SHAPE_RECOVERY_VERSION,
        "reason": "schema-incompatible-valid-json-object",
        "upstream_hypotheses": len(hypotheses),
        "usable_hypotheses": len(usable),
        "deduped_hypotheses": len(deduped),
        "selected_hypotheses": len(selected),
        "verifier_capacity": verifier_capacity,
        "extra_model_calls": 0,
    }
    return {
        "summary": (
            "Semantic adjudicator output was unusable; bounded upstream hypotheses "
            "were retained for independent verification."
        ),
        "findings": selected,
        ADJUDICATOR_SHAPE_RECOVERY_MARKER: marker,
    }


def run_challenger(
    module: Any,
    schema: dict[str, Any],
    config: Any,
    reporter: Any,
    evidence: str,
    context_scope: str,
) -> tuple[dict[str, Any], str, str]:
    staged = copy.copy(config)
    models = v32._as_string_list(
        getattr(config, "adversarial_confirmation_model_stack", None),
        v32.DEFAULT_CONFIRMATION_MODELS,
    )
    staged.model_stack = models
    staged.model = models[0]
    prompt = prompt_with_budget(
        f"{v32.INDEPENDENT_CONFIRMATION_BLOCK}\n\n{evidence}",
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
    models = v35._as_string_list(
        getattr(config, "semantic_adjudication_model_stack", None),
        v35.DEFAULT_ADJUDICATION_MODELS,
    )
    staged.model_stack = models
    staged.model = models[0]
    max_findings = int(
        getattr(
            config,
            "semantic_adjudication_max_findings",
            v35.DEFAULT_ADJUDICATION_MAX_FINDINGS,
        )
    )
    digest_chars = int(
        getattr(
            config,
            "semantic_adjudication_candidate_digest_chars",
            v35.DEFAULT_CANDIDATE_DIGEST_CHARS,
        )
    )
    digest = scope.candidate_digest(hypotheses, digest_chars)
    instruction = v35.ADJUDICATION_BLOCK.format(max_findings=max_findings)
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

    recovered_shape = False
    try:
        normalized = v37._normalize_adjudicator_result(module, raw)
    except module.hardened.ReviewQualityError as exc:
        if not _recoverable_adjudicator_shape_failure(raw, exc):
            raise
        recovered = _recover_upstream_hypotheses(module, hypotheses, config)
        if recovered is None:
            raise
        normalized = recovered
        recovered_shape = True
        marker = normalized[ADJUDICATOR_SHAPE_RECOVERY_MARKER]
        if reporter:
            reporter.update(
                "semantic-adjudicator-shape-recovery",
                (
                    f"reason={marker['reason']}; upstream={marker['upstream_hypotheses']}; "
                    f"usable={marker['usable_hypotheses']}; selected={marker['selected_hypotheses']}; "
                    f"verifier_capacity={marker['verifier_capacity']}; extra_model_calls=0"
                ),
            )

    # Normal v37 output retains the historical v35 adjudication cap. The shape-
    # recovery path is already deterministically ranked and bounded to v33's
    # active verifier capacity, so do not apply the smaller semantic-adjudicator
    # output cap a second time and silently discard required-risk reservations.
    capped = normalized if recovered_shape else v35._cap_adjudicated_findings(module, normalized, max_findings)
    capped["_semantic_adjudication_attempted"] = True
    capped["_semantic_adjudication_model"] = model
    capped["_semantic_adjudication_input_candidates"] = len(hypotheses)
    capped["_semantic_adjudication_context_scope"] = context_scope
    capped, normalized_count, floor = v39._normalize_semantic_adjudication_confidence(
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
            "shape_recovery": capped.get(ADJUDICATOR_SHAPE_RECOVERY_MARKER),
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
