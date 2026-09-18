"""Dependency-leaf contracts for DCOIR finding verification."""

from __future__ import annotations

from typing import Any


VERIFIER_MAX_MODEL_FINDINGS = 6
VERIFIER_CANDIDATE_HARD_CAP = 12
VERIFIER_MIN_SUPPORT_CONFIDENCE = 0.80
VERIFIER_MARKER = "_dcoir_verifier_v21"
BLANK_LINE_NOTATION = "[DCOIR anchor is an intentionally blank changed line]"


def verifier_candidate_limit(config: Any) -> int:
    """Return the stable bounded verifier candidate ceiling."""
    try:
        configured_limit = int(
            getattr(
                config,
                "dcoir_v32_verifier_repair_limit",
                getattr(config, "fix_synthesis_max_findings", VERIFIER_MAX_MODEL_FINDINGS),
            )
        )
    except (TypeError, ValueError):
        configured_limit = VERIFIER_MAX_MODEL_FINDINGS
    try:
        inline_limit = int(getattr(config, "max_inline_comments", configured_limit))
    except (TypeError, ValueError):
        inline_limit = configured_limit
    return max(1, min(configured_limit, inline_limit, VERIFIER_CANDIDATE_HARD_CAP))
