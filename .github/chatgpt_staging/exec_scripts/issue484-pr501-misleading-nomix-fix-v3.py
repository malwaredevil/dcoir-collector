#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
source = root / "project_sources/gemini/tools/lib/gemini_behavioral_replay_scoring.py"
validator = root / "project_sources/gemini/tools/validate_gemini_lane_separation_scoring.py"
lines = source.read_text(encoding="utf-8").splitlines(keepends=True)

func_idx = next(
    (i for i, line in enumerate(lines) if line.startswith("def _segment_has_relational_lane_separation(")),
    -1,
)
if func_idx < 0:
    raise SystemExit("relational separation function not found")

if not any("def _occurrence_has_local_lane_relation_rejection" in line for line in lines):
    helper = r'''def _occurrence_has_local_lane_relation_rejection(text: str, start: int) -> bool:
    """Reject repudiation frames only within the current comma-delimited discourse segment."""
    prefix = text[max(0, start - 160):start]
    comma = prefix.rfind(",")
    if comma >= 0:
        prefix = prefix[comma + 1:]
    return bool(
        re.search(
            r"\b(?:wrong|incorrect|false|misleading)\s+to\s+(?:say|claim)\b"
            r"[^.!?;]{0,140}$",
            prefix,
        )
    )


'''.splitlines(keepends=True)
    lines[func_idx:func_idx] = helper
    func_idx += len(helper)

start_idx = next(
    (i for i in range(func_idx, len(lines)) if lines[i].strip() == "if _find_contextual_term_hits("),
    -1,
)
end_idx = next(
    (
        i
        for i in range(func_idx, len(lines))
        if lines[i].startswith("    if _segment_has_negated_shared_context(segment):")
    ),
    -1,
)
if start_idx < 0 or end_idx < 0 or end_idx <= start_idx:
    raise SystemExit(f"no-mix branch boundaries not found: start={start_idx} end={end_idx}")

replacement = '''    for term in (
        "do not mix",
        "don't mix",
        "dont mix",
        "must not mix",
        "should not mix",
        "do not combine",
        "don't combine",
        "dont combine",
        "must not combine",
        "should not combine",
    ):
        for occurrence in _iter_term_occurrences(segment, term):
            if _occurrence_is_quoted(segment, occurrence.start(), occurrence.end()):
                continue
            if _occurrence_is_negated(segment, occurrence.start()):
                continue
            if _occurrence_is_rejected_after(segment, occurrence.end()):
                continue
            if _occurrence_has_local_lane_relation_rejection(
                segment, occurrence.start()
            ):
                continue
            return True
'''.splitlines(keepends=True)
lines[start_idx:end_idx] = replacement
source.write_text("".join(lines), encoding="utf-8")

vlines = validator.read_text(encoding="utf-8").splitlines(keepends=True)
if not any("misleading no-mix rejection" in line for line in vlines):
    print_idx = next(
        (i for i, line in enumerate(vlines) if "Gemini execution-lane separation scoring regressions passed." in line),
        -1,
    )
    if print_idx < 0:
        raise SystemExit("validator print marker not found")
    insert = '''    _expect(
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
'''.splitlines(keepends=True)
    vlines[print_idx:print_idx] = insert
validator.write_text("".join(vlines), encoding="utf-8")
