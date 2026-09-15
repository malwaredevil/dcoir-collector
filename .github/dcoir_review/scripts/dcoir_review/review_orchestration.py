"""Canonical composition owner for DCOIR Review's hybrid review lifecycle.

Participating responsibilities expose stage builders instead of replacing the same
runtime callable in sequence. This module composes those stages once, preserving the
characterized historical order without stored-original hybrid shims.
"""

from __future__ import annotations

from typing import Any, Callable

from dcoir_review import quality_gate
from dcoir_review import review_scope_guard_hooks
from dcoir_review import semantic_adjudication_confidence
from dcoir_review import semantic_result_reuse
from dcoir_review import semantic_review_ledger_hooks
from dcoir_review import structured_result_disposition
from dcoir_review import structured_result_recovery
import dcoir_review_required_runtime_patch_v32 as v32
import dcoir_review_required_runtime_patch_v35 as v35
import dcoir_review_required_runtime_patch_v44 as v44
import dcoir_review_required_runtime_patch_v46 as v46


APPLIED_MARKER = "_dcoir_review_orchestration_applied"
STAGE_ORDER = (
    "quality-gate",
    "adversarial-confirmation",
    "semantic-adjudication",
    "semantic-adjudication-confidence",
    "semantic-review-ledger",
    "semantic-result-reuse",
    "candidate-scoped-escalation",
    "canonical-semantic-context",
    "review-scope-terminal-translation",
    "structured-result-disposition",
)


def _stage_builders() -> tuple[tuple[str, Callable[[Any, Any], Any]], ...]:
    return (
        (STAGE_ORDER[0], quality_gate.build_quality_gate_stage),
        (STAGE_ORDER[1], v32.build_adversarial_confirmation_stage),
        (STAGE_ORDER[2], v35.build_semantic_adjudication_stage),
        (STAGE_ORDER[3], semantic_adjudication_confidence.build_semantic_adjudication_confidence_stage),
        (STAGE_ORDER[4], semantic_review_ledger_hooks.build_semantic_review_ledger_stage),
        (STAGE_ORDER[5], semantic_result_reuse.build_semantic_result_reuse_stage),
        (STAGE_ORDER[6], v44.build_candidate_scoped_escalation_stage),
        (STAGE_ORDER[7], v46.build_canonical_semantic_context_stage),
        (STAGE_ORDER[8], review_scope_guard_hooks.build_review_scope_terminal_translation_stage),
        (STAGE_ORDER[9], structured_result_disposition.build_structured_result_disposition_stage),
    )


def apply_pareto_context_module(module: Any) -> None:
    """Install non-hybrid structured recovery and one explicit hybrid pipeline."""

    if getattr(module, APPLIED_MARKER, False):
        return

    base_review = getattr(module, "openrouter_review_with_hybrid_first_pass", None)
    if not callable(base_review):
        raise RuntimeError("DCOIR review orchestration could not locate the base hybrid review function")

    # Structured-result provider/retry behavior historically applied at this point
    # in the production sequence. It remains a distinct responsibility helper, but
    # no longer installs another hybrid wrapper.
    structured_result_recovery.apply_pareto_context_module(module)

    composed = base_review
    for _stage_name, builder in _stage_builders():
        composed = builder(module, composed)
        if not callable(composed):
            raise RuntimeError(f"DCOIR review orchestration stage {_stage_name} did not return a callable")

    def openrouter_review_with_hybrid_first_pass(
        pr,
        files,
        diff,
        schema,
        config,
        reporter,
        risk_sentinels,
        line_index,
        deep_context_block,
        review_mode,
        context_summary,
        gh,
    ):
        return composed(
            pr,
            files,
            diff,
            schema,
            config,
            reporter,
            risk_sentinels,
            line_index,
            deep_context_block,
            review_mode,
            context_summary,
            gh,
        )

    module.openrouter_review_with_hybrid_first_pass = openrouter_review_with_hybrid_first_pass
    module.DCOIR_REVIEW_ORCHESTRATION_STAGE_ORDER = STAGE_ORDER
    setattr(module, APPLIED_MARKER, True)


__all__ = ["APPLIED_MARKER", "STAGE_ORDER", "apply_pareto_context_module"]
