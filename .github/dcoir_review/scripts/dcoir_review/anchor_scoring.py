"""Canonical semantic anchor-candidate scoring for DCOIR Review."""

from __future__ import annotations

from typing import Any

import dcoir_review_required_runtime_patch_v3 as v3


APPLIED_MARKER = "_dcoir_review_anchor_scoring_applied"
ORIGINAL_ATTR = "_dcoir_review_anchor_scoring_original_anchor_candidate_score"


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    original = getattr(module, ORIGINAL_ATTR, None)
    if original is None:
        original = getattr(module, "anchor_candidate_score", None)
        if callable(original):
            setattr(module, ORIGINAL_ATTR, original)
    if not callable(original):
        return

    def anchor_candidate_score(
        finding: dict[str, Any],
        candidate: Any,
        original_line: int,
        terms: list[str],
        risk_sentinels: list[Any],
    ) -> int:
        score = int(original(finding, candidate, original_line, terms, risk_sentinels))
        finding_kind = v3._semantic_kind(finding)
        candidate_kind = v3._line_kind(
            str(getattr(candidate, "path", "") or ""),
            str(getattr(candidate, "text", "") or ""),
        )
        if finding_kind and candidate_kind:
            if finding_kind == candidate_kind:
                score += 360
            elif finding_kind.startswith("yaml_") and candidate_kind.startswith("yaml_"):
                score -= 220
            elif finding_kind.startswith("ps_") and candidate_kind.startswith("ps_"):
                score -= 160
        return score

    module.anchor_candidate_score = anchor_candidate_score
    setattr(module, APPLIED_MARKER, True)


__all__ = ["APPLIED_MARKER", "ORIGINAL_ATTR", "apply_pareto_context_module"]
