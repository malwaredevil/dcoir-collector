#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

OLD_BLOCK = '''def _assertive_phrase_occurrences(text: str, term: str) -> Iterable[re.Match[str]]:
    for occurrence in _iter_term_occurrences(text, term):
        if _occurrence_is_quoted(text, occurrence.start(), occurrence.end()):
            continue
        if _occurrence_is_negated(text, occurrence.start()):
            continue
        if _occurrence_is_rejected_after(text, occurrence.end()):
            continue
        prefix = text[max(0, occurrence.start() - 120):occurrence.start()]
        if re.search(
            r"\\b(?:do not|don't|dont|must not|should not|never|avoid)\\b[^.!?;]{0,100}$",
            prefix,
        ):
            continue
        yield occurrence


def _clause_has_explicit_lane_mix(clause: str) -> bool:
    if not (_clause_has_endpoint_lane(clause) and _clause_has_local_lane(clause)):
        return False
    if _find_contextual_term_hits(
        clause,
        ["mix", "combine"],
        skip_negated=True,
        skip_quoted=True,
    ):
        return True
    for term in ("same shell", "single shell", "one shell", "same command", "single command", "same lane"):
        if any(_assertive_phrase_occurrences(clause, term)):
            return True
    return False


def _clause_has_relational_lane_separation(clause: str) -> bool:
    if not (_clause_has_endpoint_lane(clause) and _clause_has_local_lane(clause)):
        return False
    if _find_contextual_term_hits(
        clause,
        ["do not mix", "don't mix", "dont mix", "must not mix", "should not mix"],
        skip_negated=True,
        skip_quoted=True,
    ):
        return True
    if _find_contextual_term_hits(
        clause,
        ["different lane", "distinct lane"],
        skip_negated=True,
        skip_quoted=True,
    ):
        return True

    endpoint_positions = [
        match.start()
        for match in re.finditer(r"\\b(?:endpoint|response(?:-| )action)\\b", clause)
    ]
    local_positions = [
        match.start()
        for match in re.finditer(r"\\b(?:local|workstation)\\b", clause)
    ]
    for occurrence in _assertive_phrase_occurrences(clause, "separate"):
        if (
            endpoint_positions
            and local_positions
            and min(abs(occurrence.start() - pos) for pos in endpoint_positions) <= 120
            and min(abs(occurrence.start() - pos) for pos in local_positions) <= 120
        ):
            return True
    return False


def _clause_has_referential_lane_separation(clause: str) -> bool:
    if not re.search(
        r"\\b(?:(?:these|those|the)\\s+(?:two\\s+)?lanes?|both\\s+lanes?|two\\s+lanes?)\\b",
        clause,
    ):
        return False
    return bool(
        _find_contextual_term_hits(
            clause,
            [
                "separate",
                "distinct",
                "different",
                "do not mix",
                "don't mix",
                "dont mix",
                "must not mix",
                "should not mix",
            ],
            skip_negated=True,
            skip_quoted=True,
        )
    )


def has_execution_lane_separation(response_text: str) -> bool:
    clauses = list(_iter_clauses(response_text))
    has_endpoint_lane = any(_clause_has_endpoint_lane(clause) for clause in clauses)
    has_local_lane = any(_clause_has_local_lane(clause) for clause in clauses)
    if not (has_endpoint_lane and has_local_lane):
        return False
    if any(_clause_has_explicit_lane_mix(clause) for clause in clauses):
        return False
    if any(_clause_has_relational_lane_separation(clause) for clause in clauses):
        return True
    return any(_clause_has_referential_lane_separation(clause) for clause in clauses)
'''

NEW_BLOCK = '''_REFERENTIAL_LANES_PATTERN = (
    r"(?:(?:these|those|the)\\s+(?:two\\s+)?lanes?|both\\s+lanes?|two\\s+lanes?)"
)
_SHARED_CONTEXT_TERMS = (
    "same shell",
    "single shell",
    "one shell",
    "same command",
    "single command",
    "same lane",
)


def _iter_lane_relation_segments(clause: str) -> Iterable[str]:
    for segment in re.split(r"\\b(?:but|however|whereas|yet)\\b", clause):
        normalized = normalize_text(segment)
        if normalized:
            yield normalized


def _occurrence_has_direct_shared_context_negation(
    text: str,
    start: int,
) -> bool:
    prefix = text[max(0, start - 180):start]
    direct_use = re.search(
        r"\\b(?:do not|don't|dont|must not|should not|never|avoid)\\s+"
        r"(?:use|share)\\s+(?:the\\s+)?$",
        prefix,
    )
    if direct_use:
        return True

    scoped_action = re.search(
        r"\\b(?:do not|don't|dont|must not|should not|never|avoid)\\s+"
        r"(?:run|execute|place|put|mix|combine)\\b[^.!?;]{0,150}$",
        prefix,
    )
    if not scoped_action:
        return False
    scope = prefix[scoped_action.start():]
    return _clause_has_endpoint_lane(scope) and _clause_has_local_lane(scope)


def _assertive_phrase_occurrences(text: str, term: str) -> Iterable[re.Match[str]]:
    for occurrence in _iter_term_occurrences(text, term):
        if _occurrence_is_quoted(text, occurrence.start(), occurrence.end()):
            continue
        if _occurrence_is_negated(text, occurrence.start()):
            continue
        if _occurrence_is_rejected_after(text, occurrence.end()):
            continue
        if _occurrence_has_direct_shared_context_negation(text, occurrence.start()):
            continue
        yield occurrence


def _mix_occurrence_targets_lane(text: str, occurrence: re.Match[str]) -> bool:
    after = text[occurrence.end():min(len(text), occurrence.end() + 100)]
    before = text[max(0, occurrence.start() - 80):occurrence.start()]
    direct_lane_target = re.compile(
        r"^\\s+(?:up\\s+)?(?:the\\s+)?"
        r"(?:(?:commands?|syntax)\\s+(?:from|for)\\s+)?"
        r"(?:endpoint|response(?:-| )action|local|workstation)\\b"
    )
    direct_lane_reference = re.compile(
        rf"^\\s+(?:up\\s+)?{_REFERENTIAL_LANES_PATTERN}\\b"
    )
    trailing_lane_reference = re.compile(
        rf"{_REFERENTIAL_LANES_PATTERN}\\s*$"
    )
    return bool(
        direct_lane_target.search(after)
        or direct_lane_reference.search(after)
        or trailing_lane_reference.search(before)
    )


def _segment_has_explicit_lane_mix(segment: str) -> bool:
    if not (_clause_has_endpoint_lane(segment) and _clause_has_local_lane(segment)):
        return False
    for term in ("mix", "combine"):
        for occurrence in _assertive_phrase_occurrences(segment, term):
            if _mix_occurrence_targets_lane(segment, occurrence):
                return True
    for term in _SHARED_CONTEXT_TERMS:
        if any(_assertive_phrase_occurrences(segment, term)):
            return True
    return False


def _clause_has_explicit_lane_mix(clause: str) -> bool:
    return any(
        _segment_has_explicit_lane_mix(segment)
        for segment in _iter_lane_relation_segments(clause)
    )


def _clause_has_referential_lane_mix(clause: str) -> bool:
    for term in ("mix", "combine"):
        for occurrence in _assertive_phrase_occurrences(clause, term):
            if _mix_occurrence_targets_lane(clause, occurrence):
                return True
    return False


def _segment_has_negated_shared_context(segment: str) -> bool:
    if not (_clause_has_endpoint_lane(segment) and _clause_has_local_lane(segment)):
        return False
    for term in _SHARED_CONTEXT_TERMS:
        for occurrence in _iter_term_occurrences(segment, term):
            if _occurrence_is_quoted(segment, occurrence.start(), occurrence.end()):
                continue
            if _occurrence_is_rejected_after(segment, occurrence.end()):
                continue
            if _occurrence_has_direct_shared_context_negation(
                segment,
                occurrence.start(),
            ):
                return True
    return False


def _segment_has_relational_lane_separation(segment: str) -> bool:
    if not (_clause_has_endpoint_lane(segment) and _clause_has_local_lane(segment)):
        return False
    if _find_contextual_term_hits(
        segment,
        ["do not mix", "don't mix", "dont mix", "must not mix", "should not mix"],
        skip_negated=True,
        skip_quoted=True,
    ):
        return True
    if _segment_has_negated_shared_context(segment):
        return True
    if _find_contextual_term_hits(
        segment,
        ["different lane", "distinct lane"],
        skip_negated=True,
        skip_quoted=True,
    ):
        return True

    endpoint_positions = [
        match.start()
        for match in re.finditer(r"\\b(?:endpoint|response(?:-| )action)\\b", segment)
    ]
    local_positions = [
        match.start()
        for match in re.finditer(r"\\b(?:local|workstation)\\b", segment)
    ]
    for occurrence in _assertive_phrase_occurrences(segment, "separate"):
        if (
            endpoint_positions
            and local_positions
            and min(abs(occurrence.start() - pos) for pos in endpoint_positions) <= 120
            and min(abs(occurrence.start() - pos) for pos in local_positions) <= 120
        ):
            return True
    return False


def _clause_has_relational_lane_separation(clause: str) -> bool:
    return any(
        _segment_has_relational_lane_separation(segment)
        for segment in _iter_lane_relation_segments(clause)
    )


def _clause_has_referential_lane_separation(clause: str) -> bool:
    if not re.search(rf"\\b{_REFERENTIAL_LANES_PATTERN}\\b", clause):
        return False
    return bool(
        _find_contextual_term_hits(
            clause,
            [
                "separate",
                "distinct",
                "different",
                "do not mix",
                "don't mix",
                "dont mix",
                "must not mix",
                "should not mix",
            ],
            skip_negated=True,
            skip_quoted=True,
        )
    )


def has_execution_lane_separation(response_text: str) -> bool:
    clauses = list(_iter_clauses(response_text))
    has_endpoint_lane = any(_clause_has_endpoint_lane(clause) for clause in clauses)
    has_local_lane = any(_clause_has_local_lane(clause) for clause in clauses)
    if not (has_endpoint_lane and has_local_lane):
        return False
    if any(_clause_has_explicit_lane_mix(clause) for clause in clauses):
        return False
    if any(_clause_has_referential_lane_mix(clause) for clause in clauses):
        return False
    if any(_clause_has_relational_lane_separation(clause) for clause in clauses):
        return True
    return any(_clause_has_referential_lane_separation(clause) for clause in clauses)
'''

VALIDATOR_CONTENT = '''#!/usr/bin/env python3
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
        '\"Keep these two lanes separate.\"',
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
        "Do not run endpoint response-action commands and local workstation PowerShell "
        "in the same shell.",
        True,
        "negated shared-shell relation",
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
    print("Gemini execution-lane separation scoring regressions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one old block in {path}, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", required=True)
    args = parser.parse_args()
    root = Path(args.worktree).resolve()
    scoring = root / "project_sources/gemini/tools/lib/gemini_behavioral_replay_scoring.py"
    validator = root / "project_sources/gemini/tools/validate_gemini_lane_separation_scoring.py"
    replace_exact(scoring, OLD_BLOCK, NEW_BLOCK)
    validator.write_text(VALIDATOR_CONTENT, encoding="utf-8", newline="\n")
    print("Applied issue #484 adversarial lane-relation scoring fix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
