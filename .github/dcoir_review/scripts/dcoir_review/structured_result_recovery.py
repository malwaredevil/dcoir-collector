"""Stable bounded structured-result recovery execution policy for DCOIR Review.

This owner reduces avoidable broad semantic replay while preserving Architecture B's
quality, verifier, risk-sentinel, exact-head, and operator-control contracts.
"""

from __future__ import annotations

from typing import Any

from dcoir_review import structured_result_provider as provider

APPLIED_MARKER = "_dcoir_review_structured_result_recovery_applied"


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    provider.patch_provider(module)
    setattr(module, APPLIED_MARKER, True)
