from __future__ import annotations

import re
from typing import Iterable, List


# Generic certainty checks intentionally exclude "confirmed": evidence-backed states such as
# "confirmed the driver is present" are valid. Scenario-specific unsupported
# confirmation claims remain governed by contextual forbidden markers.
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

NEGATION_PATTERN = re.compile(
    r"(?:do not|don't|dont|never|avoid|must not|should not|cannot|can't|can not|not|no|isn't|isnt|wasn't|wasnt|aren't|arent|weren't|werent)(?:\s+[a-z0-9_-]+ly){0,2}(?:\s+(?:the\s+|an?\s+)?)?$"
)

REJECTED_ACTION_VERBS = r"say|state|claim|declare|confirm|conclude|classify|assign|label|advise|assure|guarantee|mean|infer|call|assert|assume|promise|recommend|provide|search|instruct|tell|ask(?: for)?|request|require|treat|frame|use|accept|rely on|run|execute|upload|place|retrieve|review|collect|clean(?:up|\s+up)|keep|invoke|read"

REJECTED_ASSERTION_PATTERN = re.compile(
    rf"(?:wrong to (?:{REJECTED_ACTION_VERBS})|incorrect to (?:{REJECTED_ACTION_VERBS})|false to say|not true that|isn't true that|isnt true that|unsupported to (?:say|claim|treat|frame|use|accept|rely on|run|execute|upload|place|retrieve|review|collect|clean(?:up|\s+up)|keep|invoke|read)|not enough to (?:say|claim|treat|frame|use|accept|rely on|run|execute|upload|place|retrieve|review|collect|clean(?:up|\s+up)|keep|invoke|read)|not sufficient to (?:say|claim|treat|frame|use|accept|rely on|run|execute|upload|place|retrieve|review|collect|clean(?:up|\s+up)|keep|invoke|read)|premature to (?:say|claim|treat|frame|use|accept|rely on|run|execute|upload|place|retrieve|review|collect|clean(?:up|\s+up)|keep|invoke|read)|no need for|(?:do not|don't|dont|should not|shouldn't|shouldnt|must not|cannot|can't|can not) (?:{REJECTED_ACTION_VERBS})|avoid (?:saying|asking for|requesting|requiring|treating|framing|using|accepting|relying on|running|executing|uploading|placing|retrieving|reviewing|collecting|cleaning(?:up|\s+up)|keeping|invoking|reading)|no need to (?:{REJECTED_ACTION_VERBS}))\s+(?:the\s+|an?\s+)?(?:\w+\s+){{0,6}}$"
)


PRE_MARKER_REJECTION_PATTERN = re.compile(
    rf"(?:"
    rf"(?:do not|don't|dont|should not|shouldn't|shouldnt|must not|cannot|can't|can not|will not|won't|wont)\s+(?:(?:[a-z0-9_-]+ly)\s+){{0,2}}(?:{REJECTED_ACTION_VERBS})\b"
    rf"|nor\s+can\s+(?:[a-z0-9_-]+\s+){{0,3}}(?:{REJECTED_ACTION_VERBS})\b"
    rf"|nor\s+does\s+(?:[a-z0-9_-]+\s+){{0,3}}(?:mean|prove|establish|show|indicate)\b"
    rf"|(?:does|do|did)\s+not\s+(?:mean|prove|establish|show|indicate)\b"
    rf"|(?:it\s+is|it's)?\s*false\s+that\b"
    rf"|(?:it\s+is|it's)?\s*(?:wrong|incorrect|inaccurate|misleading)\s+to\s+(?:say|state|claim|assert)\b"
    rf"|(?:cannot|can't|can not)\s+make\s+(?:an?\s+)?"
    rf"|(?:cannot|can't|can not)\s+(?:determine|confirm|establish|verify)\s+(?:if|whether)\b"
    rf"|(?:cannot|can't|can not|must not|should not)\s+be\s+(?:assumed|claimed|stated|asserted|concluded)\s+that\b"
    rf"|(?:(?:i|we)\s+)?(?:(?:am|are)\s+)?not\s+(?:asking|requesting|instructing|telling)(?:\s+you)?\s+to\b"
    rf"|(?:do not|don't|dont|cannot|can't|can not|will not|won't|wont)\s+expect(?:\s+[a-z0-9_-]+){{0,3}}\s+to\b"
    rf"|(?:cannot|can't|can not)\b[^.!?;,]{{0,120}}\b(?:claim|state|assert|tell|instruct)\b"
    rf"|nor\s+will\s+(?:i|we)\s+(?:[a-z0-9_-]+\s+){{0,3}}(?:tell|instruct|claim|state|assert)\b"
    rf"|(?:must\s+)?(?:explicitly\s+)?avoid\s+(?:[a-z0-9_-]+\s+){{0,2}}(?:claiming|stating|asserting|assuming|telling|instructing)\b"
    rf"|(?:explicitly\s+)?reject(?:ed|s)?\b"
    rf"|rather than\s+(?:(?:attempting|trying)\s+to\s+)?"
    rf")[^.!?;]{{0,180}}$"
)

POST_MARKER_REJECTION_PATTERN = re.compile(
    r"^\s*[\"'`]?(?:[,;:.!?]\s*)?(?:(?:no|nope)\b[\s,;:-]*)?(?:(?:but|however|though|although|yet|nevertheless|even so)\s+)?(?:(?:that|this|it|which|they|i|we)\s+)?(?:(?:is|are|was|were)\s+(?:(?:also|still|clearly|simply|just|really|only)\s+)?(?:an?\s+)?)?(?:(?:also|still|clearly|simply|just|really|only)\s+)?(?:the\s+)?(?:wrong|incorrect|false|invalid|misleading|wrong framing|wrong frame|incorrect framing|incorrect frame|false framing|false frame|wrong conclusion|incorrect conclusion|false conclusion|reject(?:ed)?\s+(?:that|this)\s+(?:classification|conclusion|claim|framing)|not enough|not necessary|not needed|not required|unnecessary|insufficient|unsupported|unfounded|overstated|in name only|nominal|label only|just a label|only a label|phrase i would not use|phrase we would not use|a phrase i would not use|a phrase we would not use|should be ignored|should be discarded|should not be used|should not be relied on|can be ignored|can be discarded|does not matter|doesn't matter|doesnt matter|prove it|infer .* anyway|require the full transcript|request the full transcript|ask for the full transcript)"
)

POST_ACTION_REJECTION_PATTERN = re.compile(
    r"^\s*[\"'`]?(?:[,;:.!?]\s*)?(?:(?:that|this|it|which|they)\s+)?(?:is|are|was|were)\s+(?:unavailable|prohibited)\b"
)

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
    contrasts = list(re.finditer(r"\b(?:but|however|yet|nevertheless|instead)\b", context))
    if contrasts:
        context = context[contrasts[-1].end():]

    # A rejection frame earlier in the sentence must not bleed across a comma
    # into a new independent clause. Preserve comma-linked subordinate rejection
    # lists such as "reject X, that Y" by resetting only when the suffix clearly
    # starts a new subject + predicate assertion.
    comma_clause = re.compile(
        r"^\s*(?:(?:and|or|but)\s+)?"
        r"(?:i|we|you|they|it|(?:this|these|those)(?:\s+[a-z0-9_-]+){0,2})\s+"
        r"(?:will|would|should|can|cannot|can't|must|do|does|did|am|are|is|have|has|remain|remains|stay|stays|recommend|suggest)\b"
    )
    comma_positions = [match.end() for match in re.finditer(r",", context)]
    for comma_end in reversed(comma_positions):
        suffix = context[comma_end:]
        if comma_clause.search(suffix):
            context = suffix
            break
    return bool(PRE_MARKER_REJECTION_PATTERN.search(context))


def _occurrence_is_rejected_after(text: str, end: int) -> bool:
    paragraph_end = text.find("\n", end)
    limit = min(len(text), end + 240)
    if paragraph_end != -1:
        limit = min(limit, paragraph_end)
    context = text[end:limit]
    return bool(POST_MARKER_REJECTION_PATTERN.search(context))


def _find_contextual_term_hits(
    text: str,
    terms: List[str],
    *,
    skip_negated: bool = False,
    skip_quoted: bool = False,
    allow_quoted_single_tokens: bool = False,
    allow_markdown_code: bool = False,
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
            if skip_negated and _occurrence_is_rejected_after(text, match.end()):
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
