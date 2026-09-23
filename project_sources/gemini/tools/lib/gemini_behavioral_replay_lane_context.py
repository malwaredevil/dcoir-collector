from __future__ import annotations

import re
from typing import Iterable, List

from .gemini_behavioral_replay_text_scoring import (
    _iter_term_occurrences,
    _occurrence_is_negated,
    _occurrence_is_quoted,
    _occurrence_is_rejected_after,
    normalize_text,
)

def _clause_has_endpoint_lane(clause: str) -> bool:
    return (
        "endpoint" in clause and (
            "response action" in clause
            or "response-action" in clause
            or "response console" in clause
            or "endpoint execution" in clause
            or "execute --command" in clause
        )
    ) or (
        "execute --command" in clause
        and ("response action" in clause or "response-action" in clause)
    )


def _clause_has_local_lane(clause: str) -> bool:
    return ("local" in clause or "workstation" in clause) and (
        "powershell" in clause or "command" in clause
    )


_REFERENTIAL_LANES_PATTERN = (
    r"(?:(?:these|those|the)\s+(?:two\s+)?lanes?|both\s+lanes?|two\s+lanes?)"
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
        normalized = normalize_text(segment).replace("`", "")
        normalized = normalized.replace(
            "endpoint response-action commands must not be pasted into local powershell",
            "do not mix endpoint response-action commands with local powershell",
        ).replace(
            "do not paste elastic upload, get-file, or execute syntax into a local powershell session",
            "do not mix endpoint response-action commands with local powershell",
        )
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
    if re.search(
        r"(?:^|[.!?;]\s*)(?:this|that|it)\s+is\s+(?:an?\s+)?endpoint\s+"
        r"response(?:-| )action\s*,?\s+not\s+(?:a\s+)?$",
        prefix,
    ):
        return True
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


_REPUDIATION_NEGATION_PATTERN = re.compile(
    r"\b(?:not|never|isn't|isnt|wasn't|wasnt|aren't|arent|weren't|werent)\b"
    r"(?:\s+[a-z0-9_-]+){0,3}\s*$"
)


def _repudiation_frame_is_negated(prefix: str, match_start: int) -> bool:
    polarity_prefix = prefix[max(0, match_start - 48):match_start]
    return bool(_REPUDIATION_NEGATION_PATTERN.search(polarity_prefix))


def _occurrence_has_local_mix_rejection(text: str, start: int) -> bool:
    """Reject direct wrong/incorrect/false/misleading-to-mix frames locally."""
    prefix = text[max(0, start - 160):start]
    comma = prefix.rfind(",")
    if comma >= 0:
        prefix = prefix[comma + 1:]
    match = re.search(
        r"\b(?:wrong|incorrect|false|misleading)\s+to\s+$",
        prefix,
    )
    return bool(
        match
        and not _repudiation_frame_is_negated(prefix, match.start())
    )
