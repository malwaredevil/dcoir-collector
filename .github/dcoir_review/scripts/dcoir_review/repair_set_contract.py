"""Stable contract and parser ownership for coordinated verified repair sets."""

from __future__ import annotations

from typing import Any

from dcoir_review import repair as repair_policy
from dcoir_review import repair_contract
from dcoir_review import repair_support
from dcoir_review import repair_set_edits

MARKER_VERSION = "v36"  # Persisted repair-marker compatibility value.
REPAIR_SET_OUTCOME = "verified-repair-set"
NO_SAFE_REPAIR_OUTCOME = "verified-no-safe-repair-set"
MAX_EDITS_PER_REPAIR = repair_set_edits.MAX_EDITS_PER_REPAIR
MAX_EDIT_RANGE_LINES = repair_set_edits.MAX_EDIT_RANGE_LINES
MAX_EDIT_TEXT_CHARS = repair_set_edits.MAX_EDIT_TEXT_CHARS
AUTHOR_MIN_CONFIDENCE = repair_contract.AUTHOR_MIN_CONFIDENCE
CRITIC_MIN_CONFIDENCE = repair_contract.CRITIC_MIN_CONFIDENCE

AUTHOR_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "DCOIR Verified Repair Set Author",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "defect_present", "action", "edits", "confidence", "display_title",
        "display_body", "rationale", "validation",
    ],
    "properties": {
        "defect_present": {"type": "boolean"},
        "action": {"type": "string", "enum": ["repair_set", "no_safe_repair"]},
        "edits": {
            "type": "array",
            "maxItems": MAX_EDITS_PER_REPAIR,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["path", "start_line", "end_line", "original", "replacement", "purpose"],
                "properties": {
                    "path": {"type": "string", "minLength": 1, "maxLength": 400},
                    "start_line": {"type": "integer", "minimum": 1},
                    "end_line": {"type": "integer", "minimum": 1},
                    "original": {"type": "string", "maxLength": MAX_EDIT_TEXT_CHARS},
                    "replacement": {"type": "string", "maxLength": MAX_EDIT_TEXT_CHARS},
                    "purpose": {"type": "string", "minLength": 1, "maxLength": 600},
                },
            },
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "display_title": {"type": "string", "maxLength": 160},
        "display_body": {"type": "string", "maxLength": 2200},
        "rationale": {"type": "string", "maxLength": 2200},
        "validation": {"type": "string", "maxLength": 2200},
    },
}

CRITIC_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "DCOIR Verified Repair Set Critic",
    "type": "object",
    "additionalProperties": False,
    "required": ["accepted", "confidence", "reason"],
    "properties": {
        "accepted": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string", "maxLength": 2200},
    },
}


def parse_author(result: Any, finding: dict[str, Any], hardened: Any) -> dict[str, Any]:
    result = repair_contract.normalize_author_metadata(result, finding)
    if not isinstance(result, dict):
        raise hardened.ReviewQualityError("DCOIR repair-set author returned a non-object result")
    if not isinstance(result.get("defect_present"), bool):
        raise hardened.ReviewQualityError("DCOIR repair-set author omitted boolean defect_present")
    action = str(result.get("action", "") or "").strip()
    if action not in {"repair_set", "no_safe_repair"}:
        raise hardened.ReviewQualityError("DCOIR repair-set author returned an invalid action")
    confidence = repair_contract.validated_author_confidence(
        result, hardened, stage="repair-set author"
    )
    raw_edits = result.get("edits")
    if not isinstance(raw_edits, list):
        raise hardened.ReviewQualityError("DCOIR repair-set author returned a non-list edits value")
    if len(raw_edits) > MAX_EDITS_PER_REPAIR:
        raise hardened.ReviewQualityError("DCOIR repair-set author exceeded the edit-count limit")

    fallback_path, fallback_line = repair_support._path_line(finding)
    fallback_title, fallback_body = repair_support._fallback_display(finding, fallback_path, fallback_line)
    parsed_edits: list[dict[str, Any]] = []
    for raw in raw_edits:
        if not isinstance(raw, dict):
            raise hardened.ReviewQualityError("DCOIR repair-set author returned a non-object edit")
        start_line = raw.get("start_line", 0)
        end_line = raw.get("end_line", 0)
        if type(start_line) is not int or type(end_line) is not int:
            raise hardened.ReviewQualityError("DCOIR repair-set author returned non-integer edit range")
        edit = {
            "path": str(raw.get("path", "") or "").strip(),
            "start_line": start_line,
            "end_line": end_line,
            "original": repair_set_edits.normalized_newlines(str(raw.get("original", "") or "")),
            "replacement": repair_set_edits.normalized_newlines(str(raw.get("replacement", "") or "")),
            "purpose": str(raw.get("purpose", "") or "").strip(),
        }
        reason = repair_set_edits.validate_edit_shape(edit)
        if reason:
            raise hardened.ReviewQualityError(f"DCOIR repair-set author returned invalid edit: {reason}")
        parsed_edits.append(edit)

    defect_present = bool(result["defect_present"])
    if not defect_present:
        action = "no_safe_repair"
        parsed_edits = []
    if action == "repair_set" and (confidence < AUTHOR_MIN_CONFIDENCE or not parsed_edits):
        action = "no_safe_repair"
        parsed_edits = []
    if action == "no_safe_repair":
        parsed_edits = []

    return {
        "defect_present": defect_present,
        "action": action,
        "edits": parsed_edits,
        "confidence": confidence,
        "display_title": str(result.get("display_title", "") or fallback_title).strip()[:160] or fallback_title,
        "display_body": str(result.get("display_body", "") or fallback_body).strip()[:2200] or fallback_body,
        "rationale": str(result.get("rationale", "") or "").strip()[:2200],
        "validation": str(result.get("validation", "") or "").strip()[:2200],
    }


def parse_critic(result: Any, hardened: Any) -> tuple[bool, float, str]:
    if not isinstance(result, dict):
        raise hardened.ReviewQualityError("DCOIR repair-set critic returned a non-object result")
    accepted = result.get("accepted")
    if not isinstance(accepted, bool):
        raise hardened.ReviewQualityError("DCOIR repair-set critic returned invalid accepted value")
    confidence = repair_contract.validated_critic_confidence(result, hardened)
    reason = str(result.get("reason", "") or "").strip()
    if accepted and confidence < CRITIC_MIN_CONFIDENCE:
        return False, confidence, reason or "Repair-set critic confidence was below threshold."
    return accepted, confidence, reason


def build_critic_config(config: Any, author_model: str) -> Any:
    return repair_policy.build_repair_critic_config(config, author_model)
