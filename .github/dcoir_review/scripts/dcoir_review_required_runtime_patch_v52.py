"""DCOIR Review v52 bounded structured-result recovery execution policy.

v52 reduces avoidable broad semantic replay while preserving Architecture B's
quality, verifier, risk-sentinel, exact-head, and operator-control contracts.
"""

from __future__ import annotations

from typing import Any

import dcoir_review_required_runtime_patch_v52_disposition as disposition
import dcoir_review_required_runtime_patch_v52_provider as provider

VERSION = "v52"
APPLIED_MARKER = "_dcoir_review_v52_applied"


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    provider.patch_provider(module)
    disposition.patch_quality_retry_reason(module)
    disposition.patch_hybrid(module)
    setattr(module, APPLIED_MARKER, True)
