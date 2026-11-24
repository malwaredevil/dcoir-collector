"""Deterministic regressions for response-scoped execution-lane separation scoring."""
from __future__ import annotations

from .gemini_behavioral_replay_lane_scoring import has_execution_lane_separation
from .gemini_behavioral_replay_lane_separation_cases_accepted import ACCEPTED_SEPARATION_CASES
from .gemini_behavioral_replay_lane_separation_cases_rejected import REJECTED_SEPARATION_CASES


def run_lane_separation_scoring_selftest() -> None:
    for expected, cases in ((True, ACCEPTED_SEPARATION_CASES), (False, REJECTED_SEPARATION_CASES)):
        for response, label in cases:
            actual = has_execution_lane_separation(response)
            if actual is not expected:
                raise SystemExit(
                    f"{label}: expected has_execution_lane_separation={expected}, got {actual}"
                )
