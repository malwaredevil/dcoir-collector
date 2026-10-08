"""Context-only marker helpers shared by required and forbidden replay scoring."""
from __future__ import annotations

import re

from .gemini_behavioral_replay_rejection_patterns import (
    BOUNDED_UNVERIFIED_SCOPE,
    COORDINATED_NEGATION_SCOPE,
    POST_UNSUPPORTED_SCOPE,
)
from .gemini_behavioral_replay_assertion_polarity import occurrence_is_asserted
from .gemini_behavioral_replay_quote_context import occurrence_is_backtick_wrapped, occurrence_is_quoted
from .gemini_behavioral_replay_text_scoring import (
    _iter_term_occurrences,
    normalize_text,
)


def marker_has_asserted_occurrence(
    response_text: str,
    marker: str,
    *,
    allow_quoted_single_tokens: bool = False,
    allow_markdown_code: bool = False,
) -> bool:
    lowered = normalize_text(response_text)
    for occurrence in _iter_term_occurrences(lowered, marker):
        quoted = occurrence_is_quoted(lowered, occurrence.start(), occurrence.end())
        if quoted:
            allowed_single_token = (
                allow_quoted_single_tokens and " " not in normalize_text(marker)
            )
            allowed_markdown = (
                allow_markdown_code
                and occurrence_is_backtick_wrapped(
                    lowered, occurrence.start(), occurrence.end()
                )
            )
            if not (allowed_single_token or allowed_markdown):
                continue
        if occurrence_is_asserted(lowered, occurrence.start(), occurrence.end()):
            return True
    return False


def marker_only_in_not_proven_bullets(response_text: str, marker: str) -> bool:
    target = normalize_text(marker)
    in_section = False
    seen = False
    seen_active = False
    for raw_line in str(response_text).splitlines():
        line = normalize_text(raw_line)
        if not line:
            continue
        if line.rstrip(":") == "what is not proven":
            in_section = True
            continue
        if in_section and raw_line.lstrip().startswith(("-", "*")):
            if target in line:
                seen = True
            continue
        in_section = False
        if target in line:
            seen_active = True
    return seen and not seen_active


def marker_only_in_bounded_rejection(response_text: str, marker: str) -> bool:
    lowered = normalize_text(response_text)
    seen = False
    for occurrence in _iter_term_occurrences(lowered, marker):
        if occurrence_is_quoted(lowered, occurrence.start(), occurrence.end()):
            continue
        clause_start = max(
            lowered.rfind(".", 0, occurrence.start()),
            lowered.rfind("!", 0, occurrence.start()),
            lowered.rfind("?", 0, occurrence.start()),
            lowered.rfind(";", 0, occurrence.start()),
        )
        prefix = lowered[max(clause_start + 1, occurrence.start() - 220):occurrence.start()]
        suffix = lowered[occurrence.end():occurrence.end() + 120]
        frame = BOUNDED_UNVERIFIED_SCOPE.search(prefix)
        if frame:
            scope = prefix[frame.end():]
            if not re.search(
                r"\b(?:but|however|yet|instead|so|therefore|thus|consequently)\b"
                r"|(?:,|\b(?:and|although|though|while|whereas)\b)\s*"
                r"(?:(?:and|or|although|though|while|whereas)\s+)?"
                r"(?:i|we|you|they|it|this|these|those|the(?:\s+[a-z0-9_-]+){1,4})\s+"
                r"(?:is|are|was|were|has|have|will|would|should|must|can)\b",
                scope,
            ):
                seen = True
                continue
        if COORDINATED_NEGATION_SCOPE.search(prefix):
            seen = True
            continue
        if POST_UNSUPPORTED_SCOPE.match(suffix):
            seen = True
            continue
        return False
    return seen
