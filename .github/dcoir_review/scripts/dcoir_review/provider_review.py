"""Canonical OpenRouter review-call composition for DCOIR Review."""

from __future__ import annotations

from typing import Any

from dcoir_review import final_adjudication_policy
from dcoir_review import review_telemetry
from dcoir_review import structured_result_provider

APPLIED_MARKER = "_dcoir_review_provider_review_applied"
OWNER_MARKER = "_dcoir_review_provider_review_owner"


def _finish_telemetry_fail_soft(state: Any, outcome: str) -> None:
    try:
        review_telemetry.finish_review_call(state, outcome)
    except Exception:
        try:
            config = getattr(state, "root_config", None)
            review_telemetry.note_telemetry_error(config)
        except Exception:
            pass


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return

    hardened = module.hardened
    underlying = getattr(hardened, "openrouter_review", None)
    if not callable(underlying):
        raise RuntimeError(
            "DCOIR provider review could not locate hardened openrouter_review"
        )

    def openrouter_review(prompt, schema, config, reporter=None):
        projected_prompt, projected_config = final_adjudication_policy.project_review_call(
            module, prompt, config
        )
        state = review_telemetry.prepare_review_call(
            projected_prompt, schema, projected_config
        )
        active_config = state.staged_config if state is not None else projected_config
        structured_result_provider.reset_review_recovery(active_config)
        try:
            result = underlying(
                projected_prompt, schema, active_config, reporter
            )
        except Exception:
            _finish_telemetry_fail_soft(state, "failed")
            raise

        structured_result_provider.report_review_recovery(active_config, reporter)
        _finish_telemetry_fail_soft(state, "success")
        return result

    openrouter_review.__module__ = __name__
    setattr(openrouter_review, OWNER_MARKER, True)
    hardened.openrouter_review = openrouter_review
    setattr(module, APPLIED_MARKER, True)


__all__ = ["APPLIED_MARKER", "OWNER_MARKER", "apply_pareto_context_module"]
