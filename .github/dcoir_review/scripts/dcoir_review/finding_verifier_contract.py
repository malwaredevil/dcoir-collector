"""Dependency-leaf contracts for DCOIR finding verification."""

from __future__ import annotations

from typing import Any


VERIFIER_MAX_MODEL_FINDINGS = 6
VERIFIER_CANDIDATE_HARD_CAP = 12
VERIFIER_MIN_SUPPORT_CONFIDENCE = 0.80
VERIFIER_MARKER = "_dcoir_verifier_v21"
BLANK_LINE_NOTATION = "[DCOIR anchor is an intentionally blank changed line]"


def verifier_candidate_limit(config: Any) -> int:
    """Bound evidence verification independently of repair-synthesis cost."""

    try:
        inline_limit = int(
            getattr(config, "max_inline_comments", VERIFIER_CANDIDATE_HARD_CAP)
        )
    except (TypeError, ValueError):
        inline_limit = VERIFIER_CANDIDATE_HARD_CAP
    return max(1, min(inline_limit, VERIFIER_CANDIDATE_HARD_CAP))
