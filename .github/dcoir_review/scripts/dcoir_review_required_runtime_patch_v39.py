"""DCOIR Review v39 semantic-adjudicator confidence-shape compatibility.

A live issue-456 blind run proved that the primary detector, independent
challenger, and semantic adjudicator still recover the deliberate semantic
defect, while publication can fail before independent verification when the
provider omits the schema-required ``confidence`` field from otherwise complete
adjudicated findings. The hardened normalizer correctly treats missing
confidence as 0.0, which is fail-closed but prevents the v21 evidence verifier
from independently deciding whether a real finding is supported.

v39 repairs only that provider/schema compatibility seam. It does not invent a
high confidence score and it does not authorize publication. For an otherwise
complete semantic-adjudication finding whose confidence is missing or null, v39
sets confidence to the configured normal publication floor solely to admit the
candidate to the existing v21 exact-head evidence verifier. Ordinary findings
still require verifier support at the verifier's own confidence floor before
repair synthesis or publication.

Provided confidence values remain authoritative and are never raised. Boolean,
non-numeric, non-finite, or out-of-range provided confidence values fail closed.
Malformed findings remain malformed. Detector/challenger results that did not
pass through semantic adjudication are not normalized. No branch-write,
commit, merge, or autonomous remediation capability is added.
"""

from __future__ import annotations

import math
from typing import Any

import dcoir_review_required_runtime_patch_v35 as v35


VERSION = "v39"
APPLIED_MARKER = "_dcoir_review_v39_applied"
HYBRID_STORAGE = "_dcoir_review_v39_original_hybrid_first_pass"
ADJUDICATION_BLOCK_STORAGE = "_dcoir_review_v39_original_adjudication_block"
NORMALIZATION_MARKER = "_semantic_adjudication_confidence_normalization"
NORMALIZATION_COUNT = "_semantic_adjudication_confidence_normalized_count"
NORMALIZATION_VALUE = "minimum-floor-for-verifier-admission"

_REQUIRED_OTHER_FIELDS = (
    "title",
    "severity",
    "path",
    "line",
    "body",
    "suggested_replacement",
    "validation",
)
_VALID_SEVERITIES = {"critical", "high", "medium", "low"}

ADJUDICATION_CONFIDENCE_CONTRACT = """
Output-shape requirement:
- EVERY retained finding MUST include ``confidence`` as a numeric value from
  0.0 through 1.0. Do not omit confidence even when the response schema already
  marks it required.
- Confidence is the adjudicator's own assessment. Do not copy an earlier
  detector's confidence merely to satisfy the field.
""".strip()


def _configured_floor(config: Any, hardened: Any) -> float:
    raw = getattr(config, "minimum_confidence", 0.0)
    if isinstance(raw, bool):
        raise hardened.ReviewQualityError("DCOIR v39 minimum confidence floor was boolean")
    try:
        floor = float(raw)
    except (TypeError, ValueError) as exc:
        raise hardened.ReviewQualityError("DCOIR v39 minimum confidence floor was not numeric") from exc
    if not math.isfinite(floor) or not 0.0 <= floor <= 1.0:
        raise hardened.ReviewQualityError("DCOIR v39 minimum confidence floor was outside 0.0..1.0")
    return floor


def _validate_other_finding_fields(item: dict[str, Any], hardened: Any) -> None:
    missing = [field for field in _REQUIRED_OTHER_FIELDS if field not in item]
    if missing:
        raise hardened.ReviewQualityError(
            "DCOIR v39 refused missing-confidence normalization for a partial finding; "
            f"missing fields: {', '.join(missing)}"
        )

    for field in ("title", "path", "body", "validation"):
        if not isinstance(item.get(field), str) or not str(item.get(field) or "").strip():
            raise hardened.ReviewQualityError(
                f"DCOIR v39 refused missing-confidence normalization for invalid {field}"
            )

    severity = item.get("severity")
    if not isinstance(severity, str) or severity.strip().lower() not in _VALID_SEVERITIES:
        raise hardened.ReviewQualityError(
            "DCOIR v39 refused missing-confidence normalization for invalid severity"
        )

    raw_line = item.get("line")
    if isinstance(raw_line, bool) or not isinstance(raw_line, int) or raw_line <= 0:
        raise hardened.ReviewQualityError(
            "DCOIR v39 refused missing-confidence normalization for invalid line"
        )

    if not isinstance(item.get("suggested_replacement"), str):
        raise hardened.ReviewQualityError(
            "DCOIR v39 refused missing-confidence normalization for invalid suggested_replacement"
        )


def _validate_provided_confidence(raw: Any, hardened: Any) -> None:
    # JSON-schema numeric output arrives as int/float. Do not broaden the live
    # compatibility contract to strings or booleans merely because float() could
    # coerce them.
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise hardened.ReviewQualityError(
            "DCOIR v39 semantic adjudicator returned non-numeric confidence"
        )
    confidence = float(raw)
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise hardened.ReviewQualityError(
            "DCOIR v39 semantic adjudicator confidence was outside 0.0..1.0"
        )


def _normalize_semantic_adjudication_confidence(
    module: Any,
    result: Any,
    config: Any,
) -> tuple[dict[str, Any], int, float]:
    """Normalize only missing semantic-adjudicator confidence fields.

    The configured floor is an admission-to-verification value. v21 remains the
    independent publication authority for ordinary model findings.
    """

    if not isinstance(result, dict):
        raise module.hardened.ReviewQualityError("DCOIR v39 received a non-object review result")

    floor = _configured_floor(config, module.hardened)
    if not bool(result.get("_semantic_adjudication_attempted")):
        return result, 0, floor

    raw_findings = result.get("findings")
    if not isinstance(raw_findings, list):
        raise module.hardened.ReviewQualityError(
            "DCOIR v39 semantic-adjudication result did not contain a findings list"
        )

    normalized_findings: list[Any] = []
    normalized_count = 0
    for raw_item in raw_findings:
        if not isinstance(raw_item, dict):
            raise module.hardened.ReviewQualityError(
                "DCOIR v39 semantic adjudicator returned a non-object finding"
            )
        item = dict(raw_item)
        if "confidence" not in item or item.get("confidence") is None:
            _validate_other_finding_fields(item, module.hardened)
            item["confidence"] = floor
            normalized_count += 1
        else:
            _validate_provided_confidence(item.get("confidence"), module.hardened)
        normalized_findings.append(item)

    if not normalized_count:
        return result, 0, floor

    normalized = dict(result)
    normalized["findings"] = normalized_findings
    normalized[NORMALIZATION_MARKER] = NORMALIZATION_VALUE
    normalized[NORMALIZATION_COUNT] = normalized_count
    return normalized, normalized_count, floor


def _patch_adjudication_prompt() -> None:
    original = getattr(v35, ADJUDICATION_BLOCK_STORAGE, None)
    if original is None:
        original = str(getattr(v35, "ADJUDICATION_BLOCK", "") or "")
        setattr(v35, ADJUDICATION_BLOCK_STORAGE, original)
    if not original:
        raise RuntimeError("DCOIR v39 could not locate the v35 semantic adjudication prompt block")
    v35.ADJUDICATION_BLOCK = original.rstrip() + "\n\n" + ADJUDICATION_CONFIDENCE_CONTRACT


def _patch_semantic_adjudication_result(module: Any) -> None:
    original = getattr(module, HYBRID_STORAGE, None)
    if original is None:
        original = getattr(module, "openrouter_review_with_hybrid_first_pass", None)
        if callable(original):
            setattr(module, HYBRID_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v39 could not locate the active hybrid review function")

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
        result, model_label, tier_label = original(
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
        normalized, count, floor = _normalize_semantic_adjudication_confidence(
            module, result, config
        )
        if count:
            module.hardened.write_debug_json_artifact_safely(
                config,
                "responses/07-v39-confidence-normalized.json",
                {
                    "schema_version": "dcoir_review_v39_confidence_normalization_v1",
                    "normalized_count": count,
                    "admission_floor": floor,
                    "normalization": NORMALIZATION_VALUE,
                    "result": normalized,
                },
            )
            if reporter:
                reporter.update(
                    "semantic-adjudication-confidence",
                    (
                        f"normalized_missing={count}; admission_floor={floor:.2f}; "
                        "publication still requires v21 verifier support"
                    ),
                )
        return normalized, model_label, tier_label

    module.openrouter_review_with_hybrid_first_pass = openrouter_review_with_hybrid_first_pass


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return

    _patch_adjudication_prompt()
    _patch_semantic_adjudication_result(module)
    setattr(module, APPLIED_MARKER, True)
