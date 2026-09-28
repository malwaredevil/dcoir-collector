from __future__ import annotations

from pathlib import Path

from . import gemini_behavioral_replay_semantic_precision as _semantic_precision
from .gemini_behavioral_replay_scoring import score_marker_presence

SCORER_MODULE_CHARACTER_CEILING = 15000
SCORER_MODULES = [
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_scoring.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_text_scoring.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_negation_context.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_rejection_patterns.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_rejection_precision.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_lane_context.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_lane_scoring.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_lane_equivalence.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_lane_equivalence_extended.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_collector_scoring.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_marker_precision.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_marker_semantics.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_precision_controls.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_semantic_precision.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_semantic_reciprocal_precision.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_semantic_family_precision.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_reciprocal_semantics.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_truth_frame_semantics.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_capture_controls.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_capture_paths.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_capture_adversarial.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_assertion_polarity.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_semantic_assertions.py"),
    Path("project_sources/agent_runtime/tools/usb_reporting_markdown_fences.py"),
    Path("project_sources/agent_runtime/tools/usb_reporting_transfer_semantics.py"),
    Path("project_sources/agent_runtime/tests/usb_reporting_transfer_semantics_selftest.py"),
    Path("project_sources/agent_runtime/tools/usb_reporting_evidence_semantics.py"),
    Path("project_sources/agent_runtime/tools/usb_reporting_clarification_semantics.py"),
    Path("project_sources/agent_runtime/tests/usb_reporting_evidence_semantics_selftest.py"),
    Path("project_sources/agent_runtime/tests/usb_reporting_clarification_semantics_selftest.py"),
    Path("project_sources/agent_runtime/tests/usb_reporting_markdown_fences_selftest.py"),
]

# Recorded AGENTS.md connector-size exemptions. Each is capped near its current
# size so growth is still detected; split the file rather than raising a cap.
SCORER_MODULE_SIZE_EXEMPTIONS = {
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_live_regressions.py"): 47000,
    Path("project_sources/agent_runtime/tools/score_usb_reporting_behavior.py"): 20000,
    Path("project_sources/agent_runtime/tests/score_usb_reporting_behavior_selftest.py"): 16500,
}


def run_elastic_command_lane_separation_selftest() -> None:
    """Compatibility facade for the extracted semantic-precision self-test."""
    _semantic_precision.run_elastic_command_lane_separation_selftest()


def run_negated_rejection_polarity_selftest() -> None:
    """Compatibility facade for the extracted semantic-precision self-test."""
    _semantic_precision.run_negated_rejection_polarity_selftest()


def run_scorer_module_size_selftest() -> None:
    oversized = []
    limits = {path: SCORER_MODULE_CHARACTER_CEILING for path in SCORER_MODULES}
    limits.update(SCORER_MODULE_SIZE_EXEMPTIONS)
    for path, limit in limits.items():
        size = len(path.read_bytes())
        if size > limit:
            oversized.append(f"{path}:{size}>{limit}")
    if oversized:
        raise SystemExit(
            "Behavioral replay scorer modules exceed the connector-safe ceiling: "
            + ", ".join(oversized)
        )


def run_marker_frame_rejection_selftest() -> None:
    marker = "latest acknowledged state"
    for response in (
        "Under the latest acknowledged state, I explicitly reject that A is current.",
        "Under the latest acknowledged state I explicitly reject that A is current.",
        "Per the latest acknowledged state, we reject the claim that A is current.",
    ):
        if score_marker_presence(response, [marker])["matched"] != [marker]:
            raise SystemExit(f"Rejection-frame marker was not recognized: {response}")
