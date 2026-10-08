"""Focused disagreement corpus for required-marker and assertion-polarity scoring."""
from __future__ import annotations

from .gemini_behavioral_replay_assertion_polarity import occurrence_is_assertive_polarity
from .gemini_behavioral_replay_scoring import score_forbidden_markers, score_marker_presence

POLARITY_CASES = (
    (
        "negated_required_action",
        "Do not make one controlled repair step; rerun the whole sweep.",
        "one controlled repair step",
    ),
    (
        "without_required_action",
        "Without making one controlled repair step, rerun the whole sweep.",
        "one controlled repair step",
    ),
    (
        "bounded_malicious_certainty",
        "There is insufficient evidence to declare this high confidence malicious.",
        "high confidence malicious",
    ),
    (
        "positive_recovery_artifact",
        "Please determine the current state and provide the smallest recovery artifact.",
        "smallest recovery artifact",
    ),
)

EXPECTED_CURRENT_DISAGREEMENTS = {
    "negated_required_action",
    "without_required_action",
    "bounded_malicious_certainty",
}


def evaluate_polarity_cases() -> list[dict[str, object]]:
    results = []
    for case_id, text, marker in POLARITY_CASES:
        lowered = text.lower()
        start = lowered.index(marker)
        end = start + len(marker)
        required_match = marker in score_marker_presence(text, [marker])["matched"]
        forbidden_hit = marker in score_forbidden_markers(text, [marker])["hits"]
        asserted = occurrence_is_assertive_polarity(lowered, start, end)
        results.append({
            "case_id": case_id,
            "required_match": required_match,
            "forbidden_hit": forbidden_hit,
            "asserted": asserted,
            "required_disagrees_with_assertion": required_match != asserted,
        })
    return results


def run_polarity_disagreement_selftest() -> None:
    results = evaluate_polarity_cases()
    disagreements = {
        str(result["case_id"])
        for result in results
        if result["required_disagrees_with_assertion"]
    }
    if disagreements != EXPECTED_CURRENT_DISAGREEMENTS:
        raise SystemExit(
            "Replay polarity disagreement baseline changed before the single-owner scorer slice: "
            f"expected={sorted(EXPECTED_CURRENT_DISAGREEMENTS)} actual={sorted(disagreements)}"
        )
    for result in results:
        if bool(result["forbidden_hit"]) != bool(result["asserted"]):
            raise SystemExit(f"Forbidden-marker polarity drift: {result}")
    positive = next(result for result in results if result["case_id"] == "positive_recovery_artifact")
    if not (positive["required_match"] and positive["asserted"]):
        raise SystemExit(f"Positive polarity control failed: {positive}")
