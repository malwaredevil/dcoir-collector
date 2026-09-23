from __future__ import annotations

import re
from typing import List

from .gemini_behavioral_replay_text_scoring import (
    _iter_clauses,
    _iter_term_occurrences,
    _occurrence_is_negated,
    _occurrence_is_quoted,
    _occurrence_is_rejected_after,
    normalize_text,
)
from .gemini_behavioral_replay_lane_context import (
    _REFERENTIAL_LANES_PATTERN,
    _assertive_phrase_occurrences,
    _clause_has_endpoint_lane,
    _clause_has_local_lane,
    _iter_lane_relation_segments,
    _lane_presence,
    _mix_occurrence_targets_lane,
    _occurrence_has_direct_shared_context_negation,
    _occurrence_has_local_mix_rejection,
    _repudiation_frame_is_negated,
    _segment_has_lane_relation_scope,
)

_SHARED_CONTEXT_TERMS = (
    "same shell",
    "single shell",
    "one shell",
    "same command",
    "single command",
    "same lane",
)

_NO_MIX_RELATION_BOUNDARY_PATTERN = re.compile(
    r"[.!?;,]|\b(?:but|however|whereas|yet|while|although|though|because|when|then)\b"
)


def _bounded_no_mix_relation_sides(
    text: str,
    occurrence: re.Match[str],
) -> tuple[str, str]:
    before = text[max(0, occurrence.start() - 180):occurrence.start()]
    before_boundaries = list(_NO_MIX_RELATION_BOUNDARY_PATTERN.finditer(before))
    if before_boundaries:
        before = before[before_boundaries[-1].end():]

    after = text[occurrence.end():min(len(text), occurrence.end() + 180)]
    after_boundary = _NO_MIX_RELATION_BOUNDARY_PATTERN.search(after)
    if after_boundary:
        after = after[:after_boundary.start()]
    return normalize_text(before), normalize_text(after)


_NO_MIX_OBJECT_FREE_ADVERB_PATTERN = re.compile(
    r"(?:[a-z0-9_-]+(?:ly|ward|wards|wise)|"
    r"ever|again|anymore|anywhere|anytime|elsewhere|here|there|now|today|"
    r"tonight|henceforth|always|together)"
)


_NO_MIX_ADVERBIAL_PREPOSITION_PATTERN = re.compile(
    r"^(?:at|under|during|within|throughout|for|in|outside|beyond|after|"
    r"before|until|by|without)\b"
)


def _no_mix_trailing_scope_is_object_free_modifier(scope: str) -> bool:
    """Return True only for trailing syntax that cannot supply a mix object.

    Unknown bare words remain object-like by default. This keeps a stated
    object such as ``log formats`` authoritative while allowing subject-position
    lane prohibitions to carry ordinary adverbs and prepositional adjuncts.
    ``with`` is deliberately excluded from the generic preposition path because
    it commonly introduces the object/complement of ``mix``; only the reciprocal
    ``with each other`` form is accepted.
    """
    normalized = normalize_text(scope)
    if not normalized:
        return True
    if normalized == "with each other":
        return True
    tokens = normalized.split()
    if tokens and all(
        _NO_MIX_OBJECT_FREE_ADVERB_PATTERN.fullmatch(token)
        for token in tokens
    ):
        return True
    return bool(_NO_MIX_ADVERBIAL_PREPOSITION_PATTERN.match(normalized))


def _no_mix_scope_targets_lane_relation(scope: str) -> bool:
    referential_scope = re.sub(r"^(?:up\s+)?", "", scope).strip()
    if re.fullmatch(
        rf"{_REFERENTIAL_LANES_PATTERN}(?:\s+(?:together|with\s+each\s+other))?",
        referential_scope,
    ):
        return True
    return _clause_has_endpoint_lane(scope) and _clause_has_local_lane(scope)


def _no_mix_occurrence_targets_lane_relation(
    text: str,
    occurrence: re.Match[str],
) -> bool:
    before, after = _bounded_no_mix_relation_sides(text, occurrence)
    if _no_mix_scope_targets_lane_relation(after):
        return True
    if not _no_mix_trailing_scope_is_object_free_modifier(after):
        return False
    return _no_mix_scope_targets_lane_relation(before)


def _segment_has_explicit_lane_mix(segment: str) -> bool:
    if not _segment_has_lane_relation_scope(segment):
        return False
    for term in ("mix", "combine"):
        for occurrence in _assertive_phrase_occurrences(segment, term):
            if _occurrence_has_local_mix_rejection(segment, occurrence.start()):
                continue
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
    action_pattern = re.compile(
        r"\b(?P<negated>(?:(?:do not|don't|dont|must not|should not|never|avoid)\s+)?)"
        r"(?:run|execute|place|put|use|keep)\s+(?:them|both)\b"
    )
    for term in _SHARED_CONTEXT_TERMS:
        for occurrence in _assertive_phrase_occurrences(clause, term):
            prefix = clause[max(0, occurrence.start() - 120):occurrence.start()]
            action = None
            for candidate in action_pattern.finditer(prefix):
                trailing = prefix[candidate.end():]
                if len(trailing) > 80:
                    continue
                if any(char in ".!?;" for char in trailing):
                    continue
                action = candidate
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
            if _occurrence_has_local_mix_rejection(clause, occurrence.start()):
                continue
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
            if _occurrence_has_local_lane_relation_rejection(
                segment, occurrence.start()
            ):
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
    contrasts = list(re.finditer(r"\b(?:but|however|yet|nevertheless)\b", prefix))
    if contrasts:
        prefix = prefix[contrasts[-1].end():]
    return bool(
        re.search(
            r"(?:\b(?:wrong|incorrect|false|misleading)\s+to\s+(?:say|claim)\b"
            r"|\b(?:do not|don't|dont|cannot|can't|can not|should not|must not)\s+(?:say|claim)\b"
            r"|\b(?:(?:it\s+is|it's)\s+)?not\s+true\s+that\b)"
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
    match = re.search(
        r"\b(?:wrong|incorrect|false|misleading)\s+to\s+(?:say|claim)\b"
        r"[^.!?;]{0,140}$",
        prefix,
    )
    if match and not _repudiation_frame_is_negated(prefix, match.start()):
        return True
    return bool(
        re.search(
            r"(?:\b(?:do not|don't|dont|cannot|can't|can not|should not|must not)\s+(?:say|claim)\b"
            r"|\b(?:(?:it\s+is|it's)\s+)?not\s+true\s+that\b)"
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
            if not _no_mix_occurrence_targets_lane_relation(segment, occurrence):
                continue
            return True
    if _segment_has_negated_shared_context(segment):
        return True
    for term in ("different lane", "distinct lane"):
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
            if _separate_occurrence_targets_lane(segment, occurrence):
                return True

    for occurrence in _assertive_phrase_occurrences(segment, "separate"):
        if _occurrence_has_local_lane_relation_rejection(segment, occurrence.start()):
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
    has_endpoint_lane, has_local_lane = _lane_presence(clauses)
    if not (has_endpoint_lane and has_local_lane):
        return False
    if any(_clause_has_explicit_lane_mix(clause) for clause in clauses):
        return False
    if any(_clause_has_referential_lane_mix(clause) for clause in clauses):
        return False
    if _response_has_pronominal_shared_context_mix(clauses):
        return False
    normalized = normalize_text(response_text)
    m=re.search(r"\b(this|that|it)\s+is\s+(?:an?\s+)?endpoint\s+response[- ]action(?: syntax)?\s*,?\s+not\s+(?:a\s+)?local powershell\b",normalized)
    if m and not _occurrence_is_quoted(normalized,m.start(),m.end()) and not _occurrence_has_lane_relation_rejection(normalized,m.start()):
        return True
    endpoint_only = any(
        any(_assertive_phrase_occurrences(normalized, term))
        for term in ("response console only for endpoint actions", "elastic response console only for endpoint actions")
    )
    local_only = any(
        any(_assertive_phrase_occurrences(normalized, term))
        for term in ("local powershell only for", "local workstation powershell only for")
    )
    if endpoint_only and local_only:
        return True
    for occurrence in _assertive_phrase_occurrences(normalized, "separate execution lanes"):
        if _occurrence_has_lane_relation_rejection(normalized, occurrence.start()):
            continue
        scope = normalized[max(0, occurrence.start() - 160):occurrence.end()]
        if _clause_has_endpoint_lane(scope) and _clause_has_local_lane(scope):
            return True
    if any(_assertive_phrase_occurrences(normalized, "separate the execution lanes")):
        return True
    if any(_clause_has_relational_lane_separation(clause) for clause in clauses):
        return True
    return any(_clause_has_referential_lane_separation(clause) for clause in clauses)
