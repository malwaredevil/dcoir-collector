"""Canonical composition owner for one DCOIR per-file review execution.

Semantic-result reuse and stage-local routing remain separate responsibilities, but
neither replaces ``review_single_file_context`` at runtime. This module composes
those behaviors once around the Pareto base callable and installs one final owner.
"""

from __future__ import annotations

from typing import Any

from dcoir_review import per_file_routing
from dcoir_review import semantic_result_reuse


APPLIED_MARKER = "_dcoir_per_file_review_applied"
STAGE_ORDER = ("stage-local-routing", "semantic-result-reuse", "base-review")


def apply_pareto_context_module(module: Any) -> None:
    """Install payload routing support and one explicit per-file review pipeline."""

    if getattr(module, APPLIED_MARKER, False):
        return

    base_review = getattr(module, "review_single_file_context", None)
    if not callable(base_review):
        raise RuntimeError("DCOIR per-file review could not locate the base per-file review function")

    per_file_routing.install_payload_builder(module)

    composed = semantic_result_reuse.build_per_file_semantic_result_reuse_stage(
        module, base_review
    )
    composed = per_file_routing.build_per_file_routing_stage(module, composed)

    def review_single_file_context(
        index, context, pr, diff, schema, config, risk_sentinels, review_mode
    ):
        return composed(
            index, context, pr, diff, schema, config, risk_sentinels, review_mode
        )

    module.review_single_file_context = review_single_file_context
    module.DCOIR_PER_FILE_REVIEW_STAGE_ORDER = STAGE_ORDER
    setattr(module, APPLIED_MARKER, True)


__all__ = ["APPLIED_MARKER", "STAGE_ORDER", "apply_pareto_context_module"]
