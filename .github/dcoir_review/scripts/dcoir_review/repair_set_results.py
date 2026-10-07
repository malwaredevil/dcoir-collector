"""Stable publication-result ownership for coordinated verified repair sets."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from dcoir_review import repair_precision
from dcoir_review import repair_set_contract
from dcoir_review import repair_support

MAX_REPAIR_STATUS_NOTE_CHARS = 4000
_TRUNCATION_MARKER = "\n...[truncated by DCOIR repair-set budget]"


def _bounded(text: Any, limit: int) -> str:
    value = str(text or "")
    if len(value) <= limit:
        return value
    keep = max(0, limit - len(_TRUNCATION_MARKER))
    return value[:keep] + _TRUNCATION_MARKER


def _author_confidence(author: dict[str, Any] | None) -> float:
    """Return bounded finite confidence; malformed values never authorize suppression."""

    if not author:
        return 0.0
    raw = author.get("confidence", 0)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return 0.0
    confidence = float(raw)
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        return 0.0
    return confidence


def declined_item(
    finding: dict[str, Any],
    author: dict[str, Any] | None,
    reason: str,
    *,
    outcome: str = repair_set_contract.NO_SAFE_REPAIR_OUTCOME,
    author_model: str = "",
    author_tier: str = "",
) -> dict[str, Any]:
    """Return a verified finding with explicit coordinated-repair decline metadata."""

    item = repair_support._strip_legacy_model_finding_provenance(finding)
    path, line = repair_support._path_line(item)
    title, body = repair_support._fallback_display(item, path, line)
    if author and author.get("defect_present") is not False:
        title = str(author.get("display_title", "") or title)[:160]
        body = str(author.get("display_body", "") or body)[:2200]
    item["title"] = title
    item["body"] = body
    item["suggested_replacement"] = ""
    status_note = (
        "DCOIR Review verified the finding. A native coordinated repair was not published because "
        + (reason or "the repair-set pipeline could not prove a safe complete repair")
        + "."
    )
    item["fix_guidance"] = {
        "language": Path(path).suffix.lstrip(".") or "text",
        "notes": _bounded(status_note, MAX_REPAIR_STATUS_NOTE_CHARS),
    }
    confidence = _author_confidence(author)
    item[repair_support.REPAIR_MARKER] = {
        "version": repair_set_contract.MARKER_VERSION,
        "outcome": outcome,
        "path": path,
        "line": line,
        "author_model": author_model,
        "author_service_tier": author_tier,
        "author_confidence": confidence,
        "reason": reason[:800],
    }
    if author and author.get("defect_present") is False:
        item[repair_support.REPAIR_MARKER].update(
            {
                "defect_present": False,
                "defect_presence_confidence": confidence,
            }
        )
        if confidence >= repair_precision.SUPPRESS_ABSENT_DEFECT_MIN_CONFIDENCE:
            item[repair_support.REPAIR_MARKER]["outcome"] = repair_precision.SUPPRESSED_OUTCOME
    return item
