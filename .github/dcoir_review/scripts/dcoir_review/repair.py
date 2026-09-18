"""Canonical repair-policy helpers for DCOIR Review.

This module owns stable repair-stage policy that should not depend on numbered
runtime patch chronology. Historical patch modules may delegate here during the
#550 migration, but new repair-routing behavior belongs here rather than in a
new versioned overlay.
"""

from __future__ import annotations

import copy
from typing import Any


PRIMARY_CRITIC_MODEL = "openai/gpt-5.6-terra"
FALLBACK_CRITIC_MODEL = "~anthropic/claude-sonnet-latest"
OPENAI_CROSS_FAMILY_CRITIC_MODEL = "openai/gpt-5.6-sol-pro"
ANTHROPIC_CROSS_FAMILY_CRITIC_MODEL = "anthropic/claude-opus-5"
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


def build_repair_critic_config(config: Any, author_model: str = "") -> Any:
    """Return the canonical critic config while preserving established routing."""
    critic_config = copy.copy(config)
    served_author = str(author_model or "").strip().lower()
    if served_author:
        # v36/v56 historically use one opposite-family critic. Keep that live
        # behavior intact while moving ownership out of numbered patch modules.
        critic_model = (
            ANTHROPIC_CROSS_FAMILY_CRITIC_MODEL
            if served_author.startswith("openai/")
            else OPENAI_CROSS_FAMILY_CRITIC_MODEL
        )
        if hasattr(critic_config, "model"):
            critic_config.model = critic_model
        if hasattr(critic_config, "model_stack"):
            critic_config.model_stack = [critic_model]
        if hasattr(critic_config, "fallback_models"):
            critic_config.fallback_models = []
        if hasattr(critic_config, "openrouter_route"):
            critic_config.openrouter_route = ""
        if hasattr(critic_config, "openrouter_service_tier"):
            critic_config.openrouter_service_tier = ""
        return critic_config

    # The older no-author repair-support contract retains its governed direct
    # Terra/Sonnet stack. Consolidation must not silently change either policy.
    critic_config.model = PRIMARY_CRITIC_MODEL
    critic_config.model_stack = [PRIMARY_CRITIC_MODEL, FALLBACK_CRITIC_MODEL]
    critic_config.fallback_models = []
    critic_config.openrouter_route = ""
    critic_config.openrouter_service_tier = ""
    base_prefix = str(
        getattr(config, "openrouter_session_id_prefix", "") or "dcoir-review"
    ).strip()
    critic_config.openrouter_session_id_prefix = f"{base_prefix}-{CRITIC_SESSION_SUFFIX}"
    return critic_config
