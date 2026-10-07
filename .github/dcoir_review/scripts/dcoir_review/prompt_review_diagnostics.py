"""Stable prompt-review accounting and diagnostic composition for DCOIR Review.

The legacy v9 helper modules still expose compatibility data structures used by
later historical helpers, but production ownership for prompt-review accounting,
debug readback, target-call evidence, and progress diagnostics lives here.
"""

from __future__ import annotations

from typing import Any

from dcoir_review.prompt_review_diagnostics_helpers import (
    _patch_progress_comment,
    _patch_prompt_review_call_accounting,
    _patch_prompt_review_readback,
    _patch_target_call_accounting,
)


APPLIED_MARKER = "_dcoir_review_prompt_review_diagnostics_applied"


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return

    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)

    _patch_prompt_review_call_accounting()
    if base is not None:
        _patch_progress_comment(base, hardened)
    if hardened is not None and base is not None:
        _patch_target_call_accounting(hardened)
        _patch_prompt_review_readback(hardened, base)

    setattr(module, APPLIED_MARKER, True)
