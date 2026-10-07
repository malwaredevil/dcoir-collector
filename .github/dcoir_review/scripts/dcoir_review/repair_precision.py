"""Stable defect-absence precision policy for DCOIR verified repairs.

This owner centralizes the repair-side precision behavior historically carried
by v30. Detection precision belongs to the hardened sentinel rules; this module
only owns defect-presence normalization, high-confidence suppression policy,
and final suppression filtering.
"""

from __future__ import annotations

import math
from typing import Any


VERSION = "v30"  # Persisted repair-marker compatibility value.
SUPPRESS_ABSENT_DEFECT_MIN_CONFIDENCE = 0.95
SUPPRESSED_OUTCOME = "defect-absent-suppressed"


def normalize_author_defect_presence(
    result: Any,
    parsed: dict[str, Any],
    hardened: Any,
) -> dict[str, Any]:
    """Require and normalize an explicit defect-presence attestation."""

    if not isinstance(result, dict) or not isinstance(result.get("defect_present"), bool):
        raise hardened.ReviewQualityError(
            "DCOIR repair author omitted boolean defect_present attestation"
        )
    normalized = dict(parsed)
    normalized["defect_present"] = bool(result["defect_present"])
    if not normalized["defect_present"]:
        normalized["action"] = "no_safe_single_line_fix"
        normalized["replacement"] = ""
    return normalized


def _suppression_confidence(author: dict[str, Any] | None) -> float:
    """Return a bounded finite confidence; malformed values never authorize suppression."""

    if not author:
        return 0.0
    raw = author.get("confidence", 0)
    if isinstance(raw, bool):
        return 0.0
    try:
        confidence = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        return 0.0
    return confidence


def apply_declined_suppression(
    item: dict[str, Any],
    author: dict[str, Any] | None,
    repair_marker: str,
) -> dict[str, Any]:
    """Annotate a declined repair with fail-closed defect-absence policy."""

    marker = item.get(repair_marker) if isinstance(item.get(repair_marker), dict) else {}
    marker["version"] = VERSION
    defect_absent = bool(author and author.get("defect_present") is False)
    confidence = _suppression_confidence(author)
    if defect_absent and confidence >= SUPPRESS_ABSENT_DEFECT_MIN_CONFIDENCE:
        marker.update(
            {
                "outcome": SUPPRESSED_OUTCOME,
                "defect_present": False,
                "defect_presence_confidence": confidence,
            }
        )
    elif defect_absent:
        marker.update(
            {
                "defect_present": False,
                "defect_presence_confidence": confidence,
                "suppression_declined": "defect-absence confidence below threshold",
            }
        )
    item[repair_marker] = marker
    return item


def safe_declined_author(author: dict[str, Any] | None) -> dict[str, Any] | None:
    """Hide low-confidence defect-absent model wording from publication."""

    if not author or author.get("defect_present") is not False:
        return author
    confidence = _suppression_confidence(author)
    if confidence >= SUPPRESS_ABSENT_DEFECT_MIN_CONFIDENCE:
        return author
    return None


def filter_suppressed_findings(
    findings: list[dict[str, Any]],
    repair_marker: str,
) -> tuple[list[dict[str, Any]], int]:
    kept: list[dict[str, Any]] = []
    suppressed = 0
    for item in findings:
        marker = item.get(repair_marker) if isinstance(item.get(repair_marker), dict) else {}
        if marker.get("outcome") == SUPPRESSED_OUTCOME:
            suppressed += 1
            continue
        kept.append(item)
    return kept, suppressed
