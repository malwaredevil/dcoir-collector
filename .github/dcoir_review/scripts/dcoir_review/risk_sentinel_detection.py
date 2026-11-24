"""Canonical one-shot composition for deterministic risk-sentinel detection.

The production detector is composed once from responsibility helpers instead of
wrapping ``detect_risk_sentinels`` repeatedly and retaining stored-original
callables. Historical compatibility installers remain test-only surfaces.
"""

from __future__ import annotations

from typing import Any

from dcoir_review import environment_token_detection
from dcoir_review import python_filesystem_detection
from dcoir_review import required_coverage_policy
from dcoir_review import risk_sentinel_primitives
from dcoir_review import truthy_literal_precision


APPLIED_MARKER = "_dcoir_review_risk_sentinel_detection_applied"


def _compose(module: Any, owner: Any, sentinel_owner: Any | None, *, truthy_filter: bool):
    hardened = getattr(module, "hardened", None)
    detector = getattr(owner, "detect_risk_sentinels", None)
    if not callable(detector):
        raise RuntimeError("DCOIR risk-sentinel detection could not locate baseline detector")
    detector = required_coverage_policy.build_detector(hardened, detector)
    detector = environment_token_detection.build_detector(hardened, detector)
    detector = python_filesystem_detection.build_detector(owner, sentinel_owner, detector)
    detector = risk_sentinel_primitives.build_detector(owner, sentinel_owner, detector)
    if truthy_filter:
        detector = truthy_literal_precision.build_detector(module, detector)
    return detector


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    hardened = getattr(module, "hardened", None)
    if hardened is None:
        raise RuntimeError("DCOIR risk-sentinel detection requires hardened helpers")

    # Core classifiers are initialized before the detector closures are composed.
    risk_sentinel_primitives._patch_core_semantics()
    truthy_literal_precision._patch_deterministic_line_kind()

    module.detect_risk_sentinels = _compose(
        module, module, hardened, truthy_filter=True
    )
    hardened.detect_risk_sentinels = _compose(
        module, hardened, module, truthy_filter=False
    )
    setattr(module, APPLIED_MARKER, True)


__all__ = ["APPLIED_MARKER", "apply_pareto_context_module"]
