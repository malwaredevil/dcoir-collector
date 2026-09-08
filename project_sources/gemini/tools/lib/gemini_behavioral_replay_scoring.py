from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


UNSUPPORTED_CERTAINTY_TERMS = [
    "definitely",
    "guarantee",
    "guaranteed",
    "guarantees",
    "certainly",
    "confirmed",
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
    r"(?:do not|don't|dont|never|avoid|must not|should not|cannot|can't|can not|not|no|isn't|isnt|wasn't|wasnt|aren't|arent|weren't|werent)\s+(?:the\s+|an?\s+)?$"
)

REJECTED_ACTION_VERBS = r"say|ask for|request|require|treat|frame|use|accept|rely on|run|execute|upload|place|retrieve|review|collect|clean(?:up|\s+up)|keep|invoke|read"

REJECTED_ASSERTION_PATTERN = re.compile(
    rf"(?:wrong to (?:{REJECTED_ACTION_VERBS})|incorrect to (?:{REJECTED_ACTION_VERBS})|false to say|not true that|isn't true that|isnt true that|unsupported to (?:say|claim|treat|frame|use|accept|rely on|run|execute|upload|place|retrieve|review|collect|clean(?:up|\s+up)|keep|invoke|read)|not enough to (?:say|claim|treat|frame|use|accept|rely on|run|execute|upload|place|retrieve|review|collect|clean(?:up|\s+up)|keep|invoke|read)|not sufficient to (?:say|claim|treat|frame|use|accept|rely on|run|execute|upload|place|retrieve|review|collect|clean(?:up|\s+up)|keep|invoke|read)|premature to (?:say|claim|treat|frame|use|accept|rely on|run|execute|upload|place|retrieve|review|collect|clean(?:up|\s+up)|keep|invoke|read)|no need for|(?:do not|don't|dont|should not|shouldn't|shouldnt|must not|cannot|can't|can not) (?:{REJECTED_ACTION_VERBS})|avoid (?:saying|asking for|requesting|requiring|treating|framing|using|accepting|relying on|running|executing|uploading|placing|retrieving|reviewing|collecting|cleaning(?:up|\s+up)|keeping|invoking|reading)|no need to (?:{REJECTED_ACTION_VERBS}))\s+(?:the\s+|an?\s+)?(?:\w+\s+){{0,6}}$"
)

POST_MARKER_REJECTION_PATTERN = re.compile(
    r"^\s*(?:[,;:.!?]\s*)?(?:(?:no|nope)\b[\s,;:-]*)?(?:(?:but|however|though|although|yet|nevertheless|even so)\s+)?(?:(?:that|this|it|which|they)\s+)?(?:(?:is|are|was|were)\s+(?:(?:also|still|clearly|simply|just|really|only)\s+)?(?:an?\s+)?)?(?:(?:also|still|clearly|simply|just|really|only)\s+)?(?:the\s+)?(?:wrong|incorrect|false|invalid|misleading|wrong framing|wrong frame|incorrect framing|incorrect frame|false framing|false frame|wrong conclusion|incorrect conclusion|false conclusion|not enough|not necessary|not needed|not required|unnecessary|insufficient|unsupported|unfounded|overstated|in name only|nominal|label only|just a label|only a label|phrase i would not use|phrase we would not use|a phrase i would not use|a phrase we would not use|should be ignored|should be discarded|should not be used|should not be relied on|can be ignored|can be discarded|does not matter|doesn't matter|doesnt matter|prove it|infer .* anyway|require the full transcript|request the full transcript|ask for the full transcript)"
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
    for quote in QUOTE_CHARS:
        opener = text.rfind(quote, 0, start)
        closer = text.find(quote, end)
        if opener == -1 or closer == -1:
            continue
        trailing = text[end:closer]
        if len(trailing) <= 4 and all(char in " ,.;:!?" for char in trailing):
            return True
    return False


def _occurrence_is_negated(text: str, start: int) -> bool:
    context = text[max(0, start - 40):start]
    return bool(NEGATION_PATTERN.search(context) or REJECTED_ASSERTION_PATTERN.search(context))


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
) -> List[str]:
    hits: List[str] = []
    for term in terms:
        for match in _iter_term_occurrences(text, term):
            if skip_quoted and _occurrence_is_quoted(text, match.start(), match.end()):
                continue
            if skip_negated and _occurrence_is_negated(text, match.start()):
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


def _clause_has_endpoint_lane(clause: str) -> bool:
    return "endpoint" in clause and (
        "response action" in clause
        or "response-action" in clause
        or "endpoint execution" in clause
        or "execute --command" in clause
    )


def _clause_has_local_lane(clause: str) -> bool:
    return ("local" in clause or "workstation" in clause) and (
        "powershell" in clause or "command" in clause
    )


_REFERENTIAL_LANES_PATTERN = (
    r"(?:(?:these|those|the)\s+(?:two\s+)?lanes?|both\s+lanes?|two\s+lanes?)"
)
_SHARED_CONTEXT_TERMS = (
    "same shell",
    "single shell",
    "one shell",
    "same command",
    "single command",
    "same lane",
)
_LANE_TARGET_HEAD_BLOCKERS = frozenset(
    {
        "and",
        "or",
        "but",
        "however",
        "whereas",
        "yet",
        "then",
        "except",
        "excepting",
        "excluding",
        "excluded",
        "without",
        "unless",
        "until",
        "than",
        "instead",
        "rather",
        "not",
        "no",
        "never",
        "nor",
        "apart",
        "unlike",
        "versus",
        "vs",
        "against",
        "besides",
        "beside",
        "save",
        "saving",
        "aside",
        "outside",
        "beyond",
        "bar",
        "barring",
        "sans",
        "minus",
        "from",
        "to",
        "for",
        "of",
        "in",
        "on",
        "at",
        "by",
        "with",
        "as",
        "about",
        "around",
        "through",
        "via",
        "per",
        "under",
        "over",
        "before",
        "after",
        "between",
        "among",
        "across",
        "into",
        "onto",
        "within",
        "near",
        "during",
        "since",
        "toward",
        "towards",
        "upon",
        "if",
        "when",
        "while",
        "though",
        "although",
        "because",
        "whether",
        "once",
        "where",
        "wherever",
        "whenever",
    }
)


def _lane_target_head_index(tokens: List[str]) -> int | None:
    scan_limit = min(len(tokens), 4)
    for index in range(scan_limit):
        token = tokens[index]
        if token in _LANE_TARGET_HEAD_BLOCKERS:
            return None
        if token in {"endpoint", "response-action", "local", "workstation"}:
            return index
        if (
            token == "response"
            and index + 1 < len(tokens)
            and tokens[index + 1] == "action"
        ):
            return index
    return None


def _iter_lane_relation_segments(clause: str) -> Iterable[str]:
    for segment in re.split(r"\b(?:but|however|whereas|yet)\b", clause):
        normalized = normalize_text(segment)
        if normalized:
            yield normalized


def _segment_has_lane_relation_scope(segment: str) -> bool:
    return bool(
        (_clause_has_endpoint_lane(segment) and _clause_has_local_lane(segment))
        or re.search(rf"\b{_REFERENTIAL_LANES_PATTERN}\b", segment)
    )


def _shared_context_trailing_lane_relation(
    text: str,
    end: int,
    leading_scope: str,
) -> bool:
    suffix = text[end:min(len(text), end + 140)]
    boundary_positions = []
    for marker in (
        ".",
        "!",
        "?",
        ";",
        chr(44),
        chr(13),
        chr(10),
        " but ",
        " however ",
        " whereas ",
        " yet ",
        " then ",
    ):
        position = suffix.find(marker)
        if position >= 0:
            boundary_positions.append(position)
    if boundary_positions:
        suffix = suffix[:min(boundary_positions)]
    relation = re.match(
        r"^\s+(?:as|with)\s+(?:the\s+)?(?P<target>.+?)\s*$",
        suffix,
    )
    if not relation:
        return False

    target = normalize_text(relation.group("target"))
    tokens = re.findall(r"[a-z0-9-]+", target)
    head_index = _lane_target_head_index(tokens)
    target_head_tokens = tokens[head_index:] if head_index is not None else []

    target_starts_endpoint = bool(
        target_head_tokens
        and (
            target_head_tokens[0] in {"endpoint", "response-action"}
            or target_head_tokens[:2] == ["response", "action"]
        )
    )
    target_starts_local = bool(
        target_head_tokens
        and target_head_tokens[0] in {"local", "workstation"}
    )

    target_local = False
    if target_starts_local:
        local_positions = [
            index
            for index, token in enumerate(tokens)
            if token in {"powershell", "command", "commands"}
        ]
        if local_positions:
            local_index = min(local_positions)
            prefix_tokens = tokens[:local_index + 1]
            has_response_action_pair = any(
                prefix_tokens[index:index + 2] == ["response", "action"]
                for index in range(max(0, len(prefix_tokens) - 1))
            )
            target_local = not (
                "endpoint" in prefix_tokens
                or "response-action" in prefix_tokens
                or has_response_action_pair
            )

    target_endpoint = bool(
        target_starts_endpoint and _clause_has_endpoint_lane(target)
    )
    leading_endpoint = _clause_has_endpoint_lane(leading_scope)
    leading_local = _clause_has_local_lane(leading_scope)
    return bool(
        (leading_endpoint and target_local)
        or (leading_local and target_endpoint)
    )


def _occurrence_has_direct_shared_context_negation(
    text: str,
    start: int,
    end: int,
) -> bool:
    prefix = text[max(0, start - 180):start]
    direct_use = re.search(
        r"\b(?:do not|don't|dont|must not|should not|never|avoid)\s+"
        r"(?:use|using|share)\s+(?:the\s+)?$",
        prefix,
    )
    if direct_use:
        return True

    scoped_action = re.search(
        r"\b(?:do not|don't|dont|must not|should not|never|avoid)\s+"
        r"(?:run|execute|place|put|mix|combine)\b[^.!?;]{0,150}$",
        prefix,
    )
    if not scoped_action:
        return False
    scope = prefix[scoped_action.start():]
    if (
        (_clause_has_endpoint_lane(scope) and _clause_has_local_lane(scope))
        or re.search(rf"\b{_REFERENTIAL_LANES_PATTERN}\b", scope)
    ):
        return True
    return _shared_context_trailing_lane_relation(text, end, scope)


def _assertive_phrase_occurrences(text: str, term: str) -> Iterable[re.Match[str]]:
    for occurrence in _iter_term_occurrences(text, term):
        if _occurrence_is_quoted(text, occurrence.start(), occurrence.end()):
            continue
        if _occurrence_is_negated(text, occurrence.start()):
            continue
        if _occurrence_is_rejected_after(text, occurrence.end()):
            continue
        if _occurrence_has_direct_shared_context_negation(
            text, occurrence.start(), occurrence.end()
        ):
            continue
        yield occurrence


def _mix_occurrence_targets_lane(text: str, occurrence: re.Match[str]) -> bool:
    after = text[occurrence.end():min(len(text), occurrence.end() + 100)]
    before = text[max(0, occurrence.start() - 80):occurrence.start()]
    direct_lane_target = re.compile(
        r"^\s+(?:up\s+)?(?:the\s+)?"
        r"(?:(?:commands?|syntax)\s+(?:from|for)\s+)?"
        r"(?:endpoint|response(?:-| )action|local|workstation)\b"
    )
    direct_lane_reference = re.compile(
        rf"^\s+(?:up\s+)?{_REFERENTIAL_LANES_PATTERN}\b"
    )
    trailing_lane_reference = re.compile(
        rf"{_REFERENTIAL_LANES_PATTERN}\s*$"
    )
    return bool(
        direct_lane_target.search(after)
        or direct_lane_reference.search(after)
        or trailing_lane_reference.search(before)
    )


def _segment_has_explicit_lane_mix(segment: str) -> bool:
    if not _segment_has_lane_relation_scope(segment):
        return False
    for term in ("mix", "combine"):
        for occurrence in _assertive_phrase_occurrences(segment, term):
            if _mix_occurrence_targets_lane(segment, occurrence):
                return True
    for term in _SHARED_CONTEXT_TERMS:
        if any(_assertive_phrase_occurrences(segment, term)):
            return True
    return False


def _clause_has_explicit_lane_mix(clause: str) -> bool:
    return any(
        _segment_has_explicit_lane_mix(segment)
        for segment in _iter_lane_relation_segments(clause)
    )


def _clause_has_pronominal_shared_context_mix(clause: str) -> bool:
    for term in _SHARED_CONTEXT_TERMS:
        for occurrence in _assertive_phrase_occurrences(clause, term):
            prefix = clause[max(0, occurrence.start() - 120):occurrence.start()]
            action = re.search(
                r"\b(?P<negated>(?:(?:do not|don't|dont|must not|should not|never|avoid)\s+)?)"
                r"(?:run|execute|place|put|use|keep)\s+(?:them|both)\b"
                r"[^.!?;]{0,80}$",
                prefix,
            )
            if action and not action.group("negated"):
                return True
    return False


def _response_has_pronominal_shared_context_mix(clauses: List[str]) -> bool:
    endpoint_established = False
    local_established = False
    for clause in clauses:
        if (
            endpoint_established
            and local_established
            and _clause_has_pronominal_shared_context_mix(clause)
        ):
            return True
        endpoint_established = endpoint_established or _clause_has_endpoint_lane(clause)
        local_established = local_established or _clause_has_local_lane(clause)
    return False


def _clause_has_referential_lane_mix(clause: str) -> bool:
    for term in ("mix", "combine"):
        for occurrence in _assertive_phrase_occurrences(clause, term):
            if _mix_occurrence_targets_lane(clause, occurrence):
                return True
    return False


def _segment_has_negated_shared_context(segment: str) -> bool:
    if not _segment_has_lane_relation_scope(segment):
        return False
    for term in _SHARED_CONTEXT_TERMS:
        for occurrence in _iter_term_occurrences(segment, term):
            if _occurrence_is_quoted(segment, occurrence.start(), occurrence.end()):
                continue
            if _occurrence_is_rejected_after(segment, occurrence.end()):
                continue
            if _occurrence_has_direct_shared_context_negation(
                segment,
                occurrence.start(),
                occurrence.end(),
            ):
                return True
    return False


def _separate_occurrence_targets_lane(
    segment: str,
    occurrence: re.Match[str],
) -> bool:
    before = segment[max(0, occurrence.start() - 140):occurrence.start()]
    after = segment[occurrence.end():min(len(segment), occurrence.end() + 140)]
    if re.search(
        rf"{_REFERENTIAL_LANES_PATTERN}(?:\s+(?:are|remain|stay|kept|must be|should be))?\s*$",
        before,
    ):
        return True
    if re.match(rf"^\s+{_REFERENTIAL_LANES_PATTERN}\b", after):
        return True

    endpoint_positions = [
        match.start()
        for match in re.finditer(r"\b(?:endpoint|response(?:-| )action)\b", segment)
    ]
    local_positions = [
        match.start()
        for match in re.finditer(r"\b(?:local|workstation)\b", segment)
    ]
    if not (endpoint_positions and local_positions):
        return False

    start = occurrence.start()
    endpoint_distance = min(abs(start - pos) for pos in endpoint_positions)
    local_distance = min(abs(start - pos) for pos in local_positions)
    if endpoint_distance <= 120 and local_distance <= 120:
        between_lanes = any(
            (endpoint < start < local) or (local < start < endpoint)
            for endpoint in endpoint_positions
            for local in local_positions
        )
        if between_lanes:
            return True

    lane_tail = re.search(
        r"\b(?:endpoint|response(?:-| )action|local|workstation)"
        r"(?:\s+[a-z0-9_-]+){0,4}\s*$",
        before,
    )
    if lane_tail and endpoint_distance <= 120 and local_distance <= 120:
        return True

    lane_head = re.match(
        r"^\s+(?:endpoint|response(?:-| )action|local|workstation)\b",
        after,
    )
    if lane_head and endpoint_distance <= 120 and local_distance <= 120:
        return True
    return False


def _occurrence_has_lane_relation_rejection(text: str, start: int) -> bool:
    prefix = text[max(0, start - 160):start]
    return bool(
        re.search(
            r"\b(?:wrong|incorrect|false|misleading)\s+to\s+(?:say|claim)\b"
            r"[^.!?;]{0,140}$",
            prefix,
        )
    )


def _occurrence_has_local_lane_relation_rejection(text: str, start: int) -> bool:
    """Reject repudiation frames only within the current comma-delimited discourse segment."""
    prefix = text[max(0, start - 160):start]
    comma = prefix.rfind(",")
    if comma >= 0:
        prefix = prefix[comma + 1:]
    return bool(
        re.search(
            r"\b(?:wrong|incorrect|false|misleading)\s+to\s+(?:say|claim)\b"
            r"[^.!?;]{0,140}$",
            prefix,
        )
    )


def _segment_has_relational_lane_separation(segment: str) -> bool:
    if not _segment_has_lane_relation_scope(segment):
        return False
    for term in (
        "do not mix",
        "don't mix",
        "dont mix",
        "must not mix",
        "should not mix",
        "do not combine",
        "don't combine",
        "dont combine",
        "must not combine",
        "should not combine",
    ):
        for occurrence in _iter_term_occurrences(segment, term):
            if _occurrence_is_quoted(segment, occurrence.start(), occurrence.end()):
                continue
            if _occurrence_is_negated(segment, occurrence.start()):
                continue
            if _occurrence_is_rejected_after(segment, occurrence.end()):
                continue
            if _occurrence_has_local_lane_relation_rejection(
                segment, occurrence.start()
            ):
                continue
            return True
    if _segment_has_negated_shared_context(segment):
        return True
    if _find_contextual_term_hits(
        segment,
        ["different lane", "distinct lane"],
        skip_negated=True,
        skip_quoted=True,
    ):
        return True

    for occurrence in _assertive_phrase_occurrences(segment, "separate"):
        if _occurrence_has_lane_relation_rejection(segment, occurrence.start()):
            continue
        if _separate_occurrence_targets_lane(segment, occurrence):
            return True
    return False


def _clause_has_relational_lane_separation(clause: str) -> bool:
    return any(
        _segment_has_relational_lane_separation(segment)
        for segment in _iter_lane_relation_segments(clause)
    )


def _clause_has_referential_lane_separation(clause: str) -> bool:
    return any(
        bool(re.search(rf"\b{_REFERENTIAL_LANES_PATTERN}\b", segment))
        and _segment_has_relational_lane_separation(segment)
        for segment in _iter_lane_relation_segments(clause)
    )


def has_execution_lane_separation(response_text: str) -> bool:
    clauses = list(_iter_clauses(response_text))
    has_endpoint_lane = any(_clause_has_endpoint_lane(clause) for clause in clauses)
    has_local_lane = any(_clause_has_local_lane(clause) for clause in clauses)
    if not (has_endpoint_lane and has_local_lane):
        return False
    if any(_clause_has_explicit_lane_mix(clause) for clause in clauses):
        return False
    if any(_clause_has_referential_lane_mix(clause) for clause in clauses):
        return False
    if _response_has_pronominal_shared_context_mix(clauses):
        return False
    if any(_clause_has_relational_lane_separation(clause) for clause in clauses):
        return True
    return any(_clause_has_referential_lane_separation(clause) for clause in clauses)


def _has_standalone_local_collect(response_text: str) -> bool:
    for clause in _iter_clauses(response_text):
        if not _clause_has_local_lane(clause):
            continue
        if "execute --command" in clause:
            continue
        for collect_flag in ("-quick collect-t1", "-mode collect"):
            if collect_flag not in clause:
                continue
            if _has_assertive_phase(
                clause,
                ["powershell.exe", "dcoir_collector.ps1", collect_flag],
            ):
                return True
    return False


def _has_endpoint_collect(response_text: str) -> bool:
    for clause in _iter_clauses(response_text):
        if not _clause_has_endpoint_lane(clause):
            continue
        if _has_assertive_phase(clause, ["execute --command", "dcoir_collector.ps1", "-quick collect-t1"]):
            return True
        if _has_assertive_phase(clause, ["execute --command", "dcoir_collector.ps1", "-mode collect"]):
            return True
    return False


def _has_assertive_phase(response_text: str, required_tokens: List[str]) -> bool:
    for clause in _iter_clauses(response_text):
        if not all(token in clause for token in required_tokens):
            continue
        if re.search(
            r"\b(?:do not|don't|dont|must not|should not|never|avoid|cannot|can't|can not|not)\b.*\b(?:use|run|execute|upload|place|retrieve|review|collect|clean(?:up|\s+up)|mix|keep|invoke)\b",
            clause,
        ):
            continue
        if not re.search(
            r"\b(?:use|run|execute|upload|place|retrieve|review|collect|clean(?:up|\s+up)|keep|invoke|read)\b",
            clause,
        ):
            continue
        if any(
            _occurrence_is_negated(clause, occurrence.start())
            or _occurrence_is_rejected_after(clause, occurrence.end())
            or POST_ACTION_REJECTION_PATTERN.search(clause[occurrence.end():])
            for token in required_tokens
            for occurrence in _iter_term_occurrences(clause, token)
        ):
            continue
        return True
    return False


def collector_procedure_actionability_gaps(response_text: str) -> List[str]:
    gaps: List[str] = []

    numbered_steps = len(re.findall(r"(?m)^\s*\d+[.)]\s+", str(response_text)))
    if numbered_steps < 5:
        gaps.append("ordered_procedure")

    has_package_deployment = _has_assertive_phase(
        response_text,
        ["dcoir_collector.ps1", "dcoir_collector.zip", "upload --file", "same directory"],
    ) or _has_assertive_phase(
        response_text,
        ["dcoir_collector.ps1", "dcoir_collector.zip", "upload --file", "co-located"],
    ) or _has_assertive_phase(
        response_text,
        ["dcoir_collector.ps1", "dcoir_collector.zip", "upload --file", "alongside"],
    )
    if not has_package_deployment:
        gaps.append("package_deployment")

    has_local_collect = _has_standalone_local_collect(response_text)
    has_endpoint_collect = _has_endpoint_collect(response_text)
    if not (has_local_collect and has_endpoint_collect):
        gaps.append("execution_commands")

    if not _has_assertive_phase(response_text, ["next_get_file", "get-file --path"]):
        gaps.append("retrieval")

    interpretation_surfaces = (
        "analyst_overview_path",
        "upload_summary_path",
        "metadata_report_path",
        "security_high_signal_summary_path",
    )
    if not _has_assertive_phase(response_text, list(interpretation_surfaces)):
        gaps.append("interpretation")

    if not _has_assertive_phase(response_text, ["cleanup_command"]):
        gaps.append("cleanup")

    return gaps


def score_marker_presence(response_text: str, markers: List[str]) -> Dict[str, Any]:
    lowered = normalize_text(response_text)
    matched = _find_contextual_term_hits(lowered, markers, skip_negated=True, skip_quoted=True)
    invalidated = []
    for marker in markers:
        if marker in matched:
            continue
        marker_invalidated = False
        for occurrence in _iter_term_occurrences(lowered, marker):
            if _occurrence_is_quoted(lowered, occurrence.start(), occurrence.end()):
                continue
            if _occurrence_is_negated(lowered, occurrence.start()):
                marker_invalidated = True
                break
            if _occurrence_is_rejected_after(lowered, occurrence.end()):
                marker_invalidated = True
                break
        if marker_invalidated:
            invalidated.append(marker)
    missing = [marker for marker in markers if marker not in matched]
    ratio = 1.0 if not markers else round(len(matched) / len(markers), 4)
    return {"matched": matched, "missing": missing, "invalidated": invalidated, "ratio": ratio}


def score_forbidden_markers(
    response_text: str,
    markers: List[str],
    literal_markers: List[str] | None = None,
) -> Dict[str, Any]:
    lowered = normalize_text(response_text)
    contextual_hits = _find_contextual_term_hits(lowered, markers, skip_negated=True, skip_quoted=True)
    literal_hits = _find_contextual_term_hits(lowered, literal_markers or [])
    hits = list(dict.fromkeys(contextual_hits + literal_hits))
    return {
        "hits": hits,
        "count": len(hits),
        "contextual_hits": contextual_hits,
        "literal_hits": literal_hits,
    }


def detect_anomalies(response_text: str, requested_checks: List[str]) -> List[Dict[str, str]]:
    lowered = normalize_text(response_text)
    anomalies: List[Dict[str, str]] = []

    if "unsupported_certainty_claims" in requested_checks:
        hits = _find_contextual_term_hits(
            lowered,
            UNSUPPORTED_CERTAINTY_TERMS,
            skip_negated=True,
            skip_quoted=True,
        )
        for hit in hits:
            anomalies.append({"type": "unsupported_certainty_claims", "detail": hit})

    if "invented_tool_or_workflow" in requested_checks:
        hits = _find_contextual_term_hits(lowered, INVENTED_TOOL_TERMS, skip_quoted=True)
        for hit in hits:
            anomalies.append({"type": "invented_tool_or_workflow", "detail": hit})

    if "contradictory_next_steps" in requested_checks:
        for first, second in CONTRADICTION_PAIRS:
            if first in lowered and second in lowered:
                anomalies.append({"type": "contradictory_next_steps", "detail": f"{first} + {second}"})

    if "missing_state_gap_language" in requested_checks:
        if (
            "not verified" not in lowered
            and "state gap" not in lowered
            and "cannot confirm" not in lowered
            and "without readback" not in lowered
        ):
            anomalies.append({"type": "missing_state_gap_language", "detail": "No bounded state-gap phrasing found."})

    if "output_shape_drift" in requested_checks and len(response_text.strip().split()) < 20:
        anomalies.append({"type": "output_shape_drift", "detail": "Response is unusually short for an operator-guidance turn."})

    if "duplicate_final_sections" in requested_checks:
        duplicate_headers = duplicate_final_sections(response_text)
        if duplicate_headers:
            anomalies.append(
                {
                    "type": "duplicate_final_sections",
                    "detail": "Repeated final section headers: " + ", ".join(duplicate_headers),
                }
            )

    if "missing_execution_lane_separation" in requested_checks and not has_execution_lane_separation(response_text):
        anomalies.append(
            {
                "type": "missing_execution_lane_separation",
                "detail": "No explicit non-negated separation between endpoint response-action commands and local/workstation PowerShell was found.",
            }
        )

    if "incomplete_collector_procedure_actionability" in requested_checks:
        gaps = collector_procedure_actionability_gaps(response_text)
        if gaps:
            anomalies.append(
                {
                    "type": "incomplete_collector_procedure_actionability",
                    "detail": "Missing source-grounded actionable procedure phases: " + ", ".join(gaps),
                }
            )

    return anomalies


def score_turn(fixture: Dict[str, Any], turn: Dict[str, Any], response_turn: Dict[str, Any]) -> Dict[str, Any]:
    response_text = str(response_turn.get("assistant_response", ""))
    thresholds = fixture.get("pass_thresholds", {})
    minimum_required_ratio = float(turn.get("minimum_required_marker_ratio", thresholds.get("minimum_required_marker_ratio", 1.0)))
    maximum_turn_anomalies = int(turn.get("maximum_anomaly_count", thresholds.get("maximum_turn_anomaly_count", 0)))
    turn_required_markers = turn.get("required_markers", fixture.get("required_markers", []))
    turn_forbidden_markers = turn.get("forbidden_markers", fixture.get("forbidden_markers", []))
    turn_literal_forbidden_markers = turn.get("literal_forbidden_markers", fixture.get("literal_forbidden_markers", []))
    turn_anomaly_checks = turn.get("anomaly_checks", fixture.get("anomaly_checks", []))

    required = score_marker_presence(response_text, turn_required_markers)
    forbidden = score_forbidden_markers(response_text, turn_forbidden_markers, turn_literal_forbidden_markers)
    anomalies = detect_anomalies(response_text, turn_anomaly_checks)
    success = forbidden["count"] == 0 and required["ratio"] >= minimum_required_ratio and len(anomalies) <= maximum_turn_anomalies
    return {
        "turn_id": turn.get("turn_id"),
        "response_length": len(response_text),
        "required_markers": required,
        "forbidden_markers": forbidden,
        "anomalies": anomalies,
        "success": success,
    }


def score_response_pack(fixture: Dict[str, Any], response_pack: Dict[str, Any]) -> Dict[str, Any]:
    fixture_turns = fixture.get("turns", [])
    thresholds = fixture.get("pass_thresholds", {})
    response_turns = {turn.get("turn_id"): turn for turn in response_pack.get("turns", [])}
    per_turn = []
    missing_turns = []
    for turn in fixture_turns:
        turn_id = turn.get("turn_id")
        response_turn = response_turns.get(turn_id)
        if response_turn is None:
            missing_turns.append(turn_id)
            per_turn.append(
                {
                    "turn_id": turn_id,
                    "response_length": 0,
                    "required_markers": {"matched": [], "missing": turn.get("required_markers", fixture.get("required_markers", [])), "invalidated": [], "ratio": 0.0},
                    "forbidden_markers": {"hits": [], "count": 0, "contextual_hits": [], "literal_hits": []},
                    "anomalies": [{"type": "missing_turn", "detail": "No response supplied for turn."}],
                    "success": False,
                }
            )
            continue
        per_turn.append(score_turn(fixture, turn, response_turn))

    turn_successes = sum(1 for row in per_turn if row["success"])
    all_turns_pass = turn_successes == len(per_turn)
    all_anomalies = [anomaly for row in per_turn for anomaly in row["anomalies"]]
    forbidden_hits = [hit for row in per_turn for hit in row["forbidden_markers"]["hits"]]
    overall_required_ratio = round(sum(row["required_markers"]["ratio"] for row in per_turn) / max(len(per_turn), 1), 4)
    maximum_anomaly_count = int(thresholds.get("maximum_anomaly_count", 0))
    success = (
        not missing_turns
        and all_turns_pass
        and len(forbidden_hits) <= int(thresholds.get("maximum_forbidden_marker_hits", 0))
        and len(all_anomalies) <= maximum_anomaly_count
        and overall_required_ratio >= float(thresholds.get("minimum_required_marker_ratio", 1.0))
    )

    return {
        "fixture_id": fixture.get("fixture_id"),
        "response_pack_schema_version": response_pack.get("schema_version"),
        "mode": response_pack.get("mode"),
        "model_name": response_pack.get("model_name"),
        "success": success,
        "turn_count": len(fixture_turns),
        "turn_success_count": turn_successes,
        "missing_turns": missing_turns,
        "overall_required_marker_ratio": overall_required_ratio,
        "forbidden_marker_hits": forbidden_hits,
        "anomaly_count": len(all_anomalies),
        "per_turn": per_turn,
        "metadata": response_pack.get("metadata", {}),
    }