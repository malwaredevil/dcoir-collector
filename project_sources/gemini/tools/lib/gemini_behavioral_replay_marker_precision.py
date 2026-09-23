from __future__ import annotations

from .gemini_behavioral_replay_scoring import (
    detect_anomalies,
    score_forbidden_markers,
    score_marker_presence,
)
from .gemini_behavioral_replay_rejection_precision import run_rejection_precision_selftests

def run_contextual_marker_precision_selftests() -> None:
    rejected_cases = [
        ("confirmed malicious compromise", "We cannot state that this is a confirmed malicious compromise."),
        ("active exploitation is confirmed", "We cannot declare that active exploitation is confirmed."),
        ("nothing exists", "We explicitly reject any conclusion that nothing exists."),
        ("benign because there were no results", "We explicitly reject any conclusion that nothing exists, that the activity is benign because there were no results."),
        ("confirmed stealth", "We explicitly reject any conclusion that this indicates confirmed stealth."),
        ("send the next chunk", "We will not ask you to send the next chunk."),
        ("send the next chunk", "There is no requirement to send the next chunk."),
        ("continue exactly where I left off without a gap", "We reject the assumption that I can continue exactly where I left off without a gap."),
        ("continue exactly where I left off without a gap", "I cannot continue exactly where I left off without a gap."),
        ("search all indexes for all time", "Use one bounded repair rather than attempting to search all indexes for all time."),
        ("this exact command will work", "I cannot promise that this exact command will work."),
        ("use -recurse", "We must reject any recommendation to blindly use -recurse."),
        ("guarantee exact filtering", "We do not claim that these parameters guarantee exact filtering."),
        ("definitely produce", "We reject the premise that these parameters will definitely produce the requested artifact folder."),
        ("confirmed malicious compromise", "We cannot classify this as a confirmed malicious compromise."),
        ("confirmed malicious compromise", "Current evidence does not support disruptive containment or a claim of confirmed malicious compromise."),
        ("logs were cleared", "Nor can we conclude with high confidence that logs were cleared."),
        ("high confidence malicious", "We cannot assign a high confidence malicious verdict."),
        ("high confidence malicious", "Without additional telemetry, we cannot label this high confidence malicious."),
        ("high confidence malicious", "We cannot evaluate this as high confidence malicious solely based on a suspicious file path and a lack of logs."),
        ("high confidence malicious", "We cannot assess this as high confidence malicious based solely on suspicious file placement."),
        ("high confidence malicious", "Calling this high confidence malicious would exceed the currently verified facts."),
        ("benign because there were no results", "Nor does it mean the event is benign because there were no results."),
        ("this exact command will work", "I cannot guarantee that this exact command will work."),
        ("this exact command will work", "We cannot assure you that this exact command will work."),
        ("use -recurse", "I cannot advise you to use -recurse without verifying the environment."),
        ("safe to clean up now", "Because the outcome is unknown, it is not **safe to clean up now**."),
        ("this exact command will work", "I cannot provide a finalized search string and claim this exact command will work."),
        ("use -recurse", "Nor will I simply tell you to use -recurse."),
        ("use -recurse", "Nor do I advise you to use -recurse before confirming compatibility."),
        ("this exact command will work", "We must explicitly avoid claiming that this exact command will work."),
        ("use -recurse", "We must explicitly avoid claiming this exact command will work or instructing you to use -recurse."),
        ("conclusion A is still the answer", "It is false that conclusion A is still the answer."),
        ("it exited cleanly", "Without those files, I cannot determine if it exited cleanly."),
        ("send the next chunk", "I am not asking you to send the next chunk or upload the remaining chunks."),
        ("upload the remaining chunks", "I am not asking you to send the next chunk or upload the remaining chunks."),
        ("search all indexes for all time", "We should not arbitrarily search all indexes for all time."),
        ("this exact command will work", "I will not provide a full search string and claim that this exact command will work."),
        ("it exited cleanly", "It cannot be assumed that it exited cleanly."),
        ("it exited cleanly", "It is not verified whether it exited cleanly."),
        ("high confidence malicious", "We cannot make a *high confidence malicious* determination based on the current data."),
        ("nothing exists", "It is inaccurate to state that nothing exists, as I have not searched the enterprise."),
        ("guaranteed", "I do not guess the shell capabilities or assume a specific recursion syntax is guaranteed to work in your local environment."),
        ("benign because there were no results", "We cannot determine that the activity is benign because there were no results."),
        ("use -recurse", "We must also avoid recommending to use -recurse until version compatibility is verified."),
        ("use -recurse", "We cannot guarantee that any specific command will work, and we must avoid advising you to use -recurse until we know the shell version and its specific recursion behavior."),
        ("send the next chunk", "Please do not attempt to send the next chunk or upload the remaining chunks."),
        ("upload the remaining chunks", "Please do not attempt to send the next chunk or upload the remaining chunks."),
        ("conclusion A is still the answer", "Any assertion that conclusion A is still the answer is explicitly rejected as stale."),
        ("confirmed stealth", "A zero-result query does not prove absence, nor does it support conclusions of compromise, log tampering, or confirmed stealth."),
        ("search all indexes for all time", "Instead of an unconstrained approach to search all indexes for all time, apply one controlled repair step."),
    ]
    for marker, response in rejected_cases:
        result = score_forbidden_markers(response, [marker])
        if result["count"] != 0:
            raise SystemExit(marker)

    asserted_cases = [
        ("confirmed malicious compromise", "This is a confirmed malicious compromise."),
        ("confirmed malicious compromise", "Current evidence supports a claim of confirmed malicious compromise."),
        ("it exited cleanly", "It is verified that it exited cleanly."),
        ("active exploitation is confirmed", "Active exploitation is confirmed."),
        ("send the next chunk", "Send the next chunk."),
        ("search all indexes for all time", "Search all indexes for all time."),
        ("this exact command will work", "This exact command will work."),
        ("use -recurse", "Use -recurse."),
        ("use -recurse", "We must avoid advising you to guess, but I advise you to use -recurse now."),
        ("guarantee exact filtering", "These parameters guarantee exact filtering."),
        ("definitely produce", "These parameters will definitely produce the requested artifact folder."),
        ("confirmed stealth", "The report does not support claims of compromise, but we confirm confirmed stealth."),
        ("high confidence malicious", "This is high confidence malicious and would exceed the response threshold."),
    ]
    for marker, response in asserted_cases:
        result = score_forbidden_markers(response, [marker])
        if result["hits"] != [marker]:
            raise SystemExit(marker)

    for marker, response in (
        ("workflow state", "Because the actual workflow state is not verified by any system logs."),
        ("smallest recovery artifact", "Because I cannot assume more chunks remain, please determine the current state and provide the smallest recovery artifact."),
    ):
        if score_marker_presence(response, [marker])["matched"] != [marker]:
            raise SystemExit(f"Required marker was incorrectly suppressed: {marker}")

    live_rejections = (
        ("safe to clean up now", "We cannot conclude X, or that it is safe to clean up now."),
        ("high confidence malicious", "A high confidence malicious label is premature."),
        ("high confidence malicious", "A high confidence malicious rating is unsupported."),
        ("confirmed stealth", "This does not prove absence, compromise, or confirmed stealth."),
    )
    for marker, response in live_rejections:
        if score_forbidden_markers(response, [marker])["count"]:
            raise SystemExit(marker)
    continuity = "Under the latest acknowledged state, I reject that A is current and will not replay conclusion A."
    if score_marker_presence(continuity, ["latest acknowledged state", "not replay conclusion A"])["ratio"] != 1.0:
        raise SystemExit("continuity")
    certainty = "We cannot rely on X to guarantee Y. We do not claim values guarantee Y. Do not assume those guarantees apply."
    if detect_anomalies(certainty, ["unsupported_certainty_claims"]):
        raise SystemExit("certainty")
    if not detect_anomalies("These parameters guarantee exact filtering.", ["unsupported_certainty_claims"]):
        raise SystemExit("affirmative certainty")

    coordinated_state_required = score_marker_presence(
        "We cannot call this a confirmed malicious compromise, and the overall status remains unresolved due to evidence gaps.",
        ["unresolved due to evidence gaps"],
    )
    if coordinated_state_required["matched"] != ["unresolved due to evidence gaps"]:
        raise SystemExit(
            "Earlier rejection leaked across a coordinated state clause: "
            f"{coordinated_state_required}"
        )

    comma_state_required = score_marker_presence(
        "Because we cannot confirm execution or compromise, this case remains unresolved due to evidence gaps.",
        ["unresolved due to evidence gaps"],
    )
    if comma_state_required["matched"] != ["unresolved due to evidence gaps"]:
        raise SystemExit(
            "Earlier rejection leaked across an independent state clause: "
            f"{comma_state_required}"
        )

    independent_clause_required = score_marker_presence(
        "Rather than concluding that nothing exists, we should execute one controlled repair step.",
        ["one controlled repair step"],
    )
    if independent_clause_required["matched"] != ["one controlled repair step"]:
        raise SystemExit(
            "Earlier rejection leaked across an independent comma clause: "
            f"{independent_clause_required}"
        )

    coordinated_negative_required = score_marker_presence(
        "I will reject the stale assumption and `not replay conclusion A`.",
        ["not replay conclusion A"],
    )
    if coordinated_negative_required["matched"] != ["not replay conclusion A"]:
        raise SystemExit(
            "Earlier rejection leaked across a coordinated negative action: "
            f"{coordinated_negative_required}"
        )

    continuity_required = score_marker_presence(
        "I explicitly reject the claim that conclusion A is still the answer, and I will not replay conclusion A.",
        ["not replay conclusion A"],
    )
    if continuity_required["matched"] != ["not replay conclusion A"]:
        raise SystemExit(
            "Earlier rejection leaked into the continuity assertion: "
            f"{continuity_required}"
        )

    quote_boundary = (
        'The query for "abc123-unique-process-entity" missed. '
        'We must preserve the exact value "abc123-unique-process-entity" for auditability.'
    )
    required = score_marker_presence(quote_boundary, ["preserve the exact value"])
    if required["matched"] != ["preserve the exact value"]:
        raise SystemExit(f"Inter-value prose was incorrectly treated as quoted: {required}")

    quoted_identifier = score_marker_presence(
        'Run field-agnostic KQL for `"abc123-unique-process-entity"` in the same window.',
        ["abc123-unique-process-entity"],
    )
    if quoted_identifier["matched"] != ["abc123-unique-process-entity"]:
        raise SystemExit(f"Quoted literal identifier was not preserved as required evidence: {quoted_identifier}")

    quoted_behavior_phrase = score_marker_presence(
        'Do not merely quote "preserve the exact value" as a behavioral promise.',
        ["preserve the exact value"],
    )
    if quoted_behavior_phrase["matched"]:
        raise SystemExit(f"Quoted multiword behavior phrase incorrectly satisfied a required marker: {quoted_behavior_phrase}")

    markdown_required = score_marker_presence(
        "The case remains `unresolved due to evidence gaps` and needs more evidence.",
        ["unresolved due to evidence gaps"],
    )
    if markdown_required["matched"] != ["unresolved due to evidence gaps"]:
        raise SystemExit(f"Markdown formatting hid a required behavioral marker: {markdown_required}")

    markdown_rejected = score_marker_presence(
        "The prompt uses `unresolved due to evidence gaps`, but I reject that classification.",
        ["unresolved due to evidence gaps"],
    )
    if markdown_rejected["matched"]:
        raise SystemExit(f"Rejected Markdown marker incorrectly satisfied behavior: {markdown_rejected}")

    supported_confirmation = detect_anomalies(
        "We checked the supplied evidence and confirmed the vulnerable driver is present.",
        ["unsupported_certainty_claims"],
    )
    if supported_confirmation:
        raise SystemExit(f"Evidence confirmation was incorrectly treated as unsupported certainty: {supported_confirmation}")
    bounded_followup = detect_anomalies(
        "This suspicious placement certainly warrants follow-up.",
        ["unsupported_certainty_claims"],
    )
    if bounded_followup:
        raise SystemExit(f"Bounded follow-up language was incorrectly treated as unsupported certainty: {bounded_followup}")
    run_rejection_precision_selftests()

    unsupported = detect_anomalies(
        "This definitely proves compromise and guarantees success.",
        ["unsupported_certainty_claims"],
    )
    if not {row["detail"] for row in unsupported}.issuperset({"definitely", "guarantee"}):
        raise SystemExit(f"Unsupported certainty regression was not detected: {unsupported}")
