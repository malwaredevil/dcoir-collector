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
CRITIC_SESSION_SUFFIX = "repair-critic"


def build_repair_critic_config(config: Any, author_model: str = "") -> Any:
    """Return the canonical independent structured-output critic config.

    The governed direct critic stack is Terra/Sonnet. When the repair author was
    served by an OpenAI model, reverse that stack so the first critic attempt is
    from the other model family while retaining the same canonical two-model
    fallback contract.
    """
    critic_config = copy.copy(config)
    served_author = str(author_model or "").strip().lower()
    if served_author.startswith("openai/"):
        primary_model = FALLBACK_CRITIC_MODEL
        fallback_model = PRIMARY_CRITIC_MODEL
    else:
        primary_model = PRIMARY_CRITIC_MODEL
        fallback_model = FALLBACK_CRITIC_MODEL

    critic_config.model = primary_model
    critic_config.model_stack = [primary_model, fallback_model]

    # Keep fallback deterministic at the explicit model-stack layer. Native
    # fallback_models would make it harder to attribute which critic served.
    critic_config.fallback_models = []

    # Direct critic models do not need Auto/Pareto router controls.
    critic_config.openrouter_route = ""
    critic_config.openrouter_service_tier = ""

    base_prefix = str(
        getattr(config, "openrouter_session_id_prefix", "") or "dcoir-review"
    ).strip()
    critic_config.openrouter_session_id_prefix = (
        f"{base_prefix}-{CRITIC_SESSION_SUFFIX}"
    )
    return critic_config
