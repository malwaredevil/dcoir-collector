"""Stable deterministic risk-sentinel semantics foundation for DCOIR Review.

This owner composes the final deterministic risk-sentinel classifier/detector,
required-selection baseline, selection metadata/overflow behavior, and legacy
progress evidence that were historically installed by runtime patch v16.
Stable selection, identity, verification, precision, rendering, and progress
owners then wrap this foundation explicitly. The historical v16 module remains
importable only as a helper-definition layer.
"""

from __future__ import annotations

from typing import Any

import dcoir_review.risk_sentinel_primitives as v16


APPLIED_MARKER = "_dcoir_review_risk_sentinel_semantics_applied"


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return

    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)

    v16._patch_core_semantics()
    module.rank_findings_for_required_budget = lambda findings, config: sorted(
        [v16.v5._normalize_comment_finding(item) for item in findings if isinstance(item, dict)],
        key=v16._candidate_priority,
    )[: max(0, int(getattr(config, "max_inline_comments", 12)))]

    if hardened is not None:
        hardened.add_risk_sentinel_fallback_findings = (
            lambda findings, risk_sentinels, config, unanchored_findings=None: v16._select_required_postable(
                hardened,
                findings,
                risk_sentinels,
                config,
                unanchored_findings,
            )
        )
        hardened.enforce_risk_sentinel_findings = (
            lambda findings, risk_sentinels, config, unanchored_findings=None: findings.__setitem__(
                slice(None),
                v16._select_required_postable(
                    hardened,
                    findings,
                    risk_sentinels,
                    config,
                    unanchored_findings,
                ),
            )
        )
        v16._patch_review_body_overflow(hardened)

    if base is not None:
        v16.v11._patch_progress_comment(base, hardened)

    setattr(module, APPLIED_MARKER, True)
