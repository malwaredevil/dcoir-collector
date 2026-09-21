from __future__ import annotations

import re
from typing import List

from .gemini_behavioral_replay_text_scoring import (
    POST_ACTION_REJECTION_PATTERN,
    _iter_clauses,
    _iter_term_occurrences,
    _occurrence_is_negated,
    _occurrence_is_rejected_after,
)
from .gemini_behavioral_replay_lane_context import (
    _clause_has_endpoint_lane,
    _clause_has_local_lane,
)

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


