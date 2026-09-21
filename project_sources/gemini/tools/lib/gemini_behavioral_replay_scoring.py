from __future__ import annotations

from typing import Any, Dict, List

from .gemini_behavioral_replay_text_scoring import (
    CONTRADICTION_PAIRS,
    INVENTED_TOOL_TERMS,
    UNSUPPORTED_CERTAINTY_TERMS,
    _find_contextual_term_hits,
    _iter_term_occurrences,
    _occurrence_is_negated,
    _occurrence_is_quoted,
    _occurrence_is_rejected_after,
    _occurrence_is_rejected_before,
    duplicate_final_sections,
    normalize_text,
)
from .gemini_behavioral_replay_lane_scoring import has_execution_lane_separation
from .gemini_behavioral_replay_collector_scoring import collector_procedure_actionability_gaps

def score_marker_presence(response_text: str, markers: List[str]) -> Dict[str, Any]:
    lowered = normalize_text(response_text)
    matched = _find_contextual_term_hits(
        lowered,
        markers,
        skip_negated=True,
        skip_quoted=True,
        allow_quoted_single_tokens=True,
        allow_markdown_code=True,
    )
    invalidated = []
    for marker in markers:
        if marker in matched:
            continue
        marker_invalidated = False
        for occurrence in _iter_term_occurrences(lowered, marker):
            if _occurrence_is_quoted(lowered, occurrence.start(), occurrence.end()):
                continue
            if (
                _occurrence_is_negated(lowered, occurrence.start())
                or _occurrence_is_rejected_before(lowered, occurrence.start())
            ):
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