"""Focused disagreement corpus for required-marker and assertion-polarity scoring."""
from __future__ import annotations

from .gemini_behavioral_replay_assertion_polarity import occurrence_is_asserted
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
    (
        "positive_recovery_artifact_after_negated_assumption",
        "Because I cannot assume more chunks remain, please determine the current state and provide the smallest recovery artifact.",
        "smallest recovery artifact",
    ),
)

def evaluate_polarity_cases() -> list[dict[str, object]]:
    results = []
    for case_id, text, marker in POLARITY_CASES:
        lowered = text.lower()
        start = lowered.index(marker)
        end = start + len(marker)
        required_match = marker in score_marker_presence(text, [marker])["matched"]
        forbidden_hit = marker in score_forbidden_markers(text, [marker])["hits"]
        asserted = occurrence_is_asserted(lowered, start, end)
        results.append({
            "case_id": case_id,
            "required_match": required_match,
            "forbidden_hit": forbidden_hit,
            "asserted": asserted,
            "required_disagrees_with_assertion": required_match != asserted,
        })
    return results


def run_polarity_consistency_selftest() -> None:
    results = evaluate_polarity_cases()
    for result in results:
        required_match = bool(result["required_match"])
        forbidden_hit = bool(result["forbidden_hit"])
        asserted = bool(result["asserted"])
        if required_match != asserted:
            raise SystemExit(f"Required-marker polarity drift: {result}")
        if forbidden_hit != asserted:
            raise SystemExit(f"Forbidden-marker polarity drift: {result}")
        if (not required_match) != (not forbidden_hit):
            raise SystemExit(f"Required/forbidden complement invariant failed: {result}")
    positives = [
        result for result in results
        if str(result["case_id"]).startswith("positive_recovery_artifact")
    ]
    for positive in positives:
        if not (positive["required_match"] and positive["asserted"]):
            raise SystemExit(f"Positive polarity control failed: {positive}")
