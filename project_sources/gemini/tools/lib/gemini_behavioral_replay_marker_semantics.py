from __future__ import annotations

import re
from typing import List

from .gemini_behavioral_replay_rejection_patterns import (
    DIRECT_REJECTION_PREFIX,
    GOVERNED_SOURCE_ACTION_SCOPE,
)
from .gemini_behavioral_replay_semantic_assertions import analyze_semantics, response_has_next_evidence_semantics
from .gemini_behavioral_replay_text_scoring import (
    _find_contextual_term_hits,
    _iter_term_occurrences,
    _occurrence_is_negated,
    _occurrence_is_quoted,
    _occurrence_is_rejected_after,
    _occurrence_is_rejected_before,
    normalize_text,
)


def _append_once(values: List[str], marker: str) -> None:
    if marker not in values:
        values.append(marker)


def _has_unresolved_gap_semantics(lowered: str) -> bool:
    unresolved = _find_contextual_term_hits(
        lowered, ["unresolved"], skip_negated=True, skip_quoted=True
    )
    if not unresolved:
        return False
    return bool(
        re.search(
            r"\b(?:"
            r"no\s+[^.!?;]{0,100}\b(?:has|have|was|were)\s+been\s+read\s+back"
            r"|(?:not|never)\s+[^.!?;]{0,60}\b(?:read\s+back|provided|available)"
            r"|(?:missing|unavailable|unread)\s+(?:direct\s+)?evidence"
            r"|visibility\s+gaps?|evidence\s+gaps?"
            r")\b",
            lowered,
        )
    )


def augment_semantic_marker_matches(
    response_text: str,
    markers: List[str],
    matched: List[str],
) -> List[str]:
    lowered = normalize_text(response_text)
    result = list(matched)

    if "workflow state" in markers and "workflow state" not in result and re.search(
        r"\b(?:does not|doesn't|doesnt|cannot|can't|can not)\s+"
        r"(?:establish|verify|confirm)\b[^.!?;]{0,80}\bworkflow state\b",
        lowered,
    ):
        _append_once(result, "workflow state")

    if "do not guess" in markers and "do not guess" not in result:
        for occurrence in _iter_term_occurrences(lowered, "will not guess"):
            if _occurrence_is_quoted(lowered, occurrence.start(), occurrence.end()):
                continue
            if _occurrence_is_rejected_before(lowered, occurrence.start()):
                continue
            if _occurrence_is_rejected_after(lowered, occurrence.end(), occurrence.start()):
                continue
            _append_once(result, "do not guess")
            break

    if "governed source" in markers:
        result = [value for value in result if value != "governed source"]
        for occurrence in _iter_term_occurrences(lowered, "governed source"):
            if _occurrence_is_quoted(lowered, occurrence.start(), occurrence.end()):
                continue
            prefix = lowered[max(0, occurrence.start() - 120):occurrence.start()]
            action = GOVERNED_SOURCE_ACTION_SCOPE.search(prefix)
            if action and DIRECT_REJECTION_PREFIX.search(prefix[max(0, action.start() - 40):action.start()]):
                continue
            if not action and (
                _occurrence_is_negated(lowered, occurrence.start())
                or _occurrence_is_rejected_before(lowered, occurrence.start())
                or _occurrence_is_rejected_after(lowered, occurrence.end(), occurrence.start())
            ):
                continue
            _append_once(result, "governed source")
            break

    if "do not claim" in markers and "do not claim" not in result:
        if analyze_semantics(response_text).has_no_claim_semantics():
            _append_once(result, "do not claim")

    if "interpret" in markers and "interpret" not in result:
        if _find_contextual_term_hits(
            lowered, ["interpretation"], skip_negated=True, skip_quoted=True
        ):
            _append_once(result, "interpret")

    unresolved_marker = "unresolved due to evidence gaps"
    if unresolved_marker in markers and unresolved_marker not in result:
        if _has_unresolved_gap_semantics(lowered):
            _append_once(result, unresolved_marker)

    next_evidence_marker = "next evidence"
    if next_evidence_marker in markers and next_evidence_marker not in result:
        if response_has_next_evidence_semantics(response_text):
            _append_once(result, next_evidence_marker)

    return result
