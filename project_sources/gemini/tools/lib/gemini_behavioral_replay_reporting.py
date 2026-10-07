from __future__ import annotations

from typing import Any, Dict, List


def render_markdown_report(results: List[Dict[str, Any]], metadata: Dict[str, Any] | None = None) -> str:
    metadata = metadata or {}
    validation_messages = metadata.get("validation_messages", [])
    validation_error_count = sum(1 for message in validation_messages if message.get("level") == "error")
    aggregate_success = bool(results) and all(result.get("success") for result in results) and validation_error_count == 0
    turn_count = sum(int(result.get("turn_count", 0)) for result in results)
    turn_success_count = sum(int(result.get("turn_success_count", 0)) for result in results)
    lines = ["# Gemini Behavioral Replay Report", ""]
    lines.extend(
        [
            "## Summary",
            "",
            f"- aggregate_success: `{str(aggregate_success).lower()}`",
            f"- result_count: `{len(results)}`",
            f"- turns passed: `{turn_success_count}/{turn_count}`",
            f"- validation errors: `{validation_error_count}`",
            "",
        ]
    )
    if metadata:
        lines.extend(["## Execution", ""])
        for key in ("replay_mode", "model_name", "live_execution", "fallback_reason", "fixture_count", "prompt_profile", "production_prompt_equivalent", "api_call_count", "api_call_success_count", "api_call_failure_count", "live_response_complete"):
            if key in metadata:
                lines.append(f"- {key}: `{metadata[key]}`")
        if metadata.get("checked_evidence"):
            lines.append(f"- checked_evidence: {', '.join(metadata['checked_evidence'])}")
        if metadata.get("unchecked_evidence"):
            lines.append(f"- unchecked_evidence: {', '.join(metadata['unchecked_evidence'])}")
        if metadata.get("live_environment_fidelity_gap"):
            lines.append(f"- live_environment_fidelity_gap: {metadata['live_environment_fidelity_gap']}")
        lines.append("")
    for result in results:
        lines.extend(
            [
                f"## {result['fixture_id']}",
                "",
                f"- mode: `{result.get('mode', 'unknown')}`",
                f"- model: `{result.get('model_name', 'unknown')}`",
                f"- success: `{str(result['success']).lower()}`",
                f"- turns passed: `{result['turn_success_count']}/{result['turn_count']}`",
                f"- required marker ratio: `{result['overall_required_marker_ratio']}`",
                f"- anomaly count: `{result['anomaly_count']}`",
                "",
            ]
        )
        if result.get("missing_turns"):
            lines.append(f"- missing turns: `{', '.join(result['missing_turns'])}`")
            lines.append("")
        lines.append("### Per-turn findings")
        lines.append("")
        for turn in result.get("per_turn", []):
            lines.append(f"- `{turn['turn_id']}` success=`{str(turn['success']).lower()}`")
            lines.append(f"  required matched: {', '.join(turn['required_markers']['matched']) or 'none'}")
            lines.append(f"  required missing: {', '.join(turn['required_markers']['missing']) or 'none'}")
            lines.append(f"  required invalidated: {', '.join(turn['required_markers'].get('invalidated', [])) or 'none'}")
            lines.append(f"  forbidden hits: {', '.join(turn['forbidden_markers']['hits']) or 'none'}")
            anomaly_details = ", ".join(f"{row['type']}: {row['detail']}" for row in turn.get("anomalies", []))
            lines.append(f"  anomalies: {anomaly_details or 'none'}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"

