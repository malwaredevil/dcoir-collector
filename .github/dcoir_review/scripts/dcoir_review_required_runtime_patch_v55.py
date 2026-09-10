"""DCOIR Review v55 bounded semantic-adjudicator shape recovery.

Issue #524 was exposed by live benchmark run 34454110354: the semantic
adjudicator completed successfully and returned valid JSON, but the parsed
object matched neither the canonical findings envelope nor v37's complete flat
single-finding compatibility shape. The review then terminated after all premium
semantic work had already completed.

v55 preserves the versioned v44 helper unchanged and replaces only its
``run_adjudicator`` seam after v54 telemetry is installed. Recovery is deliberately
narrow: only an unrelated valid-JSON object with none of the flat-finding fields
may fall back to already-structured hypotheses from the same escalation. Those
hypotheses must satisfy the existing publication-candidate semantic contract,
pass the active production ranking boundary, and are hard-capped to v33's current
verifier capacity. The rejected adjudicator object is never interpreted or
persisted.

Every recovered hypothesis still flows through the existing exact-head v21/v33
verifier and all downstream publication/repair gates. No additional model call,
provider/routing change, retry change, confidence synthesis, branch write, or
automatic remediation is introduced.
"""

from __future__ import annotations

import copy
import math
from typing import Any

import dcoir_review_required_runtime_patch_v33 as v33
import dcoir_review_required_runtime_patch_v35 as v35
import dcoir_review_required_runtime_patch_v37 as v37
import dcoir_review_required_runtime_patch_v39 as v39
import dcoir_review_required_runtime_patch_v44_execution as execution
import dcoir_review_required_runtime_patch_v44_scope as scope
import dcoir_review_required_runtime_patch_v51 as v51


VERSION = "v55"
APPLIED_MARKER = "_dcoir_review_v55_applied"
RUN_STORAGE = "_dcoir_review_v55_original_run_adjudicator"
RECOVERY_MARKER = "_semantic_adjudication_shape_recovery"
RECOVERY_REASON = "schema-incompatible-valid-json-object"
_V37_SHAPE_ERROR_PREFIX = (
    "DCOIR v37 adjudicator returned neither a findings envelope nor a complete flat single finding"
)
_V54_STAGE_LABEL_ATTR = "_dcoir_v54_stage_label"
_VALID_SEVERITIES = {"critical", "high", "medium", "low"}


def _recoverable_shape_failure(raw: Any, exc: Exception) -> bool:
    """Recognize only the live #524 valid-object compatibility seam."""

    if not isinstance(raw, dict):
        return False
    if "findings" in raw:
        # Canonical-envelope validation stays owned by v35/v37. A malformed
        # findings value must not be converted into a fallback.
        return False
    if v37._is_complete_flat_finding(raw):
        return False
    if any(field in raw for field in v37._REQUIRED_FLAT_FINDING_FIELDS):
        # Preserve v37's historical fail-closed behavior for partial flat
        # findings. v55 never repairs missing semantic fields.
        return False
    return str(exc).startswith(_V37_SHAPE_ERROR_PREFIX)


def _complete_upstream_hypothesis(_module: Any, item: Any) -> bool:
    """Accept only complete publication candidates without coercing semantic data.

    v51 may deliberately remove detector-authored ``suggested_replacement`` while
    preserving the semantic candidate. That field is not part of v37's publication
    identity and is regenerated only after verification, so its absence must not
    erase otherwise complete upstream evidence during this fallback.
    """

    if not isinstance(item, dict):
        return False
    if not all(field in item for field in v37._REQUIRED_FLAT_FINDING_FIELDS):
        return False
    for field in ("title", "severity", "path", "body", "validation"):
        if not isinstance(item.get(field), str) or not str(item.get(field) or "").strip():
            return False
    if str(item.get("severity", "") or "").strip().lower() not in _VALID_SEVERITIES:
        return False

    line = item.get("line")
    if isinstance(line, bool) or not isinstance(line, int) or line <= 0:
        return False
    confidence = item.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return False
    try:
        parsed_confidence = float(confidence)
    except (OverflowError, TypeError, ValueError):
        return False
    if not math.isfinite(parsed_confidence) or not 0.0 <= parsed_confidence <= 1.0:
        return False

    suggested = item.get("suggested_replacement")
    if suggested is not None and not isinstance(suggested, str):
        return False
    return True


def _recovery_identity_key(item: dict[str, Any]) -> tuple[Any, ...]:
    """Return a stable identity-aware key without collapsing v51 semantics."""

    candidate_id = str(item.get(v51.CANDIDATE_ID_FIELD, "") or "").strip()
    if candidate_id:
        return ("candidate-id", candidate_id)

    semantic_key = v51._raw_key(item.get(v51.SEMANTIC_KEY_FIELD))
    if semantic_key is not None and semantic_key[2].startswith(v51.SEMANTIC_KIND_PREFIX):
        return ("semantic-key",) + semantic_key

    # Unprepared hypotheses still need deterministic duplicate removal before the
    # active ranker. v51's derived candidate identity includes path, line, title,
    # body, and validation, so same-site/same-title but semantically distinct
    # hypotheses remain separate while exact semantic duplicates collapse.
    return ("derived-candidate-id", v51._candidate_id(item))


def _dedupe_upstream_hypotheses(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate exact semantic identities while preserving v51 distinctions."""

    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for raw in findings:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        key = _recovery_identity_key(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _recover_upstream_hypotheses(
    module: Any,
    hypotheses: list[dict[str, Any]],
    config: Any,
) -> dict[str, Any] | None:
    """Rank and bound complete same-escalation hypotheses for verification."""

    usable = [
        dict(item)
        for item in hypotheses
        if _complete_upstream_hypothesis(module, item)
    ]
    if not usable:
        return None

    deduped = _dedupe_upstream_hypotheses(usable)
    ranked = module.rank_findings_for_required_budget(deduped, config)
    verifier_capacity = v33.verifier_candidate_limit(config)
    selected = [dict(item) for item in ranked if isinstance(item, dict)][:verifier_capacity]
    if not selected:
        return None

    marker = {
        "version": VERSION,
        "reason": RECOVERY_REASON,
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
        RECOVERY_MARKER: marker,
    }


def run_adjudicator(
    module: Any,
    schema: dict[str, Any],
    config: Any,
    reporter: Any,
    hypotheses: list[dict[str, Any]],
    evidence: str,
    context_scope: str,
) -> tuple[dict[str, Any], str, str]:
    """Run the historical v44 adjudicator with one bounded post-parse fallback."""

    staged = copy.copy(config)
    models = v35._as_string_list(
        getattr(config, "semantic_adjudication_model_stack", None),
        v35.DEFAULT_ADJUDICATION_MODELS,
    )
    staged.model_stack = models
    staged.model = models[0]
    # v54 is already installed when v55 is applied. Give its observational
    # wrapper an explicit stage label because the callsite now lives in v55.
    setattr(staged, _V54_STAGE_LABEL_ATTR, "semantic-adjudicator")

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
    prompt = execution.prompt_with_budget(
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

    raw, model, tier = module.hardened.openrouter_review(prompt, schema, staged, reporter)
    recovered_shape = False
    try:
        normalized = v37._normalize_adjudicator_result(module, raw)
    except module.hardened.ReviewQualityError as exc:
        if not _recoverable_shape_failure(raw, exc):
            raise
        recovered = _recover_upstream_hypotheses(module, hypotheses, config)
        if recovered is None:
            raise
        normalized = recovered
        recovered_shape = True
        marker = normalized[RECOVERY_MARKER]
        if reporter:
            reporter.update(
                "semantic-adjudicator-shape-recovery",
                (
                    f"reason={marker['reason']}; upstream={marker['upstream_hypotheses']}; "
                    f"usable={marker['usable_hypotheses']}; selected={marker['selected_hypotheses']}; "
                    f"verifier_capacity={marker['verifier_capacity']}; extra_model_calls=0"
                ),
            )

    # Normal output retains v35's historical semantic-adjudicator cap. Recovery
    # is already ranked through the active production selection boundary and
    # hard-capped to v33's verifier capacity; applying the smaller adjudicator
    # cap again could discard required-risk reservations before verification.
    capped = normalized if recovered_shape else v35._cap_adjudicated_findings(module, normalized, max_findings)
    capped["_semantic_adjudication_attempted"] = True
    capped["_semantic_adjudication_model"] = model
    capped["_semantic_adjudication_input_candidates"] = len(hypotheses)
    capped["_semantic_adjudication_context_scope"] = context_scope
    capped, normalized_count, floor = v39._normalize_semantic_adjudication_confidence(
        module, capped, config
    )
    capped["_semantic_adjudication_output_findings"] = len(module.hardened.result_findings(capped))
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
            "shape_recovery": capped.get(RECOVERY_MARKER),
            "result": capped,
        },
    )
    return capped, model, tier


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    original = getattr(execution, RUN_STORAGE, None)
    if original is None:
        original = getattr(execution, "run_adjudicator", None)
        if callable(original):
            setattr(execution, RUN_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v55 could not locate v44 adjudicator execution helper")
    execution.run_adjudicator = run_adjudicator
    setattr(module, APPLIED_MARKER, True)
