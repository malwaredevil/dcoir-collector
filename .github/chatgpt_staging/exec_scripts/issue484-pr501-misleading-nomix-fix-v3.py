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
    helper = '''def _occurrence_has_local_lane_relation_rejection(text: str, start: int) -> bool:\n    """Reject repudiation frames only within the current comma-delimited discourse segment."""\n    prefix = text[max(0, start - 160):start]\n    comma = prefix.rfind(",")\n    if comma >= 0:\n        prefix = prefix[comma + 1:]\n    return bool(\n        re.search(\n            r"\\b(?:wrong|incorrect|false|misleading)\\s+to\\s+(?:say|claim)\\b"\n            r"[^.!?;]{0,140}$",\n            prefix,\n        )\n    )\n\n\n'''.splitlines(keepends=True)
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
        if lines[i].startswith('    for term in ("different lane", "distinct lane"):')
    ),
    -1,
)
if start_idx < 0 or end_idx < 0 or end_idx <= start_idx:
    raise SystemExit(f"no-mix branch boundaries not found: start={start_idx} end={end_idx}")

replacement = '''    for term in (\n        "do not mix",\n        "don't mix",\n        "dont mix",\n        "must not mix",\n        "should not mix",\n        "do not combine",\n        "don't combine",\n        "dont combine",\n        "must not combine",\n        "should not combine",\n    ):\n        for occurrence in _iter_term_occurrences(segment, term):\n            if _occurrence_is_quoted(segment, occurrence.start(), occurrence.end()):\n                continue\n            if _occurrence_is_negated(segment, occurrence.start()):\n                continue\n            if _occurrence_is_rejected_after(segment, occurrence.end()):\n                continue\n            if _occurrence_has_local_lane_relation_rejection(\n                segment, occurrence.start()\n            ):\n                continue\n            return True\n'''.splitlines(keepends=True)
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
    insert = '''    _expect(\n        "It is misleading to say do not mix endpoint response-action syntax and local "\n        "workstation PowerShell.",\n        False,\n        "misleading no-mix rejection",\n    )\n    _expect(\n        "Although it is misleading to say these tools are interchangeable, do not mix "\n        "endpoint response-action syntax and local workstation PowerShell.",\n        True,\n        "comma boundary preserves affirmative no-mix instruction",\n    )\n'''.splitlines(keepends=True)
    vlines[print_idx:print_idx] = insert
validator.write_text("".join(vlines), encoding="utf-8")
