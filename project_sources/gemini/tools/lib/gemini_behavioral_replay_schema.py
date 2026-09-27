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
OPTIONAL_TURN_LIST_KEYS = ("required_markers", "forbidden_markers", "literal_forbidden_markers")
FIXTURE_LIST_KEYS = ("required_markers", "forbidden_markers")


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
    for key in (*TURN_LIST_KEYS, *OPTIONAL_TURN_LIST_KEYS):
        if key in turn and not isinstance(turn.get(key), list):
            messages.append(
                ValidationMessage(
                    "error",
                    f"turn {turn.get('turn_id', '<missing-turn-id>')} field {key} must be a list",
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

    for key in FIXTURE_LIST_KEYS:
        if key in fixture and not isinstance(fixture.get(key), list):
            messages.append(
                ValidationMessage(
                    "error",
                    f"fixture {fixture.get('fixture_id', '<missing-fixture-id>')} field {key} must be a list",
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
        if turn_id not in evidence_by_turn:
            messages.append(
                ValidationMessage(
                    "error",
                    f"fixture {fixture.get('fixture_id', '<missing-fixture-id>')} has no available_evidence_by_turn entry for {turn_id}",
                )
            )
        elif not isinstance(evidence_by_turn.get(turn_id), list):
            messages.append(
                ValidationMessage(
                    "error",
                    f"fixture {fixture.get('fixture_id', '<missing-fixture-id>')} evidence for {turn_id} must be a list",
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
