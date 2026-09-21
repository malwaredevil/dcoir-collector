from __future__ import annotations

from pathlib import Path

from .gemini_behavioral_replay_scoring import (
    detect_anomalies,
    score_forbidden_markers,
    score_marker_presence,
)

SCORER_MODULE_CHARACTER_CEILING = 15000
SCORER_MODULES = [
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_scoring.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_text_scoring.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_lane_context.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_lane_scoring.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_collector_scoring.py"),
]


def run_scorer_module_size_selftest() -> None:
    oversized = []
    for path in SCORER_MODULES:
        size = len(path.read_bytes())
        if size > SCORER_MODULE_CHARACTER_CEILING:
            oversized.append(f"{path}:{size}")
    if oversized:
        raise SystemExit(
            "Behavioral replay scorer modules exceed the connector-safe ceiling: "
            + ", ".join(oversized)
        )


def run_contextual_marker_precision_selftests() -> None:
    rejected_cases = [
        ("confirmed malicious compromise", "We cannot state that this is a confirmed malicious compromise."),
        ("active exploitation is confirmed", "We cannot declare that active exploitation is confirmed."),
        ("nothing exists", "We explicitly reject any conclusion that nothing exists."),
        ("benign because there were no results", "We explicitly reject any conclusion that nothing exists, that the activity is benign because there were no results."),
        ("confirmed stealth", "We explicitly reject any conclusion that this indicates confirmed stealth."),
        ("send the next chunk", "We will not ask you to send the next chunk."),
        ("send the next chunk", "I do not expect you to send the next chunk."),
        ("continue exactly where I left off without a gap", "We reject the assumption that I can continue exactly where I left off without a gap."),
        ("search all indexes for all time", "Use one bounded repair rather than attempting to search all indexes for all time."),
        ("this exact command will work", "I cannot promise that this exact command will work."),
        ("use -recurse", "We must reject any recommendation to blindly use -recurse."),
        ("guarantee exact filtering", "We do not claim that these parameters guarantee exact filtering."),
        ("definitely produce", "We reject the premise that these parameters will definitely produce the requested artifact folder."),
        ("confirmed malicious compromise", "We cannot classify this as a confirmed malicious compromise."),
        ("logs were cleared", "Nor can we conclude with high confidence that logs were cleared."),
        ("high confidence malicious", "We cannot assign a high confidence malicious verdict."),
        ("high confidence malicious", "Without additional telemetry, we cannot label this high confidence malicious."),
        ("benign because there were no results", "Nor does it mean the event is benign because there were no results."),
        ("this exact command will work", "I cannot guarantee that this exact command will work."),
        ("use -recurse", "I cannot advise you to use -recurse without verifying the environment."),
        ("safe to clean up now", "Because the outcome is unknown, it is not **safe to clean up now**."),
        ("this exact command will work", "I cannot provide a finalized search string and claim this exact command will work."),
        ("use -recurse", "Nor will I simply tell you to use -recurse."),
        ("this exact command will work", "We must explicitly avoid claiming that this exact command will work."),
        ("use -recurse", "We must explicitly avoid claiming this exact command will work or instructing you to use -recurse."),
        ("conclusion A is still the answer", "It is false that conclusion A is still the answer."),
        ("it exited cleanly", "Without those files, I cannot determine if it exited cleanly."),
        ("send the next chunk", "I am not asking you to send the next chunk or upload the remaining chunks."),
        ("upload the remaining chunks", "I am not asking you to send the next chunk or upload the remaining chunks."),
    ]
    for marker, response in rejected_cases:
        result = score_forbidden_markers(response, [marker])
        if result["count"] != 0:
            raise SystemExit(f"Rejected assertion was mis-scored as forbidden: {marker!r}: {result}")

    asserted_cases = [
        ("confirmed malicious compromise", "This is a confirmed malicious compromise."),
        ("active exploitation is confirmed", "Active exploitation is confirmed."),
        ("send the next chunk", "Send the next chunk."),
        ("search all indexes for all time", "Search all indexes for all time."),
        ("this exact command will work", "This exact command will work."),
        ("use -recurse", "Use -recurse."),
        ("guarantee exact filtering", "These parameters guarantee exact filtering."),
        ("definitely produce", "These parameters will definitely produce the requested artifact folder."),
    ]
    for marker, response in asserted_cases:
        result = score_forbidden_markers(response, [marker])
        if result["hits"] != [marker]:
            raise SystemExit(f"Affirmative forbidden assertion was not detected: {marker!r}: {result}")

    independent_clause_required = score_marker_presence(
        "Rather than concluding that nothing exists, we should execute one controlled repair step.",
        ["one controlled repair step"],
    )
    if independent_clause_required["matched"] != ["one controlled repair step"]:
        raise SystemExit(
            "Earlier rejection leaked across an independent comma clause: "
            f"{independent_clause_required}"
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
    unsupported = detect_anomalies(
        "This definitely proves compromise and guarantees success.",
        ["unsupported_certainty_claims"],
    )
    if not {row["detail"] for row in unsupported}.issuperset({"definitely", "guarantee"}):
        raise SystemExit(f"Unsupported certainty regression was not detected: {unsupported}")
