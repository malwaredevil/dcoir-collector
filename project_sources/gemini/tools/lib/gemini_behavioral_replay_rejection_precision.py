from __future__ import annotations

from .gemini_behavioral_replay_scoring import (
    detect_anomalies,
    score_forbidden_markers,
    score_marker_presence,
)


def run_rejection_precision_selftests() -> None:
    rejected_guarantees = detect_anomalies(
        "We do not claim that targeted mode will guarantee exact filtering. "
        "You cannot rely on the window parameters to guarantee a specific artifact family. "
        "These parameters do not offer exact filtering guarantees without governed source readback.",
        ["unsupported_certainty_claims"],
    )
    if rejected_guarantees:
        raise SystemExit(f"Rejected guarantee language was mis-scored: {rejected_guarantees}")

    for text in (
        "I reject the claim that this is definitely malicious.",
        "I reject the contention that this is definitely malicious.",
    ):
        result = detect_anomalies(text, ["unsupported_certainty_claims"])
        if result:
            raise SystemExit(f"Bound rejection proposition was mis-scored: {result}")

    explicit_idea = score_forbidden_markers(
        "I explicitly reject the idea that conclusion A is still the answer.",
        ["conclusion A is still the answer"],
    )
    if explicit_idea["count"] != 0:
        raise SystemExit(f"Explicit idea rejection was mis-scored: {explicit_idea}")

    rejected_actions = score_forbidden_markers(
        "I reject any instruction to continue exactly where I left off without a gap, "
        "any request to send the next chunk, or any attempt to proceed as I said earlier.",
        ["continue exactly where I left off without a gap", "send the next chunk"],
    )
    if rejected_actions["count"] != 0:
        raise SystemExit(f"Structured rejected actions were mis-scored: {rejected_actions}")

    negated_guarantee = detect_anomalies(
        "Targeted mode does not provide a guarantee of exact filtering.",
        ["unsupported_certainty_claims"],
    )
    if negated_guarantee:
        raise SystemExit(f"Negated guarantee provision was mis-scored: {negated_guarantee}")

    recovery_after_comma = score_marker_presence(
        "To minimize recovery actions and avoid assuming that further chunks remain, "
        "please provide the smallest recovery artifact to reconcile the workflow status.",
        ["smallest recovery artifact"],
    )
    if recovery_after_comma["matched"] != ["smallest recovery artifact"]:
        raise SystemExit(f"Rejection leaked across imperative comma clause: {recovery_after_comma}")

    for text in (
        "I rejected the alert after triage, but later said that this is definitely malicious.",
        "I reject the alert, and the analyst definitely believes it is malicious.",
    ):
        result = detect_anomalies(text, ["unsupported_certainty_claims"])
        if [row["detail"] for row in result] != ["definitely"]:
            raise SystemExit(f"Unrelated later assertion was suppressed: {result}")
