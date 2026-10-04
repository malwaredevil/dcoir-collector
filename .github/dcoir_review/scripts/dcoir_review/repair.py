"""Canonical repair-policy helpers for DCOIR Review.

This module owns stable repair-stage policy that should not depend on numbered
runtime patch chronology. Historical patch modules may delegate here during the
#550 migration, but new repair-routing behavior belongs here rather than in a
new versioned overlay.
"""

from __future__ import annotations

import copy
from typing import Any


PRIMARY_REPAIR_AUTHOR_MODEL = "openai/gpt-5.6-terra"
FALLBACK_REPAIR_AUTHOR_MODEL = "anthropic/claude-sonnet-5.5"
PRIMARY_CRITIC_MODEL = "openai/gpt-5.6-terra"
FALLBACK_CRITIC_MODEL = "anthropic/claude-sonnet-5.5"
OPENAI_CROSS_FAMILY_CRITIC_MODEL = "openai/gpt-5.6-sol-pro"
OPENAI_CROSS_FAMILY_CRITIC_FALLBACK_MODEL = PRIMARY_CRITIC_MODEL
ANTHROPIC_CROSS_FAMILY_CRITIC_MODEL = "anthropic/claude-opus-5.5"
ANTHROPIC_CROSS_FAMILY_CRITIC_FALLBACK_MODEL = FALLBACK_CRITIC_MODEL
GOOGLE_CROSS_FAMILY_CRITIC_FALLBACK_MODEL = "google/gemini-3.1-pro-preview"
REPAIR_REASONING_EFFORT_BY_MODEL = {
    PRIMARY_REPAIR_AUTHOR_MODEL: "xhigh",
    FALLBACK_REPAIR_AUTHOR_MODEL: "high",
    PRIMARY_CRITIC_MODEL: "xhigh",
    ANTHROPIC_CROSS_FAMILY_CRITIC_MODEL: "xhigh",
    ANTHROPIC_CROSS_FAMILY_CRITIC_FALLBACK_MODEL: "high",
}
AUTHOR_SESSION_SUFFIX = "repair-author"
CRITIC_SESSION_SUFFIX = "repair-critic"
REPAIR_CANDIDATE_HARD_CAP = 12


def _positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(0, parsed)


def repair_synthesis_budget(config: Any) -> int:
    """Return how many verified findings may enter repair synthesis."""
    if not bool(getattr(config, "fix_synthesis_enabled", True)):
        return 0
    inline_limit = _positive_int(
        getattr(config, "max_inline_comments", REPAIR_CANDIDATE_HARD_CAP),
        REPAIR_CANDIDATE_HARD_CAP,
    )
    configured = _positive_int(getattr(config, "fix_synthesis_max_findings", 0), 0)
    return min(configured, inline_limit)


def _apply_repair_request_policy(config: Any, models: list[str], session_suffix: str) -> Any:
    projected = copy.copy(config)
    projected.model = models[0]
    projected.model_stack = list(models)
    projected.fallback_models = []
    projected.openrouter_route = ""
    projected.openrouter_service_tier = ""
    projected.dcoir_reasoning_effort_by_model = {
        model: REPAIR_REASONING_EFFORT_BY_MODEL[model]
        for model in models
        if model in REPAIR_REASONING_EFFORT_BY_MODEL
    }
    base_prefix = str(
        getattr(config, "openrouter_session_id_prefix", "") or "dcoir-review"
    ).strip()
    projected.openrouter_session_id_prefix = f"{base_prefix}-{session_suffix}"
    return projected


def build_repair_author_config(config: Any) -> Any:
    """Return the governed repair-author stack independently of detector routing."""
    return _apply_repair_request_policy(
        config,
        [PRIMARY_REPAIR_AUTHOR_MODEL, FALLBACK_REPAIR_AUTHOR_MODEL],
        AUTHOR_SESSION_SUFFIX,
    )


def build_repair_critic_config(config: Any, author_model: str = "") -> Any:
    """Return the canonical critic config while preserving cross-family routing."""
    served_author = str(author_model or "").strip().lower()
    if served_author.startswith("openai/"):
        critic_models = [
            ANTHROPIC_CROSS_FAMILY_CRITIC_MODEL,
            ANTHROPIC_CROSS_FAMILY_CRITIC_FALLBACK_MODEL,
            GOOGLE_CROSS_FAMILY_CRITIC_FALLBACK_MODEL,
        ]
    elif served_author:
        critic_models = [
            OPENAI_CROSS_FAMILY_CRITIC_MODEL,
            OPENAI_CROSS_FAMILY_CRITIC_FALLBACK_MODEL,
        ]
    else:
        critic_models = [PRIMARY_CRITIC_MODEL, FALLBACK_CRITIC_MODEL]

    return _apply_repair_request_policy(
        config,
        critic_models,
        CRITIC_SESSION_SUFFIX,
    )
