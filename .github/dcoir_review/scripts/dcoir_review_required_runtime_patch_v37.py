"""DCOIR Review v37 semantic-adjudicator result-shape compatibility.

A live issue-456 blind run proved that the primary detector, independent
challenger, and v35 semantic adjudicator can all recover the same concrete
semantic defect, while publication still loses the finding when the adjudicator
returns one complete finding as the top-level JSON object instead of the normal
``{"findings": [...]}`` envelope.

v37 repairs only that serialization seam. It does not alter detector prompts,
adjudication prompts, model selection, confidence thresholds, publication
budgets, verification, repair synthesis, or branch-write capabilities.

Accepted result shapes are deliberately narrow:

1. the normal object containing a ``findings`` list; or
2. one complete top-level finding containing every required publication field.

A partial top-level object is still malformed and fails closed. The existing
v35 cap/ranking logic remains authoritative after normalization.
"""

from __future__ import annotations

from typing import Any

import dcoir_review_required_runtime_patch_v35 as v35


VERSION = "v37"
APPLIED_MARKER = "_dcoir_review_v37_applied"
CAP_STORAGE = "_dcoir_review_v37_original_cap_adjudicated_findings"
FLAT_SHAPE_MARKER = "_semantic_adjudication_result_shape"
FLAT_SHAPE_VALUE = "flat-single-finding"

_REQUIRED_FLAT_FINDING_FIELDS = (
    "title",
    "severity",
    "confidence",
    "path",
    "line",
    "body",
    "validation",
)


def _is_complete_flat_finding(result: dict[str, Any]) -> bool:
    """Return true only for an unambiguous, publication-shaped single finding."""

    if "findings" in result:
        return False
    if not all(field in result for field in _REQUIRED_FLAT_FINDING_FIELDS):
        return False

    for field in ("title", "severity", "path", "body", "validation"):
        if not isinstance(result.get(field), str) or not str(result.get(field) or "").strip():
            return False

    raw_line = result.get("line")
    if isinstance(raw_line, bool):
        return False
    try:
        line = int(raw_line)
    except (TypeError, ValueError):
        return False
    if line <= 0:
        return False

    raw_confidence = result.get("confidence")
    if isinstance(raw_confidence, bool):
        return False
    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        return False
    if not 0.0 <= confidence <= 1.0:
        return False

    return True


def _normalize_adjudicator_result(module: Any, result: Any) -> dict[str, Any]:
    """Normalize the one safe compatibility shape without forgiving malformed output."""

    if not isinstance(result, dict):
        raise module.hardened.ReviewQualityError("DCOIR v37 adjudicator returned a non-object result")

    if "findings" in result:
        # Preserve the canonical envelope exactly. v35 remains responsible for
        # validating that findings is a list and for enforcing the output cap.
        return result

    if not _is_complete_flat_finding(result):
        missing = [field for field in _REQUIRED_FLAT_FINDING_FIELDS if field not in result]
        detail = f"; missing required fields: {', '.join(missing)}" if missing else ""
        raise module.hardened.ReviewQualityError(
            "DCOIR v37 adjudicator returned neither a findings envelope nor a complete flat single finding"
            + detail
        )

    finding = dict(result)
    return {
        "findings": [finding],
        FLAT_SHAPE_MARKER: FLAT_SHAPE_VALUE,
    }


def _patch_v35_adjudication_cap(module: Any) -> None:
    original = getattr(v35, CAP_STORAGE, None)
    if original is None:
        original = getattr(v35, "_cap_adjudicated_findings", None)
        if callable(original):
            setattr(v35, CAP_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v37 could not locate v35 adjudication result cap")

    def _cap_adjudicated_findings(active_module: Any, result: Any, limit: int) -> dict[str, Any]:
        normalized = _normalize_adjudicator_result(active_module, result)
        capped = original(active_module, normalized, limit)
        if normalized.get(FLAT_SHAPE_MARKER) == FLAT_SHAPE_VALUE:
            capped[FLAT_SHAPE_MARKER] = FLAT_SHAPE_VALUE
        return capped

    v35._cap_adjudicated_findings = _cap_adjudicated_findings


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return

    _patch_v35_adjudication_cap(module)
    setattr(module, APPLIED_MARKER, True)
