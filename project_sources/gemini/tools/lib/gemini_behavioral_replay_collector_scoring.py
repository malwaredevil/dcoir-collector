from __future__ import annotations

import re
from typing import List

from .gemini_behavioral_replay_lane_context import _clause_has_endpoint_lane, _clause_has_local_lane
from .gemini_behavioral_replay_rejection_patterns import POST_ACTION_REJECTION_PATTERN
from .gemini_behavioral_replay_semantic_assertions import analyze_semantics
from .gemini_behavioral_replay_text_scoring import (
    _iter_clauses,
    _iter_term_occurrences,
    _occurrence_is_negated,
    _occurrence_is_rejected_after,
)

_RETRIEVAL_WAIVER = re.compile(
    r"\b(?:no need to|(?:do|does) not need to|(?:don't|dont|doesn't|doesnt) need to|"
    r"without (?:waiting for|using)|ignor(?:e|ing)|skip(?:ping)?|guess(?:ing)?)\b"
)


def _has_standalone_local_collect(response_text: str) -> bool:
    for clause in _iter_clauses(response_text):
        if "execute --command" in clause or "powershell" not in clause:
            continue
        # A clause that places the command on the endpoint lane is not local collection.
        if _clause_has_endpoint_lane(clause) and not _clause_has_local_lane(clause):
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
        # A clause that places execute --command in local PowerShell swaps the lanes.
        if _clause_has_local_lane(clause) and not _clause_has_endpoint_lane(clause):
            continue
        for collect_flag in ("-quick collect-t1", "-mode collect"):
            if _has_assertive_phase(clause, ["execute --command", "dcoir_collector.ps1", collect_flag]):
                return True
    return False


def _has_assertive_phase(response_text: str, required_tokens: List[str]) -> bool:
    for clause in _iter_clauses(response_text):
        if not all(token in clause for token in required_tokens):
            continue
        if re.search(
            r"\b(?:do not|don't|dont|must not|should not|never|avoid|cannot|can't|can not|not)\b.*\b(?:use|run|execute|upload(?:ed|ing)?|plac(?:e|ed|ing)|retrieve|review|interpret|collect|clean(?:up|\s+up)|mix|keep|invoke)\b",
            clause,
        ):
            continue
        if not re.search(
            r"\b(?:use|run|execute|upload(?:ed|ing)?|plac(?:e|ed|ing)|retrieve|review|interpret|collect|clean(?:up|\s+up)|keep|invoke|read)\b",
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
    normalized = " ".join(str(response_text).lower().split())

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
        has_package_deployment = (
            _has_assertive_phase(response_text, ["upload --file", "dcoir_collector.ps1"])
            and _has_assertive_phase(response_text, ["upload --file", "dcoir_collector.zip"])
            and _has_assertive_phase(response_text, ["same directory"])
        )
    if not has_package_deployment:
        same_directory_required = bool(
            re.search(r"\b(?:must|should|need(?:s)?\s+to)\s+be\s+in\s+(?:the\s+)?same directory\b", normalized)
        )
        has_package_deployment = (
            _has_assertive_phase(response_text, ["upload --file", "dcoir_collector.ps1"])
            and _has_assertive_phase(response_text, ["upload --file", "dcoir_collector.zip"])
            and _has_assertive_phase(response_text, ["upload both files"])
            and same_directory_required
        )
    if not has_package_deployment:
        gaps.append("package_deployment")

    has_local_collect = _has_standalone_local_collect(response_text)
    has_endpoint_collect = _has_endpoint_collect(response_text)
    if not (has_local_collect and has_endpoint_collect):
        gaps.append("execution_commands")

    # Retrieval must follow NEXT_GET_FILE; a waived source or guessed path is not governed retrieval.
    clauses = list(_iter_clauses(response_text))
    has_source = any(
        "next_get_file" in clause and not _RETRIEVAL_WAIVER.search(clause)
        and _has_assertive_phase(clause, ["next_get_file"])
        for clause in clauses
    )
    has_retrieval = any(
        not _RETRIEVAL_WAIVER.search(clause) and (
            _has_assertive_phase(clause, ["get-file --path"])
            or _has_assertive_phase(clause, ["get-file", "response action"])
        )
        for clause in clauses
    )
    if not (has_source and has_retrieval):
        gaps.append("retrieval")

    semantic_interpretation = analyze_semantics(response_text).interpretation_actionability_status()
    if semantic_interpretation is None:
        interpretation_surfaces = (
            "analyst_overview_path",
            "upload_summary_path",
            "metadata_report_path",
            "security_high_signal_summary_path",
        )
        has_interpretation = _has_assertive_phase(response_text, list(interpretation_surfaces))
        if not has_interpretation and all(surface in normalized for surface in interpretation_surfaces):
            has_interpretation = (
                "begin with orientation surfaces" in normalized
                or "interpret collection output" in normalized
                or _has_assertive_phase(response_text, ["orientation surfaces"])
                or _has_assertive_phase(response_text, ["interpret the returned evidence", "analyst-first order"])
                or _has_assertive_phase(response_text, ["interpret collector output", "analyst-first order"])
                or _has_assertive_phase(response_text, ["review", "returned", "in this order"])
            )
    else:
        has_interpretation = semantic_interpretation
    if not has_interpretation:
        gaps.append("interpretation")

    if not _has_assertive_phase(response_text, ["cleanup_command"]):
        gaps.append("cleanup")

    return gaps
