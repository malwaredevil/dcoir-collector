#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def replace_exact(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", required=True)
    args = parser.parse_args()
    root = Path(args.worktree).resolve()
    scoring = root / "project_sources/gemini/tools/lib/gemini_behavioral_replay_scoring.py"
    validator = root / "project_sources/gemini/tools/validate_gemini_lane_separation_scoring.py"

    text = scoring.read_text(encoding="utf-8")

    old = '''def _iter_lane_relation_segments(clause: str) -> Iterable[str]:
    for segment in re.split(r"\\b(?:but|however|whereas|yet)\\b", clause):
        normalized = normalize_text(segment)
        if normalized:
            yield normalized


def _occurrence_has_direct_shared_context_negation(
'''
    new = '''def _iter_lane_relation_segments(clause: str) -> Iterable[str]:
    for segment in re.split(r"\\b(?:but|however|whereas|yet)\\b", clause):
        normalized = normalize_text(segment)
        if normalized:
            yield normalized


def _segment_has_lane_relation_scope(segment: str) -> bool:
    return bool(
        (_clause_has_endpoint_lane(segment) and _clause_has_local_lane(segment))
        or re.search(rf"\\b{_REFERENTIAL_LANES_PATTERN}\\b", segment)
    )


def _occurrence_has_direct_shared_context_negation(
'''
    text = replace_exact(text, old, new, "insert relation-scope helper")

    old = '''    scope = prefix[scoped_action.start():]
    return _clause_has_endpoint_lane(scope) and _clause_has_local_lane(scope)
'''
    new = '''    scope = prefix[scoped_action.start():]
    return bool(
        (_clause_has_endpoint_lane(scope) and _clause_has_local_lane(scope))
        or re.search(rf"\\b{_REFERENTIAL_LANES_PATTERN}\\b", scope)
    )
'''
    text = replace_exact(text, old, new, "broaden direct-negation scope")

    old = '''def _segment_has_explicit_lane_mix(segment: str) -> bool:
    if not (_clause_has_endpoint_lane(segment) and _clause_has_local_lane(segment)):
        return False
'''
    new = '''def _segment_has_explicit_lane_mix(segment: str) -> bool:
    if not _segment_has_lane_relation_scope(segment):
        return False
'''
    text = replace_exact(text, old, new, "broaden explicit-mix scope")

    old = '''def _segment_has_negated_shared_context(segment: str) -> bool:
    if not (_clause_has_endpoint_lane(segment) and _clause_has_local_lane(segment)):
        return False
'''
    new = '''def _segment_has_negated_shared_context(segment: str) -> bool:
    if not _segment_has_lane_relation_scope(segment):
        return False
'''
    text = replace_exact(text, old, new, "broaden negated shared-context scope")

    old = '''def _segment_has_relational_lane_separation(segment: str) -> bool:
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
'''
    new = '''def _separate_occurrence_targets_lane(
    segment: str,
    occurrence: re.Match[str],
) -> bool:
    before = segment[max(0, occurrence.start() - 140):occurrence.start()]
    after = segment[occurrence.end():min(len(segment), occurrence.end() + 140)]
    if re.search(
        rf"{_REFERENTIAL_LANES_PATTERN}(?:\\s+(?:are|remain|stay|kept|must be|should be))?\\s*$",
        before,
    ):
        return True
    if re.match(rf"^\\s+{_REFERENTIAL_LANES_PATTERN}\\b", after):
        return True

    endpoint_positions = [
        match.start()
        for match in re.finditer(r"\\b(?:endpoint|response(?:-| )action)\\b", segment)
    ]
    local_positions = [
        match.start()
        for match in re.finditer(r"\\b(?:local|workstation)\\b", segment)
    ]
    if not (endpoint_positions and local_positions):
        return False

    start = occurrence.start()
    endpoint_distance = min(abs(start - pos) for pos in endpoint_positions)
    local_distance = min(abs(start - pos) for pos in local_positions)
    if endpoint_distance <= 120 and local_distance <= 120:
        between_lanes = any(
            (endpoint < start < local) or (local < start < endpoint)
            for endpoint in endpoint_positions
            for local in local_positions
        )
        if between_lanes:
            return True

    lane_tail = re.search(
        r"\\b(?:endpoint|response(?:-| )action|local|workstation)"
        r"(?:\\s+[a-z0-9_-]+){0,4}\\s*$",
        before,
    )
    if lane_tail and endpoint_distance <= 120 and local_distance <= 120:
        return True

    lane_head = re.match(
        r"^\\s+(?:endpoint|response(?:-| )action|local|workstation)\\b",
        after,
    )
    if lane_head and endpoint_distance <= 120 and local_distance <= 120:
        return True
    return False


def _segment_has_relational_lane_separation(segment: str) -> bool:
    if not _segment_has_lane_relation_scope(segment):
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

    for occurrence in _assertive_phrase_occurrences(segment, "separate"):
        if _separate_occurrence_targets_lane(segment, occurrence):
            return True
    return False
'''
    text = replace_exact(text, old, new, "bind positive separation to lanes")

    old = '''def _clause_has_referential_lane_separation(clause: str) -> bool:
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
'''
    new = '''def _clause_has_referential_lane_separation(clause: str) -> bool:
    return any(
        bool(re.search(rf"\\b{_REFERENTIAL_LANES_PATTERN}\\b", segment))
        and _segment_has_relational_lane_separation(segment)
        for segment in _iter_lane_relation_segments(clause)
    )
'''
    text = replace_exact(text, old, new, "bind referential separation to segment")

    scoring.write_text(text, encoding="utf-8", newline="\n")

    tests = validator.read_text(encoding="utf-8")
    anchor = '''    _expect(
        "Use a separate log folder, but combine endpoint response-action commands "
        "with local PowerShell.",
        False,
        "direct targeted lane mixing",
    )
'''
    replacement = anchor + '''    _expect(
        "Endpoint response-action execution uses execute --command. "
        "Local workstation PowerShell runs the collector. "
        "Run these two lanes in the same shell, but keep the log folders separate.",
        False,
        "referential shared-shell mix cannot be masked by unrelated separation",
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
'''
    tests = replace_exact(tests, anchor, replacement, "append Codi regression controls")
    validator.write_text(tests, encoding="utf-8", newline="\n")
    print("Applied issue #484 Codi relation-binding fix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
