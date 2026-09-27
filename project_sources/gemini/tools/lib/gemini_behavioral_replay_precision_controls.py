from __future__ import annotations

from pathlib import Path

from .gemini_behavioral_replay_lane_scoring import has_execution_lane_separation
from .gemini_behavioral_replay_scoring import score_forbidden_markers, score_marker_presence

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
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_marker_semantics.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_precision_controls.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_capture_controls.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_capture_paths.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_capture_adversarial.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_assertion_polarity.py"),
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_semantic_assertions.py"),
    Path("project_sources/agent_runtime/tools/usb_reporting_transfer_semantics.py"),
    Path("project_sources/agent_runtime/tests/usb_reporting_transfer_semantics_selftest.py"),
    Path("project_sources/agent_runtime/tools/usb_reporting_evidence_semantics.py"),
    Path("project_sources/agent_runtime/tools/usb_reporting_clarification_semantics.py"),
    Path("project_sources/agent_runtime/tests/usb_reporting_evidence_semantics_selftest.py"),
    Path("project_sources/agent_runtime/tests/usb_reporting_clarification_semantics_selftest.py"),
]

# Recorded AGENTS.md connector-size exemptions. Each is capped near its current
# size so growth is still detected; split the file rather than raising a cap.
SCORER_MODULE_SIZE_EXEMPTIONS = {
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_live_regressions.py"): 47000,
    Path("project_sources/agent_runtime/tools/score_usb_reporting_behavior.py"): 20000,
    Path("project_sources/agent_runtime/tests/score_usb_reporting_behavior_selftest.py"): 16500,
}


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


def run_negated_rejection_polarity_selftest() -> None:
    marker = "high confidence malicious"
    for response in (
        "I do not reject the conclusion: this is high confidence malicious.",
        "We cannot deny that this is high confidence malicious.",
        "There is no doubt this is high confidence malicious.",
        "I don't dispute it: this is high confidence malicious.",
        "No lateral movement was observed: this is high confidence malicious.",
        "No lateral movement was observed - this is high confidence malicious.",
    ):
        if score_forbidden_markers(response, [marker])["hits"] != [marker]:
            raise SystemExit(f"Affirmed forbidden marker was suppressed: {response}")
    for response in (
        "We do not reject benign use, and we cannot claim this is high confidence malicious.",
        "What is not proven: high confidence malicious.",
        "I do not dispute the driver finding, but we cannot label this high confidence malicious.",
    ):
        if score_forbidden_markers(response, [marker])["hits"]:
            raise SystemExit(f"Rejected forbidden marker was scored as asserted: {response}")


def run_elastic_command_lane_separation_selftest() -> None:
    """Concrete Elastic command names count as response-action syntax (live Terra run 36308610507)."""
    context = (
        "Use the Elastic endpoint response console for execute --command. "
        "Local workstation PowerShell runs the collector for testing. "
    )
    for sentence, expected in (
        ("Do not use `upload --file` or `execute --command` in local PowerShell.", True),
        ("Never paste get-file --path into local workstation PowerShell.", True),
        ("Do not forget to use execute --command in local PowerShell.", False),
        ("Never fail to run execute --command in local workstation PowerShell.", False),
        ("Use execute --command with local PowerShell interchangeably.", False),
    ):
        if has_execution_lane_separation(context + sentence) is not expected:
            raise SystemExit(f"Elastic command lane separation expected {expected}: {sentence}")
