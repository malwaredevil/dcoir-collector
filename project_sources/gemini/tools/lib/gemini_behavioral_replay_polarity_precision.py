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
    (
        "rejection_label_colon",
        "Do not claim: high confidence malicious.",
        "high confidence malicious",
    ),
    (
        "rejection_with_timestamp",
        "Do not claim that the 03:14 logon is high confidence malicious.",
        "high confidence malicious",
    ),
    (
        "rejection_with_url_port",
        "Do not claim that http://intranet-host:445 is high confidence malicious.",
        "high confidence malicious",
    ),
    (
        "rejection_joined_subjects",
        "Never claim: the endpoint console and local PowerShell are interchangeable.",
        "interchangeable",
    ),
    (
        "rejection_coordinated_verbs",
        "Do not claim the agent can read, retrieve, or upload the evidence bundle.",
        "upload the evidence bundle",
    ),
    (
        "positive_independent_colon_caution",
        "Absence does not indicate tampering: missing logs do not prove log clearing.",
        "missing logs do not prove log clearing",
    ),
    (
        "positive_assertion_after_contrast",
        "Do not claim this is malicious, but the endpoint console and local PowerShell are interchangeable.",
        "interchangeable",
    ),
    (
        "positive_malicious_certainty",
        "This is high confidence malicious.",
        "high confidence malicious",
    ),
    (
        "rejection_colon_with_finite_predicate",
        "Do not claim: this is high confidence malicious.",
        "high confidence malicious",
    ),
    (
        "rejection_dash_label",
        "Never state - high confidence malicious.",
        "high confidence malicious",
    ),
    (
        "rejection_then_coordinated_verb",
        "Never claim the agent can read, then upload the evidence bundle.",
        "upload the evidence bundle",
    ),
    (
        "positive_separate_colon_assertion",
        "The alert is incomplete: the endpoint console and local PowerShell are interchangeable.",
        "interchangeable",
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
    rejected = {
        "negated_required_action",
        "without_required_action",
        "bounded_malicious_certainty",
        "rejection_label_colon",
        "rejection_with_timestamp",
        "rejection_with_url_port",
        "rejection_joined_subjects",
        "rejection_coordinated_verbs",
        "rejection_colon_with_finite_predicate",
        "rejection_dash_label",
        "rejection_then_coordinated_verb",
    }
    for result in results:
        if bool(result["asserted"]) == (str(result["case_id"]) in rejected):
            raise SystemExit(f"Unexpected assertion polarity for control: {result}")
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
