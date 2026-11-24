"""Canonical OpenRouter reasoning-payload policy for DCOIR Review.

This responsibility owns model-family reasoning compatibility independently of
historical runtime-patch chronology. It preserves the governed request shape
for GPT-5 reasoning SKUs and Claude 5/5.5 adaptive reasoning while leaving
provider selection and stage routing to their existing owners.
"""

from __future__ import annotations

from typing import Any

from dcoir_review import review_config


DEFAULT_REASONING_EFFORT = review_config.DEFAULT_REASONING_EFFORT


def _normalized_openai_model_id(model: Any) -> str:
    value = str(model or "").strip().lower()
    if not value.startswith("openai/"):
        return ""
    return value.split("/", 1)[1].split(":", 1)[0]


def model_owns_fixed_pro_reasoning(model: Any) -> bool:
    """Return True for OpenAI model SKUs that already encode Pro reasoning."""

    model_id = _normalized_openai_model_id(model)
    return bool(model_id) and (model_id.endswith("-pro") or "-pro-" in model_id)


def model_uses_openai_gpt5_reasoning(model: Any) -> bool:
    """Return True for the governed OpenAI GPT-5 reasoning family."""

    return _normalized_openai_model_id(model).startswith("gpt-5")


def model_uses_anthropic_adaptive_reasoning(model: Any) -> bool:
    """Return True for governed Claude 5/5.5 adaptive-reasoning requests."""

    model_id = str(model or "").strip().lower().split(":", 1)[0]
    return (
        model_id.startswith("anthropic/claude-opus-5")
        or model_id.startswith("anthropic/claude-sonnet-5")
    )


def reasoning_effort_for_model(config: Any, model: Any) -> str:
    model_id = str(model or "").strip().lower().split(":", 1)[0]
    overrides = getattr(config, "dcoir_reasoning_effort_by_model", None)
    if isinstance(overrides, dict):
        for configured_model, configured_effort in overrides.items():
            normalized = str(configured_model or "").strip().lower().split(":", 1)[0]
            if normalized == model_id:
                return str(configured_effort or "").strip()
    return str(
        getattr(config, "review_reasoning_effort", DEFAULT_REASONING_EFFORT) or ""
    ).strip()


def apply_reasoning_payload_policy(
    payload: dict[str, Any],
    config: Any,
    model: Any,
) -> dict[str, Any]:
    """Apply the governed reasoning compatibility contract to a payload."""

    effort = reasoning_effort_for_model(config, model)
    reasoning_active = bool(effort and effort.lower() != "none")

    if (
        model_uses_openai_gpt5_reasoning(model)
        and (model_owns_fixed_pro_reasoning(model) or reasoning_active)
    ) or (
        model_uses_anthropic_adaptive_reasoning(model) and reasoning_active
    ):
        payload.pop("temperature", None)

    if model_owns_fixed_pro_reasoning(model):
        # OpenRouter's OpenAI *-pro SKUs already encode reasoning.mode=pro.
        payload.pop("reasoning", None)
        return payload

    if reasoning_active:
        payload["reasoning"] = {
            "enabled": True,
            "effort": effort,
            "exclude": True,
        }
    return payload


__all__ = [
    "DEFAULT_REASONING_EFFORT",
    "apply_reasoning_payload_policy",
    "model_owns_fixed_pro_reasoning",
    "model_uses_anthropic_adaptive_reasoning",
    "model_uses_openai_gpt5_reasoning",
    "reasoning_effort_for_model",
]
