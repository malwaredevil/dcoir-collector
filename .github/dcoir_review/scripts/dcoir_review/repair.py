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


def build_repair_critic_config(config: Any) -> Any:
    """Return an independent structured-output config for the repair critic."""
    critic_config = copy.copy(config)
    critic_config.model = PRIMARY_CRITIC_MODEL
    critic_config.model_stack = [PRIMARY_CRITIC_MODEL, FALLBACK_CRITIC_MODEL]

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
