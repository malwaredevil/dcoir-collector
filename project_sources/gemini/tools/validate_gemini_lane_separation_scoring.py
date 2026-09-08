#!/usr/bin/env python3
"""Deterministic regression checks for response-scoped execution-lane separation scoring."""
from __future__ import annotations

from lib.gemini_behavioral_replay_scoring import has_execution_lane_separation


def _expect(response: str, expected: bool, label: str) -> None:
    actual = has_execution_lane_separation(response)
    if actual is not expected:
        raise SystemExit(
            f"{label}: expected has_execution_lane_separation={expected}, got {actual}"
        )


def main() -> int:
    _expect(
        "Endpoint response-action execution uses execute --command for remote actions. "
        "Local workstation PowerShell runs the collector directly. "
        "Keep these two lanes separate.",
        True,
        "response-scope referential separation",
    )
    _expect(
        "Keep endpoint response-action syntax separate from local workstation PowerShell.",
        True,
        "same-clause relational separation",
    )
    _expect(
        "Endpoint response-action execution uses execute --command. "
        "Local workstation PowerShell runs the collector. "
        "Do not mix these two lanes.",
        True,
        "response-scope no-mix relationship",
    )
    _expect(
        "Endpoint response-action execution uses execute --command. "
        "Local workstation PowerShell runs the collector. "
        "Do not combine these two lanes.",
        True,
        "response-scope no-combine relationship",
    )
    _expect(
        "Use a separate log folder, but run endpoint response-action commands and local "
        "PowerShell in the same shell.",
        False,
        "unrelated separate wording with explicit lane mixing",
    )
    _expect(
        "Keep package staging separate from evidence retrieval. "
        "Endpoint response-action execution uses execute --command. "
        "Local workstation PowerShell runs the collector.",
        False,
        "unrelated separation wording",
    )
    _expect(
        "Endpoint response-action execution uses execute --command. "
        "Local workstation PowerShell runs the collector. "
        '"Keep these two lanes separate."',
        False,
        "quoted separation assertion",
    )
    _expect(
        "It is wrong to say do not mix endpoint response-action syntax and local "
        "workstation PowerShell.",
        False,
        "rejected no-mix assertion",
    )
    _expect(
        "It is wrong to say endpoint response-action commands are separate from local "
        "workstation PowerShell.",
        False,
        "rejected separation assertion",
    )
    _expect(
        "It would be misleading to say endpoint response-action commands are separate "
        "from local workstation PowerShell.",
        False,
        "misleading separation assertion",
    )
    _expect(
        "Do not run endpoint response-action commands and local workstation PowerShell "
        "in the same shell.",
        True,
        "negated shared-shell relation",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as local "
        "workstation PowerShell.",
        True,
        "trailing-lane shared-shell negation",
    )
    _expect(
        "Avoid using the same shell for endpoint response-action commands and local "
        "PowerShell.",
        True,
        "avoid-using shared-shell negation",
    )
    _expect(
        "Do not run local workstation PowerShell in the same shell as endpoint "
        "response-action commands.",
        True,
        "trailing-endpoint shared-shell negation",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as your local "
        "PowerShell commands.",
        True,
        "possessive trailing-local shared-shell negation",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as my local "
        "PowerShell commands.",
        True,
        "first-person possessive trailing-local shared-shell negation",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as her local "
        "PowerShell commands.",
        True,
        "third-person possessive trailing-local shared-shell negation",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as your own local "
        "PowerShell commands.",
        True,
        "possessive-intensifier trailing-local shared-shell negation",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as another local "
        "PowerShell command.",
        True,
        "unlisted-determiner trailing-local shared-shell negation",
    )
    _expect(
        "Do not run local workstation PowerShell in the same shell as a dedicated endpoint "
        "response-action console.",
        True,
        "adjectival trailing-endpoint shared-shell negation",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as anything except "
        "local PowerShell commands.",
        False,
        "exclusion operator cannot be skipped before local lane head",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as anything other "
        "than local PowerShell commands.",
        False,
        "other-than exclusion cannot be skipped before local lane head",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as anything besides "
        "local PowerShell commands.",
        False,
        "besides exclusion cannot be skipped before local lane head",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as anything aside "
        "from local PowerShell commands.",
        False,
        "aside-from exclusion cannot be skipped before local lane head",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as anything near "
        "local PowerShell commands.",
        False,
        "preposition cannot be skipped before local lane head",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as anything barring "
        "local PowerShell commands.",
        False,
        "barring exclusion cannot be skipped before local lane head",
    )
    _expect(
        "Do not run local workstation PowerShell in the same shell as an endpoint "
        "response-action console.",
        True,
        "article trailing-endpoint shared-shell negation",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as my local "
        "response-action tooling and PowerShell commands.",
        False,
        "possessive target cannot hide endpoint contamination",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell, and local "
        "workstation PowerShell runs the collector directly.",
        False,
        "unbound trailing lane does not imply separation",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as usual, and "
        "local workstation PowerShell runs the collector directly.",
        False,
        "coordinated clause cannot satisfy trailing lane relation",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as usual and "
        "local workstation PowerShell runs the collector directly.",
        False,
        "non-lane immediate target cannot borrow a later lane",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as local tooling "
        "and PowerShell commands.",
        True,
        "coordinated local target remains a bound lane relation",
    )
    _expect(
        "Do not run endpoint response-action commands in the same shell as local "
        "response-action tooling and PowerShell commands.",
        False,
        "local target cannot borrow a later endpoint marker",
    )
    _expect(
        "Do not use the same shell for endpoint response-action commands and local "
        "PowerShell.",
        True,
        "negated shared-shell object relation",
    )
    _expect(
        "Do not delete logs, but run endpoint response-action commands and local "
        "PowerShell in the same shell. Keep these two lanes separate.",
        False,
        "unrelated negation cannot hide explicit lane mixing",
    )
    _expect(
        "Combine the log files, but keep endpoint response-action commands separate "
        "from local PowerShell.",
        True,
        "unrelated combine wording does not imply lane mixing",
    )
    _expect(
        "Endpoint response-action execution uses execute --command. "
        "Local workstation PowerShell runs the collector. "
        "Keep these two lanes separate. Then mix these two lanes.",
        False,
        "referential lane-mix contradiction",
    )
    _expect(
        "Use a separate log folder, but combine endpoint response-action commands "
        "with local PowerShell.",
        False,
        "direct targeted lane mixing",
    )
    _expect(
        "Endpoint response-action execution uses execute --command. "
        "Local workstation PowerShell runs the collector. "
        "Run these two lanes in the same shell, but keep the log folders separate.",
        False,
        "referential shared-shell mix cannot be masked by unrelated separation",
    )
    _expect(
        "Endpoint response-action execution uses execute --command. "
        "Local workstation PowerShell runs the collector. "
        "Run them in the same shell. Keep these two lanes separate.",
        False,
        "pronominal shared-shell mix after lane establishment",
    )
    _expect(
        "Endpoint response-action execution uses execute --command. "
        "Local workstation PowerShell runs the collector. "
        "Do not run them in the same shell. Keep these two lanes separate.",
        True,
        "negated pronominal shared-shell action does not create lane mixing",
    )
    _expect(
        "Endpoint response-action execution uses execute --command. "
        "Local workstation PowerShell runs the collector. "
        "Do not use the same shell for these two lanes.",
        True,
        "referential negated shared-shell relation",
    )
    _expect(
        "Endpoint response-action execution uses execute --command. "
        "Local workstation PowerShell runs the collector. "
        "These two lanes use dedicated identifiers and the log folders are separate.",
        False,
        "unrelated referential separation wording",
    )
    _expect(
        "Do not run local workstation PowerShell in the same shell as the fully "
        "dedicated remote response action endpoint console.",
        True,
        "split response action head at the last scan-window slot",
    )
    _expect(
        "It is misleading to say do not mix endpoint response-action syntax and local "
        "workstation PowerShell.",
        False,
        "misleading no-mix rejection",
    )
    _expect(
        "Although it is misleading to say these tools are interchangeable, do not mix "
        "endpoint response-action syntax and local workstation PowerShell.",
        True,
        "comma boundary preserves affirmative no-mix instruction",
    )
    _expect(
        "Endpoint response-action execution uses execute --command. "
        "Local workstation PowerShell runs the collector. "
        "Do not run them separately, run them in the same shell. "
        "Keep these two lanes separate.",
        False,
        "nearest pronominal action governs shared-context mix verdict",
    )
    _expect(
        "Endpoint response-action execution uses execute --command. "
        "Local workstation PowerShell runs the collector. "
        "Keep them in the same order in your report and never run them in the same shell. "
        "Keep these two lanes separate.",
        True,
        "nearer pronominal negation governs shared-context mix verdict",
    )
    _expect(
        "Although it is misleading to say these tools are interchangeable, keep endpoint "
        "response-action commands separate from local workstation PowerShell.",
        True,
        "comma boundary preserves affirmative separate instruction",
    )
    print("Gemini execution-lane separation scoring regressions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())