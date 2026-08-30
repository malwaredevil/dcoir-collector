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
]

NEGATION_PATTERN = re.compile(
    r"(?:do not|don't|dont|never|avoid|must not|should not|cannot|can't|can not|not|no|isn't|isnt|wasn't|wasnt|aren't|arent|weren't|werent)\s+(?:the\s+|an?\s+)?$"
)

REJECTED_ASSERTION_PATTERN = re.compile(
    r"(?:wrong to (?:say|ask for|request|require|treat|frame|use|accept|rely on)|incorrect to (?:say|ask for|request|require|treat|frame|use|accept|rely on)|false to say|not true that|isn't true that|isnt true that|unsupported to (?:say|claim|treat|frame|use|accept|rely on)|not enough to (?:say|claim|treat|frame|use|accept|rely on)|not sufficient to (?:say|claim|treat|frame|use|accept|rely on)|premature to (?:say|claim|treat|frame|use|accept|rely on)|no need for|(?:do not|don't|dont|should not|shouldn't|shouldnt|must not|cannot|can't|can not) (?:say|ask for|request|require|treat|frame|use|accept|rely on)|avoid (?:saying|asking for|requesting|requiring|treating|framing|using|accepting|relying on)|no need to (?:say|ask for|request|require|treat|frame|use|accept|rely on))\s+(?:the\s+|an?\s+)?(?:\w+\s+){0,6}$"
)

POST_MARKER_REJECTION_PATTERN = re.compile(
    r"^\s*(?:[,;:.!?]\s*)?(?:(?:no|nope)\b[\s,;:-]*)?(?:(?:but|however|though|although|yet|nevertheless|even so)\s+)?(?:(?:that|this|it|which|they)\s+)?(?:(?:is|are|was|were)\s+(?:(?:also|still|clearly|simply|just|really|only)\s+)?(?:an?\s+)?)?(?:(?:also|still|clearly|simply|just|really|only)\s+)?(?:the\s+)?(?:wrong|incorrect|false|invalid|misleading|wrong framing|wrong frame|incorrect framing|incorrect frame|false framing|false frame|wrong conclusion|incorrect conclusion|false conclusion|not enough|not necessary|not needed|not required|unnecessary|insufficient|unsupported|unfounded|overstated|in name only|nominal|label only|just a label|only a label|phrase i would not use|phrase we would not use|a phrase i would not use|a phrase we would not use|should be ignored|should be discarded|should not be used|should not be relied on|can be ignored|can be discarded|does not matter|doesn't matter|doesnt matter|prove it|infer .* anyway|require the full transcript|request the full transcript|ask for the full transcript)"
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


def duplicate_final_sections(response_text: str) -> List[str]:
    counts = {header: 0 for header in FINAL_SECTION_HEADERS}
    for line in str(response_text).splitlines():
        normalized = _normalized_header_line(line)
        if normalized in counts:
            counts[normalized] += 1
    return [header for header, count in counts.items() if count > 1]


def _clause_has_endpoint_lane(clause: str) -> bool:
    return "endpoint" in clause and ("response action" in clause or "response-action" in clause)


def _clause_has_local_lane(clause: str) -> bool:
    return ("local" in clause or "workstation" in clause) and (
        "powershell" in clause or "command" in clause
    )


def has_execution_lane_separation(response_text: str) -> bool:
    for clause in _iter_clauses(response_text):
        if not (_clause_has_endpoint_lane(clause) and _clause_has_local_lane(clause)):
            continue
        positive_separation = bool(
            _find_contextual_term_hits(
                clause,
                ["separate", "different lane", "distinct lane"],
                skip_negated=True,
                skip_quoted=True,
            )
        )
        explicit_no_mix = bool(
            _find_contextual_term_hits(
                clause,
                ["do not mix", "don't mix", "dont mix", "must not mix", "should not mix"],
                skip_quoted=True,
            )
        )
        if positive_separation or explicit_no_mix:
            return True
    return False


def _has_standalone_local_collect(response_text: str) -> bool:
    for clause in _iter_clauses(response_text):
        if "execute --command" in clause:
            continue
        if not ("local" in clause or "workstation" in clause):
            continue
        if (
            "powershell.exe" in clause
            and "dcoir_collector.ps1" in clause
            and ("-quick collect-t1" in clause or "-mode collect" in clause)
        ):
            return True
    return False


def _has_endpoint_collect(response_text: str) -> bool:
    for clause in _iter_clauses(response_text):
        if (
            "execute --command" in clause
            and "dcoir_collector.ps1" in clause
            and ("-quick collect-t1" in clause or "-mode collect" in clause)
        ):
            return True
    return False


def collector_procedure_actionability_gaps(response_text: str) -> List[str]:
    lowered = normalize_text(response_text)
    gaps: List[str] = []

    numbered_steps = len(re.findall(r"(?m)^\s*\d+[.)]\s+", str(response_text)))
    if numbered_steps < 5:
        gaps.append("ordered_procedure")

    has_package_deployment = (
        "dcoir_collector.ps1" in lowered
        and "dcoir_collector.zip" in lowered
        and "upload --file" in lowered
        and any(marker in lowered for marker in ("same directory", "co-located", "alongside"))
    )
    if not has_package_deployment:
        gaps.append("package_deployment")

    has_local_collect = _has_standalone_local_collect(response_text)
    has_endpoint_collect = _has_endpoint_collect(response_text)
    if not (has_local_collect and has_endpoint_collect):
        gaps.append("execution_commands")

    if not ("next_get_file" in lowered and "get-file --path" in lowered):
        gaps.append("retrieval")

    interpretation_surfaces = (
        "analyst_overview_path",
        "upload_summary_path",
        "metadata_report_path",
        "security_high_signal_summary_path",
    )
    if not all(marker in lowered for marker in interpretation_surfaces):
        gaps.append("interpretation")

    if "cleanup_command" not in lowered:
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
        for header in duplicate_final_sections(response_text):
            anomalies.append({"type": "duplicate_final_sections", "detail": f"Repeated final section header: {header}"})

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
