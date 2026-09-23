from __future__ import annotations

from pathlib import Path

SCORER_MODULE_CHARACTER_CEILING = 15000
SCORER_MODULES = [
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_scoring.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_text_scoring.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_rejection_patterns.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_rejection_precision.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_lane_context.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_lane_scoring.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_collector_scoring.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_marker_precision.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_precision_controls.py"),
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
