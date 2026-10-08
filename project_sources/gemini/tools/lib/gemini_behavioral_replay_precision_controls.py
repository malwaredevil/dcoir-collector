from __future__ import annotations

from pathlib import Path

from .gemini_behavioral_replay_scoring import score_marker_presence

SCORER_MODULE_CHARACTER_CEILING = 15000
REPLAY_LIB_ROOT = Path("project_sources/gemini/tools/lib")
SCORER_MODULES = sorted({
    *REPLAY_LIB_ROOT.glob("gemini_behavioral_replay_*.py"),
    *REPLAY_LIB_ROOT.glob("openai_*replay*.py"),
    Path("project_sources/agent_runtime/tools/usb_reporting_markdown_fences.py"),
    Path("project_sources/agent_runtime/tools/usb_reporting_transfer_semantics.py"),
    Path("project_sources/agent_runtime/tests/usb_reporting_transfer_semantics_selftest.py"),
    Path("project_sources/agent_runtime/tools/usb_reporting_evidence_semantics.py"),
    Path("project_sources/agent_runtime/tools/usb_reporting_clarification_semantics.py"),
    Path("project_sources/agent_runtime/tests/usb_reporting_evidence_semantics_selftest.py"),
    Path("project_sources/agent_runtime/tests/usb_reporting_clarification_semantics_selftest.py"),
    Path("project_sources/agent_runtime/tests/usb_reporting_markdown_fences_selftest.py"),
})


# Recorded AGENTS.md connector-size exemptions. Each is capped near its current
# size so growth is still detected; split the file rather than raising a cap.
SCORER_MODULE_SIZE_EXEMPTIONS = {
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_live_regressions.py"): 47000,
    # Schema remains over the connector-safe target while #604 consolidates the scorer.
    # Keep the exemption close to the observed size so growth still fails closed.
    Path("project_sources/gemini/tools/lib/gemini_behavioral_replay_schema.py"): 18000,
    Path("project_sources/agent_runtime/tools/score_usb_reporting_behavior.py"): 20000,
    Path("project_sources/agent_runtime/tests/score_usb_reporting_behavior_selftest.py"): 16500,
}


GOVERNED_SOURCE_REJECTED = (
    "Never verify against the governed source.",
    "Do not validate against the governed source.",
    "Verification against the governed source, which is not needed.",
    "Verify against the governed source, which is not needed.",
)
GOVERNED_SOURCE_ACCEPTED = (
    "Verify against the governed source before claiming targeted mode.",
    "I cannot verify against the governed source, so the window semantics stay unconfirmed.",
    "I did not perform validation against the governed source.",
)


def run_governed_source_override_selftest() -> None:
    """The 'governed source' rule must honor rejection before and after the marker."""
    for text in GOVERNED_SOURCE_REJECTED:
        if score_marker_presence(text, ["governed source"])["matched"]:
            raise SystemExit(f"Rejected governed-source action counted as the marker: {text}")
    for text in GOVERNED_SOURCE_ACCEPTED:
        if score_marker_presence(text, ["governed source"])["matched"] != ["governed source"]:
            raise SystemExit(f"Governed-source marker was incorrectly suppressed: {text}")


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
