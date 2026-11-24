"""Trusted one-shot source-candidate receipt across model-result replacement stages.

The reviewer creates one GitHub client per run. Review stages may shallow-copy
model configuration and replace JSON result dictionaries, so neither is a
trustworthy place to carry source-backed candidates between those stages.
"""
from __future__ import annotations

import copy
import re
from typing import Any

_RECEIPT = "_dcoir_trusted_source_inventory_candidate_receipt"
_RESULT_KEY = "_dcoir_source_inventory_candidates"
_SHA = re.compile(r"^[0-9a-f]{40}$")
_STATE = "source-backed-pending-independent-verification"
_MAX = 6


def begin(review_client: Any) -> None:
    """Prevent cross-review receipt reuse on the live GitHub client."""
    setattr(review_client, _RECEIPT, None)


def capture(review_client: Any, reviewed_head: str, candidates: list[dict]) -> None:
    """Retain only locally detected source-backed candidates at an exact SHA."""
    if not isinstance(reviewed_head, str) or not _SHA.fullmatch(reviewed_head):
        return
    if not isinstance(candidates, list) or not 0 < len(candidates) <= _MAX:
        return
    if any(
        not isinstance(c, dict)
        or c.get("_dcoir_candidate_state") != _STATE
        or not isinstance(c.get("_dcoir_evidence"), dict)
        or c["_dcoir_evidence"].get("reviewed_head") != reviewed_head
        for c in candidates
    ):
        return
    setattr(review_client, _RECEIPT, (reviewed_head, tuple(copy.deepcopy(candidates))))


def restore(review_client: Any, reviewed_head: str, result: dict[str, Any]) -> int:
    """Discard provider-side candidates and consume the trusted receipt once."""
    result.pop(_RESULT_KEY, None)
    receipt = getattr(review_client, _RECEIPT, None)
    setattr(review_client, _RECEIPT, None)
    if not (isinstance(receipt, tuple) and len(receipt) == 2
            and receipt[0] == reviewed_head
            and isinstance(receipt[1], tuple)
            and 0 < len(receipt[1]) <= _MAX):
        return 0
    candidates = list(copy.deepcopy(receipt[1]))
    if any(
        not isinstance(c, dict)
        or c.get("_dcoir_candidate_state") != _STATE
        or not isinstance(c.get("_dcoir_evidence"), dict)
        or c["_dcoir_evidence"].get("reviewed_head") != reviewed_head
        for c in candidates
    ):
        return 0
    result[_RESULT_KEY] = candidates
    return len(candidates)


__all__ = ["begin", "capture", "restore"]
