from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


REQUIRED_FIXTURE_KEYS = [
    "fixture_id",
    "title",
    "source_issue_numbers",
    "source_pr_numbers",
    "scenario_tags",
    "system_surface",
    "model_target_profile",
    "turns",
    "available_evidence_by_turn",
    "artifact_inputs",
    "expected_behaviors",
    "forbidden_behaviors",
    "required_markers",
    "forbidden_markers",
    "expected_next_move_shapes",
    "anomaly_checks",
    "pass_thresholds",
    "report_expectations",
]

REQUIRED_TURN_KEYS = [
    "turn_id",
    "speaker",
    "content",
    "available_context_refs",
    "allowed_assumptions",
    "disallowed_assumptions",
    "expected_behavior_tags",
    "forbidden_behavior_tags",
    "scoring_notes",
]

TURN_LIST_KEYS = (
    "available_context_refs",
    "allowed_assumptions",
    "disallowed_assumptions",
    "expected_behavior_tags",
    "forbidden_behavior_tags",
)
OPTIONAL_TURN_LIST_KEYS = ("required_markers", "forbidden_markers", "literal_forbidden_markers", "anomaly_checks")
TURN_TEXT_KEYS = ("speaker", "content", "scoring_notes")
SUPPORTED_ANOMALY_CHECKS = frozenset({
    "contradictory_next_steps",
    "duplicate_final_sections",
    "incomplete_collector_procedure_actionability",
    "invented_tool_or_workflow",
    "missing_execution_lane_separation",
    "missing_state_gap_language",
    "output_shape_drift",
    "unsupported_certainty_claims",
})
FIXTURE_TEXT_KEYS = ("fixture_id", "title", "system_surface")
FIXTURE_INT_LIST_KEYS = ("source_issue_numbers", "source_pr_numbers")
FIXTURE_STRING_LIST_KEYS = (
    "scenario_tags", "expected_behaviors", "forbidden_behaviors",
    "required_markers", "forbidden_markers", "literal_forbidden_markers", "expected_next_move_shapes", "anomaly_checks",
)
FIXTURE_DICT_KEYS = ("model_target_profile", "available_evidence_by_turn", "pass_thresholds", "report_expectations")


REQUIRED_RESPONSE_PACK_KEYS = [
    "schema_version",
    "fixture_id",
    "mode",
    "model_name",
    "turns",
]

REQUIRED_RESPONSE_TURN_KEYS = [
    "turn_id",
    "assistant_response",
]

ALLOWED_RESPONSE_MODES = {
    "deterministic",
    "live_gemini",
    "fallback_emulation",
    "agent_designer_capture",
    "openai_webui_capture",
    "live_openai_api",
}

EXPECTED_RESPONSE_PACK_SCHEMA_VERSION = "gemini_behavioral_replay_response_pack_v1"


@dataclass(frozen=True)
class ValidationMessage:
    level: str
    message: str


def missing_keys(payload: Dict[str, Any], required_keys: List[str]) -> List[str]:
    return [key for key in required_keys if key not in payload]


def validate_turn(turn: Any) -> List[ValidationMessage]:
    messages: List[ValidationMessage] = []
    if not isinstance(turn, dict):
        return [ValidationMessage("error", "turn entry must be an object")]
    missing = missing_keys(turn, REQUIRED_TURN_KEYS)
    if missing:
        messages.append(
            ValidationMessage(
                "error",
                f"turn {turn.get('turn_id', '<missing-turn-id>')} is missing keys: {', '.join(missing)}",
            )
        )
    turn_id = turn.get("turn_id")
    if "turn_id" in turn and (not isinstance(turn_id, str) or not turn_id.strip()):
        messages.append(ValidationMessage("error", "turn_id must be a non-empty string"))
    for key in TURN_TEXT_KEYS:
        if key in turn and (not isinstance(turn.get(key), str) or not turn.get(key).strip()):
            messages.append(
                ValidationMessage(
                    "error",
                    f"turn {turn.get('turn_id', '<missing-turn-id>')} field {key} must be a non-empty string",
                )
            )
    if isinstance(turn.get("speaker"), str) and turn.get("speaker").strip() and turn.get("speaker") != "user":
        messages.append(ValidationMessage("error", "speaker must be 'user' for operator replay turns"))
    for key in (*TURN_LIST_KEYS, *OPTIONAL_TURN_LIST_KEYS):
        if key not in turn:
            continue
        value = turn.get(key)
        if not isinstance(value, list):
            messages.append(
                ValidationMessage(
                    "error",
                    f"turn {turn.get('turn_id', '<missing-turn-id>')} field {key} must be a list",
                )
            )
        elif any(not isinstance(item, str) or not item.strip() for item in value):
            messages.append(
                ValidationMessage(
                    "error",
                    f"turn {turn.get('turn_id', '<missing-turn-id>')} field {key} must contain only non-empty strings",
                )
            )
    if "minimum_required_marker_ratio" in turn:
        value = turn.get("minimum_required_marker_ratio")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
            messages.append(ValidationMessage("error", "turn minimum_required_marker_ratio must be a number from 0 to 1"))
    if "maximum_anomaly_count" in turn:
        value = turn.get("maximum_anomaly_count")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            messages.append(ValidationMessage("error", "turn maximum_anomaly_count must be a non-negative integer"))

    anomaly_checks = turn.get("anomaly_checks")
    if isinstance(anomaly_checks, list):
        unknown_checks = sorted({item for item in anomaly_checks if isinstance(item, str) and item.strip()} - SUPPORTED_ANOMALY_CHECKS)
        if unknown_checks:
            messages.append(
                ValidationMessage(
                    "error",
                    "turn anomaly_checks contains unsupported values: " + ", ".join(unknown_checks),
                )
            )
    return messages


def validate_fixture_shape(fixture: Any) -> List[ValidationMessage]:
    messages: List[ValidationMessage] = []
    if not isinstance(fixture, dict):
        return [ValidationMessage("error", "fixture must be an object")]
    missing = missing_keys(fixture, REQUIRED_FIXTURE_KEYS)
    if missing:
        messages.append(
            ValidationMessage(
                "error",
                f"fixture {fixture.get('fixture_id', '<missing-fixture-id>')} is missing keys: {', '.join(missing)}",
            )
        )

    for key in FIXTURE_TEXT_KEYS:
        if key in fixture and (not isinstance(fixture.get(key), str) or not fixture.get(key).strip()):
            messages.append(ValidationMessage("error", f"fixture field {key} must be a non-empty string"))
    for key in FIXTURE_INT_LIST_KEYS:
        if key not in fixture:
            continue
        value = fixture.get(key)
        if not isinstance(value, list):
            messages.append(ValidationMessage("error", f"fixture field {key} must be a list"))
        elif any(isinstance(item, bool) or not isinstance(item, int) for item in value):
            messages.append(ValidationMessage("error", f"fixture field {key} must contain only integers"))
    for key in FIXTURE_STRING_LIST_KEYS:
        if key not in fixture:
            continue
        value = fixture.get(key)
        if not isinstance(value, list):
            messages.append(ValidationMessage("error", f"fixture field {key} must be a list"))
        elif any(not isinstance(item, str) or not item.strip() for item in value):
            messages.append(ValidationMessage("error", f"fixture field {key} must contain only non-empty strings"))
    if "artifact_inputs" in fixture:
        artifact_inputs = fixture.get("artifact_inputs")
        if not isinstance(artifact_inputs, list):
            messages.append(ValidationMessage("error", "fixture field artifact_inputs must be a list"))
        elif any(not isinstance(item, dict) for item in artifact_inputs):
            messages.append(ValidationMessage("error", "fixture field artifact_inputs must contain only objects"))
    for key in FIXTURE_DICT_KEYS:
        if key in fixture and not isinstance(fixture.get(key), dict):
            messages.append(ValidationMessage("error", f"fixture field {key} must be an object"))

    turns = fixture.get("turns", [])
    if not isinstance(turns, list) or not turns:
        messages.append(
            ValidationMessage(
                "error",
                f"fixture {fixture.get('fixture_id', '<missing-fixture-id>')} must define at least one turn",
            )
        )
    else:
        seen_turn_ids = set()
        for turn in turns:
            for message in validate_turn(turn):
                messages.append(message)
            if not isinstance(turn, dict):
                continue
            turn_id = turn.get("turn_id")
            if not isinstance(turn_id, str) or not turn_id.strip():
                continue
            if turn_id in seen_turn_ids:
                messages.append(
                    ValidationMessage(
                        "error",
                        f"fixture {fixture.get('fixture_id', '<missing-fixture-id>')} repeats turn_id {turn_id}",
                    )
                )
            seen_turn_ids.add(turn_id)

    model_target_profile = fixture.get("model_target_profile", {})
    if not isinstance(model_target_profile, dict):
        messages.append(
            ValidationMessage(
                "error",
                f"fixture {fixture.get('fixture_id', '<missing-fixture-id>')} model_target_profile must be an object",
            )
        )
        model_target_profile = {}
    for required_key in ("reference_baseline", "simulated_production", "default_live_target"):
        if required_key not in model_target_profile:
            messages.append(
                ValidationMessage(
                    "error",
                    f"fixture {fixture.get('fixture_id', '<missing-fixture-id>')} missing model_target_profile.{required_key}",
                )
            )
        elif not isinstance(model_target_profile.get(required_key), str) or not model_target_profile.get(required_key).strip():
            messages.append(ValidationMessage("error", f"model_target_profile.{required_key} must be a non-empty string"))

    thresholds = fixture.get("pass_thresholds", {})
    if isinstance(thresholds, dict):
        ratio = thresholds.get("minimum_required_marker_ratio")
        if ratio is not None and (isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not 0 <= float(ratio) <= 1):
            messages.append(ValidationMessage("error", "pass_thresholds.minimum_required_marker_ratio must be a number from 0 to 1"))
        for key in ("maximum_forbidden_marker_hits", "maximum_anomaly_count", "maximum_turn_anomaly_count"):
            value = thresholds.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                messages.append(ValidationMessage("error", f"pass_thresholds.{key} must be a non-negative integer"))

    report_expectations = fixture.get("report_expectations", {})
    if isinstance(report_expectations, dict):
        for key in ("require_json_summary", "require_markdown_report"):
            if key in report_expectations and not isinstance(report_expectations.get(key), bool):
                messages.append(ValidationMessage("error", f"report_expectations.{key} must be boolean"))
        if "report_name" in report_expectations and (not isinstance(report_expectations.get("report_name"), str) or not report_expectations.get("report_name").strip()):
            messages.append(ValidationMessage("error", "report_expectations.report_name must be a non-empty string"))

    fixture_anomaly_checks = fixture.get("anomaly_checks")
    if isinstance(fixture_anomaly_checks, list):
        unknown_checks = sorted({item for item in fixture_anomaly_checks if isinstance(item, str) and item.strip()} - SUPPORTED_ANOMALY_CHECKS)
        if unknown_checks:
            messages.append(
                ValidationMessage(
                    "error",
                    "fixture anomaly_checks contains unsupported values: " + ", ".join(unknown_checks),
                )
            )

    evidence_by_turn = fixture.get("available_evidence_by_turn", {})
    if not isinstance(evidence_by_turn, dict):
        messages.append(
            ValidationMessage(
                "error",
                f"fixture {fixture.get('fixture_id', '<missing-fixture-id>')} available_evidence_by_turn must be an object",
            )
        )
        evidence_by_turn = {}
    for turn in turns if isinstance(turns, list) else []:
        if not isinstance(turn, dict):
            continue
        turn_id = turn.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id.strip():
            continue
        if turn_id not in evidence_by_turn:
            messages.append(
                ValidationMessage(
                    "error",
                    f"fixture {fixture.get('fixture_id', '<missing-fixture-id>')} has no available_evidence_by_turn entry for {turn_id}",
                )
            )
        else:
            evidence = evidence_by_turn.get(turn_id)
            if not isinstance(evidence, list):
                messages.append(
                    ValidationMessage(
                        "error",
                        f"fixture {fixture.get('fixture_id', '<missing-fixture-id>')} evidence for {turn_id} must be a list",
                    )
                )
            elif any(not isinstance(item, str) or not item.strip() for item in evidence):
                messages.append(
                    ValidationMessage(
                        "error",
                        f"fixture {fixture.get('fixture_id', '<missing-fixture-id>')} evidence for {turn_id} must contain only non-empty strings",
                    )
                )

    if not fixture.get("required_markers"):
        messages.append(
            ValidationMessage(
                "warning",
                f"fixture {fixture.get('fixture_id', '<missing-fixture-id>')} has no required_markers",
            )
        )

    return messages


def validate_response_turn(turn: Dict[str, Any]) -> List[ValidationMessage]:
    messages: List[ValidationMessage] = []
    missing = missing_keys(turn, REQUIRED_RESPONSE_TURN_KEYS)
    if missing:
        messages.append(
            ValidationMessage(
                "error",
                f"response turn {turn.get('turn_id', '<missing-turn-id>')} is missing keys: {', '.join(missing)}",
            )
        )
    assistant_response = str(turn.get("assistant_response", "")).strip()
    if "assistant_response" in turn and not assistant_response:
        messages.append(
            ValidationMessage(
                "error",
                f"response turn {turn.get('turn_id', '<missing-turn-id>')} must not have an empty assistant_response",
            )
        )
    return messages


def validate_response_pack_shape(response_pack: Dict[str, Any], fixture: Dict[str, Any] | None = None) -> List[ValidationMessage]:
    messages: List[ValidationMessage] = []
    missing = missing_keys(response_pack, REQUIRED_RESPONSE_PACK_KEYS)
    if missing:
        messages.append(
            ValidationMessage(
                "error",
                f"response pack is missing keys: {', '.join(missing)}",
            )
        )

    schema_version = response_pack.get("schema_version")
    if schema_version is not None and schema_version != EXPECTED_RESPONSE_PACK_SCHEMA_VERSION:
        messages.append(
            ValidationMessage(
                "error",
                f"response pack schema_version {schema_version!r} does not match expected {EXPECTED_RESPONSE_PACK_SCHEMA_VERSION!r}",
            )
        )

    mode = response_pack.get("mode")
    if mode is not None and mode not in ALLOWED_RESPONSE_MODES:
        messages.append(
            ValidationMessage(
                "error",
                f"response pack mode {mode!r} is not allowed; expected one of {sorted(ALLOWED_RESPONSE_MODES)}",
            )
        )

    turns = response_pack.get("turns", [])
    if not isinstance(turns, list) or not turns:
        messages.append(
            ValidationMessage(
                "error",
                "response pack must define at least one turn",
            )
        )
    else:
        seen_turn_ids = set()
        for turn in turns:
            for message in validate_response_turn(turn):
                messages.append(message)
            turn_id = turn.get("turn_id")
            if turn_id in seen_turn_ids:
                messages.append(
                    ValidationMessage(
                        "error",
                        f"response pack repeats turn_id {turn_id}",
                    )
                )
            seen_turn_ids.add(turn_id)

    if fixture is not None:
        fixture_id = fixture.get("fixture_id")
        if response_pack.get("fixture_id") != fixture_id:
            messages.append(
                ValidationMessage(
                    "error",
                    f"response pack fixture_id {response_pack.get('fixture_id')!r} does not match fixture {fixture_id!r}",
                )
            )

        fixture_turn_ids = [turn.get("turn_id") for turn in fixture.get("turns", [])]
        response_turn_ids = [turn.get("turn_id") for turn in turns if isinstance(turns, list)]
        for turn_id in response_turn_ids:
            if turn_id not in fixture_turn_ids:
                messages.append(
                    ValidationMessage(
                        "error",
                        f"response pack includes unknown turn_id {turn_id!r} for fixture {fixture_id!r}",
                    )
                )

    return messages
