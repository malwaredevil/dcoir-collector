"""DCOIR Review v29 repair-critic routing compatibility overlay.

The verified repair pipeline deliberately uses a second AI call to critique an
exact one-line repair before exposing a GitHub-native suggestion. The previous
critic configuration forced OpenRouter Auto Router, which can select routes
that do not satisfy the reviewer's strict JSON-schema response parameters and
therefore fail with HTTP 404 before the critic can judge the repair.

v29 keeps the critic independent from the repair-author call but routes it
through direct models with structured-output support:

1. OpenAI GPT-5.6 Terra
2. Anthropic Claude Sonnet Latest fallback

The call uses a separate sticky-session namespace and clears Auto/Pareto router
fallback parameters. It does not weaken the verifier, critic confidence gate,
deterministic exact-line validation, or no-branch-write boundary.
"""

from __future__ import annotations

import copy
from typing import Any

import dcoir_review_required_runtime_patch_v25 as v25


PRIMARY_CRITIC_MODEL = "openai/gpt-5.6-terra"
FALLBACK_CRITIC_MODEL = "~anthropic/claude-sonnet-latest"
CRITIC_SESSION_SUFFIX = "repair-critic"


def structured_output_critic_config(config: Any) -> Any:
    """Return a separate direct-model config for the repair critic."""
    critic_config = copy.copy(config)
    critic_config.model = PRIMARY_CRITIC_MODEL
    critic_config.model_stack = [PRIMARY_CRITIC_MODEL, FALLBACK_CRITIC_MODEL]

    # Keep fallback deterministic at the explicit model-stack layer. Native
    # fallback_models would make it harder to attribute which critic served.
    critic_config.fallback_models = []

    # Direct critic models do not need Auto/Pareto router controls.
    critic_config.openrouter_route = ""
    critic_config.openrouter_service_tier = ""

    base_prefix = str(getattr(config, "openrouter_session_id_prefix", "") or "dcoir-review").strip()
    critic_config.openrouter_session_id_prefix = f"{base_prefix}-{CRITIC_SESSION_SUFFIX}"
    return critic_config


def apply_pareto_context_module(module: Any) -> None:
    del module
    # v28 calls this helper dynamically immediately before the critic request.
    # Replacing the helper preserves the v28 repair/validation logic while
    # removing the incompatible Auto Router constraint.
    v25._independent_config = structured_output_critic_config
