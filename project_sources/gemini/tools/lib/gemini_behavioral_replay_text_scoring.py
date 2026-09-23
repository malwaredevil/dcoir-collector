from __future__ import annotations

import re
from typing import Iterable, List


from .gemini_behavioral_replay_rejection_patterns import (
    NEGATION_PATTERN,
    POST_MARKER_EVIDENCE_BOUNDARY_PATTERN,
    POST_MARKER_REJECTION_NOUN_PHRASE,
    POST_MARKER_REJECTION_PATTERN,
    PRE_MARKER_REJECTION_FRAME_PATTERN,
    REJECTED_ASSERTION_PATTERN,
    REJECTION_SCOPE_LIMIT,
)

UNSUPPORTED_CERTAINTY_TERMS = [
    "definitely",
    "guarantee",
    "guaranteed",
    "guarantees",
]

INVENTED_TOOL_TERMS = [
    "invoke-dcoir",
    "enterprise_web_search_status",
    "planner_payloads",
    "routing_state",
]

CONTRADICTION_PAIRS = [
    ("wait", "kill"),
    ("rerun", "leave it alone"),
    ("cleanup now", "do not clean up yet"),
]

FINAL_SECTION_HEADERS = [
    "bluf",
    "facts and sources",
    "analysis",
    "syntax verification",
    "singular triage command",
    "analyst scratchpad",
    "executive summary",
    "benign rationale",
    "supporting evidence",
    "tuning recommendation",
    "residual uncertainty",
    "timeline",
    "root cause or true source",
    "impact and scope",
    "containment and remediation recommendations",
    "hunting pivots and derived indicators",
    "what is known",
    "what is blocked",
    "what evidence paths were exhausted",
    "why scope cannot be declared",
    "best next steps",
    "required telemetry or artifacts",
    "why containment or troubleshooting is not yet justified",
    "package/deployment",
    "package deployment",
    "package and deployment",
    "endpoint execution",
    "endpoint response-action execution",
    "artifact retrieval",
    "retrieve",
    "evidence interpretation",
    "interpret",
    "cleanup",
]

AMBIGUOUS_LIST_SECTION_HEADERS = {"retrieve", "interpret", "cleanup"}

QUOTE_CHARS = {'"', "'", "`"}


def normalize_text(text: str) -> str:
    return " ".join(str(text).lower().split())


def _term_variants(term: str) -> List[str]:
    normalized = normalize_text(term)
    variants = {normalized}
    if "guarantee exact filtering" in normalized:
        variants.add(normalized.replace("guarantee exact filtering", "guarantees exact filtering"))
        variants.add(normalized.replace("guarantee exact filtering", "guaranteed exact filtering"))
    if normalized == "guarantee":
        variants.update({"guaranteed", "guarantees"})
    if normalized == "not verified":
        variants.add("did not verify")
    if normalized == "one controlled repair step":
        variants.add("one controlled broadening step")
    return sorted(variants, key=len, reverse=True)


def _iter_term_occurrences(text: str, term: str) -> Iterable[re.Match[str]]:
    for variant in _term_variants(term):
        pattern = re.compile(rf"(?<![a-z0-9_-]){re.escape(variant)}(?![a-z0-9_-])")
        yield from pattern.finditer(text)


def _occurrence_is_quoted(text: str, start: int, end: int) -> bool:
    if start <= 0 or end >= len(text):
        return False
    before = text[start - 1]
    after = text[end]
    if before in QUOTE_CHARS and after == before:
        return True

    # Double quotes and backticks can be paired reliably. Pair them in source
    # order so a closing quote from one value cannot become the opener for the
    # next value and incorrectly swallow intervening prose.
    for quote in ('"', '`'):
        positions = [index for index, char in enumerate(text) if char == quote]
        for offset in range(0, len(positions) - 1, 2):
            opener, closer = positions[offset], positions[offset + 1]
            if opener < start and end <= closer:
                return True

    # Apostrophes are common in contractions, so only treat a single-quoted
    # marker as quoted when its opening quote is immediately adjacent and the
    # closing quote follows only short punctuation.
    opener = text.rfind("'", max(0, start - 2), start)
    closer = text.find("'", end, min(len(text), end + 6))
    if opener != -1 and closer != -1:
        prefix = text[opener + 1:start]
        trailing = text[end:closer]
        if not prefix.strip() and len(trailing) <= 4 and all(char in " ,.;:!?" for char in trailing):
            return True
    return False


def _occurrence_is_backtick_wrapped(text: str, start: int, end: int) -> bool:
    if start > 0 and end < len(text) and text[start - 1] == "`" and text[end] == "`":
        return True
    positions = [index for index, char in enumerate(text) if char == "`"]
    for offset in range(0, len(positions) - 1, 2):
        opener, closer = positions[offset], positions[offset + 1]
        if opener < start and end <= closer:
            return True
    return False


def _occurrence_is_negated(text: str, start: int) -> bool:
    context = text[max(0, start - 40):start]
    context = re.sub(r"[*_]+", "", context)
    return bool(NEGATION_PATTERN.search(context) or REJECTED_ASSERTION_PATTERN.search(context))


_COORDINATED_AFFIRMATIVE_PREDICATE = re.compile(
    r"^(?:(?:clearly|definitely|certainly|explicitly|actually|also|still|now|then)\s+){0,3}"
    r"(?:guarantees?|guaranteed|confirms|confirmed|claims|claimed|states|stated|asserts|asserted|"
    r"concludes|concluded|proves|proved|establishes|established|shows|showed|indicates|indicated|"
    r"means|meant|recommends|recommended|requires|required|needs|needed|believes|believed|"
    r"will|would|can|could|must|should|is|are|was|were|has|have|does|do)\b"
)

_COORDINATED_AFFIRMATIVE_SUBJECT_PREDICATE = re.compile(
    r"^(?:i|we|you|they|he|she|it|this|that|these|those|"
    r"the(?:\s+[a-z0-9_-]+){1,3}|(?!(?:a|an|the)\b)[a-z0-9_-]+)\s+"
    r"(?:(?:clearly|definitely|certainly|explicitly|actually|also|still|now|then)\s+){0,3}"
    r"(?:guarantee(?:s|d)?|confirm(?:s|ed)?|claim(?:s|ed)?|state(?:s|d)?|assert(?:s|ed)?|"
    r"conclude(?:s|d)?|prove(?:s|d)?|establish(?:es|ed)?|show(?:s|ed)?|indicate(?:s|d)?|"
    r"mean(?:s|t)?|recommend(?:s|ed)?|require(?:s|d)?|need(?:s|ed)?|believe(?:s|d)?|"
    r"will|would|can|could|must|should|is|are|was|were|has|have|does|do)\b"
)


def _rejection_frame_governs_marker(context: str, marker_tail: str) -> bool:
    frames = list(PRE_MARKER_REJECTION_FRAME_PATTERN.finditer(context))
    if not frames:
        return False
    frame = frames[-1]
    tail = context[frame.end():]
    if len(tail) > REJECTION_SCOPE_LIMIT:
        return False

    frame_text = normalize_text(frame.group(0))
    frame_opens_that_complement = bool(re.search(r"\bthat\s*$", frame_text))
    coordinators = list(re.finditer(r"\b(?:and|or)\b", tail))
    for coordinator in reversed(coordinators):
        suffix = normalize_text(tail[coordinator.end():] + " " + marker_tail)
        if not suffix:
            continue
        prefix = tail[:coordinator.start()]
        has_that_complement = frame_opens_that_complement or bool(
            re.search(r"\bthat\b", prefix)
        )
        if re.match(
            r"^confirmed\s+(?!(?:the|a|an|that|this)\b)[a-z0-9_-]+(?:\s*[,.;:]|$)",
            suffix,
        ) and (
            re.search(r"\b(?:conclusions?|claims?|assertions?|inferences?)\s+of\b", prefix)
            or (
                re.search(r"\b(?:prove|indicate|show|establish|demonstrate|support)\b", frame_text)
                and "," in prefix
            )
        ):
            continue
        independently_predicated = bool(
            _COORDINATED_AFFIRMATIVE_PREDICATE.match(suffix)
            or _COORDINATED_AFFIRMATIVE_SUBJECT_PREDICATE.match(suffix)
        )
        if independently_predicated and not has_that_complement:
            return False
    return True


def _occurrence_is_rejected_before(text: str, start: int) -> bool:
    # Broad assertion rejection is intentionally separate from the narrow
    # negation helper because execution-lane scoring has relationship-specific
    # discourse rules. Applying broad rejection there can hide an affirmative
    # mix after an earlier negated phrase in the same clause.
    clause_start = max(
        text.rfind(".", 0, start),
        text.rfind("!", 0, start),
        text.rfind("?", 0, start),
        text.rfind(";", 0, start),
        text.rfind("\n", 0, start),
    )
    context = text[max(clause_start + 1, start - 220):start]
    context = re.sub(r"[*_]+", "", context)
    contrasts = list(
        re.finditer(r"\b(?:but|however|yet|nevertheless|instead(?!\s+of\b))\b", context)
    )
    if contrasts:
        context = context[contrasts[-1].end():]

    marker_tail = normalize_text(text[start:start + 96])
    if re.search(r"\b(?:and|or)(?:\s+(?:(?:i|we)\s+)?(?:will|would|should|must|can|could))?\s*[\x60]*$", context) and re.match(
        r"^(?:not|do not|does not|did not|will not|would not|cannot|can't|must not|should not)\b",
        marker_tail,
    ):
        context = ""

    # Reset rejection scope only at clear independent clause boundaries.
    clause_boundary = re.compile(
        r"^\s*(?:(?:and|or|but|so)\s+)?(?:"
        r"(?:i|we|you|they|it|(?:this|these|those)(?:\s+[a-z0-9_-]+){0,2}|the(?:\s+[a-z0-9_-]+){1,5})\s+"
        r"(?:will|would|should|can|cannot|can't|must|do|does|did|am|are|is|have|has|need|needs|remain|remains|stay|stays|recommend|suggest)\b"
        r"|(?!(?:that|which|who|and|or|but|so)\b)(?:[a-z0-9_-]+(?:\s+[a-z0-9_-]+){0,2})\s+(?:will|would|should|can|cannot|can't|must|do|does|did|am|are|is|have|has|need|needs|remain|remains|stay|stays)\b"
        r"|(?:please\s+)?(?:provide|send|run|execute|read|retrieve|upload|review|collect|use|check|verify|focus|determine)\b"
        r")"
    )
    boundary_positions = [match.end() for match in re.finditer(r"[:,]", context)]
    for boundary_end in reversed(boundary_positions):
        suffix = context[boundary_end:]
        candidate = suffix + " " + marker_tail
        if (
            re.search(r"\b(?:cannot|can't|can not)\s+conclude\b", context[:boundary_end])
            and re.search(r",\s*(?:and|or)\s+that\b", candidate)
        ):
            continue
        if clause_boundary.search(candidate):
            context = suffix
            break

    return _rejection_frame_governs_marker(context, marker_tail)

def _occurrence_is_rejected_after(text: str, end: int, start: int | None = None) -> bool:
    paragraph_end = text.find("\n", end)
    limit = min(len(text), end + 240)
    if paragraph_end != -1:
        limit = min(limit, paragraph_end)
    context = text[end:limit]
    if POST_MARKER_REJECTION_PATTERN.search(context):
        return True
    if POST_MARKER_EVIDENCE_BOUNDARY_PATTERN.match(context):
        return True

    # A short noun phrase may defer the rejection predicate.
    if re.match(
        rf"^\s+{POST_MARKER_REJECTION_NOUN_PHRASE}\s+"
        r"(?:(?:is|are|was|were)\s+"
        r"(?:not\s+(?:supported|justified|established|proven)|unsupported|unjustified|unproven|premature)"
        r"|(?:cannot|can't|can not)\s+be\s+(?:supported|justified|established|proven))\b",
        context,
    ):
        return True

    # Coordinated gerund subjects can defer one rejection predicate across both
    # claims: "Declaring that X or asserting Y is not supported."
    if start is not None:
        before = text[max(0, start - 96):start]
        if re.search(
            r"\b(?:declaring|asserting|claiming|stating|concluding)\s+that\s*$",
            before,
        ) and re.match(
            r"^\s+(?:or|and)\s+(?:asserting|declaring|claiming|stating|concluding)\b"
            r"[^.!?;]{0,160}\b(?:is|are|was|were)\s+not\s+"
            r"(?:supported|justified|established|proven)\b",
            context,
        ):
            return True
    return False


def _find_contextual_term_hits(
    text: str,
    terms: List[str],
    *,
    skip_negated: bool = False,
    skip_quoted: bool = False,
    allow_quoted_single_tokens: bool = False,
    allow_markdown_code: bool = False,
    reject_unverified: bool = False,
) -> List[str]:
    hits: List[str] = []
    for term in terms:
        for match in _iter_term_occurrences(text, term):
            quoted = _occurrence_is_quoted(text, match.start(), match.end())
            if skip_quoted and quoted:
                allowed_single_token = (
                    allow_quoted_single_tokens
                    and not re.search(r"\s", normalize_text(term))
                )
                allowed_markdown = (
                    allow_markdown_code
                    and _occurrence_is_backtick_wrapped(
                        text, match.start(), match.end()
                    )
                )
                if not (allowed_single_token or allowed_markdown):
                    continue
            if skip_negated and (
                _occurrence_is_negated(text, match.start())
                or _occurrence_is_rejected_before(text, match.start())
            ):
                continue
            if skip_negated and _occurrence_is_rejected_after(text, match.end(), match.start()):
                continue
            if reject_unverified and re.match(
                r"^\s+(?:is|are|was|were)\s+(?:not\s+verified|unverified)\b",
                text[match.end():match.end() + 80],
            ):
                continue
            hits.append(term)
            break
    return hits


def _iter_clauses(text: str) -> Iterable[str]:
    for clause in re.split(r"(?:\r?\n)+|(?<=[.!?;])\s+", str(text)):
        normalized = normalize_text(clause)
        if normalized:
            yield normalized


def _normalized_header_line(line: str) -> str:
    value = str(line).strip().lower()
    value = re.sub(r"^[#>*_\-\s]+", "", value)
    value = re.sub(r"^\d{1,3}[.)]\s+", "", value)
    value = re.sub(r"[*_`]+", "", value)
    value = value.rstrip(":").strip()
    return " ".join(value.split())


def _line_is_list_prefixed(line: str) -> bool:
    value = str(line).lstrip()
    return bool(re.match(r"^(?:[-*+]\s+|\d{1,3}[.)]\s+)", value))


def _final_section_header_for_line(line: str) -> str | None:
    normalized = _normalized_header_line(line)
    is_list_prefixed = _line_is_list_prefixed(line)
    is_numbered_list_item = bool(re.match(r"^\s*\d{1,3}[.)]\s+", str(line)))
    if normalized in FINAL_SECTION_HEADERS:
        if is_list_prefixed and not is_numbered_list_item and normalized in AMBIGUOUS_LIST_SECTION_HEADERS:
            return None
        return normalized
    for header in FINAL_SECTION_HEADERS:
        if is_list_prefixed and not is_numbered_list_item and header in AMBIGUOUS_LIST_SECTION_HEADERS:
            continue
        if re.match(rf"^{re.escape(header)}\s*[:\-–—]\s*.+$", normalized):
            return header
    return None


def duplicate_final_sections(response_text: str) -> List[str]:
    counts = {header: 0 for header in FINAL_SECTION_HEADERS}
    for line in str(response_text).splitlines():
        header = _final_section_header_for_line(line)
        if header is not None:
            counts[header] += 1
    return [header for header, count in counts.items() if count > 1]
