"""DCOIR Review v47 stage-local first-pass routing projection for issue #457.

The #485 calibration showed that routine per-file first-pass review can use
Claude Sonnet 5 at high reasoning with a 32,768-token output cap and price-sorted
provider selection while the mature premium challenger, adjudicator, verifier,
and escalation stages remain on their existing Opus/Sol contracts.

v47 keeps that distinction explicit. New per-file configuration is projected
onto a shallow copy only for ``review_single_file_context``. The shared global
configuration is left unchanged for every later semantic stage. The projected
payload enables Response Healing explicitly, preserves strict structured output
and ``require_parameters=true``, and omits generic sampling temperature for
Sonnet 5. Generic hardened-provider controls capture request evidence and enforce
stop/object response contracts without bypassing the mature request-wrapper
chain.

The overlay adds no publication, branch-write, commit, workflow-dispatch, or
paid-evaluation capability. Existing operator gates continue to own live review
invocation.
"""

from __future__ import annotations

import copy
from typing import Any


VERSION = "v47"
APPLIED_MARKER = "_dcoir_review_v47_applied"
RESPONSE_HEALING_PLUGIN_ID = "response-healing"


def _optional_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _optional_positive_int(value: Any, key: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Config key {key!r} must be a positive integer or empty, got {value!r}") from exc
    if parsed <= 0:
        raise ValueError(f"Config key {key!r} must be a positive integer or empty, got {value!r}")
    return parsed


def _is_claude_sonnet_5(model: Any) -> bool:
    value = str(model or "").strip().lower().split(":", 1)[0]
    return value == "anthropic/claude-sonnet-5" or value.startswith("anthropic/claude-sonnet-5-")


def project_per_file_review_config(config: Any) -> Any:
    """Return a stage-local request config without mutating the shared config."""

    projected = copy.copy(config)
    models = _optional_string_list(getattr(config, "per_file_review_model_stack", []))
    effort = getattr(config, "per_file_review_reasoning_effort", None)
    max_tokens = getattr(config, "per_file_review_max_tokens", None)
    provider_sort = str(getattr(config, "per_file_review_provider_sort", "") or "").strip()

    if models:
        projected.model_stack = list(models)
        projected.model = models[0]
    if effort is not None:
        projected.review_reasoning_effort = str(effort).strip()
    if max_tokens is not None:
        projected.openrouter_request_max_tokens = int(max_tokens)
    if provider_sort:
        projected.openrouter_provider_sort = provider_sort

    stage_override_active = bool(models or effort is not None or max_tokens is not None or provider_sort)
    if stage_override_active:
        projected.openrouter_response_healing = True
        projected.openrouter_capture_request_telemetry = True
        projected.openrouter_require_object_response = True
        projected.dcoir_v47_per_file_projection = True
    if max_tokens is not None:
        projected.openrouter_require_stop_finish_reason = True
    return projected


def _patch_config_loader(module: Any) -> None:
    storage = "_dcoir_review_v47_original_load_pareto_context_config"
    original = getattr(module, storage, None)
    if original is None:
        original = getattr(module, "load_pareto_context_config", None)
        if callable(original):
            setattr(module, storage, original)
    if not callable(original):
        raise RuntimeError("DCOIR v47 could not locate load_pareto_context_config")

    def load_pareto_context_config(path: str):
        config = original(path)
        data = module.hardened.parse_yaml_like_data(path)
        config.per_file_review_model_stack = _optional_string_list(data.get("per_file_review_model_stack"))
        effort = str(data.get("per_file_review_reasoning_effort", "") or "").strip()
        config.per_file_review_reasoning_effort = effort or None
        config.per_file_review_max_tokens = _optional_positive_int(
            data.get("per_file_review_max_tokens"), "per_file_review_max_tokens"
        )
        config.per_file_review_provider_sort = str(data.get("per_file_review_provider_sort", "") or "").strip()
        return config

    module.load_pareto_context_config = load_pareto_context_config


def _patch_payload_builder(module: Any) -> None:
    hardened = module.hardened
    storage = "_dcoir_review_v47_original_build_openrouter_payload"
    original = getattr(hardened, storage, None)
    if original is None:
        original = getattr(hardened, "build_openrouter_payload", None)
        if callable(original):
            setattr(hardened, storage, original)
    if not callable(original):
        raise RuntimeError("DCOIR v47 could not locate hardened build_openrouter_payload")

    def build_openrouter_payload(prompt, schema, config, ignored_providers, model):
        payload = original(prompt, schema, config, ignored_providers, model)

        request_max_tokens = getattr(config, "openrouter_request_max_tokens", None)
        if request_max_tokens is not None:
            payload["max_tokens"] = int(request_max_tokens)

        provider_sort = str(getattr(config, "openrouter_provider_sort", "") or "").strip()
        if provider_sort:
            provider = payload.setdefault("provider", {})
            provider["sort"] = provider_sort

        if bool(getattr(config, "openrouter_response_healing", False)):
            plugins = list(payload.get("plugins") or [])
            if not any(
                isinstance(plugin, dict) and str(plugin.get("id", "")) == RESPONSE_HEALING_PLUGIN_ID
                for plugin in plugins
            ):
                plugins.append({"id": RESPONSE_HEALING_PLUGIN_ID, "enabled": True})
            payload["plugins"] = plugins

        # Only the calibrated per-file Sonnet contract omits the generic
        # sampling temperature. Installing v47 must not change an unrelated
        # global/premium Sonnet request when the stage-local projection is absent.
        projected_per_file = bool(getattr(config, "dcoir_v47_per_file_projection", False))
        if projected_per_file and _is_claude_sonnet_5(model):
            payload.pop("temperature", None)

        return payload

    hardened.build_openrouter_payload = build_openrouter_payload
    if hasattr(module, "build_openrouter_payload"):
        module.build_openrouter_payload = build_openrouter_payload


def _write_request_telemetry(module: Any, projected: Any, index: int, context: Any) -> dict[str, Any] | None:
    telemetry = getattr(projected, "_openrouter_last_request_telemetry", None)
    if not isinstance(telemetry, dict):
        return None
    path = str(context.get("path", "") or "") if isinstance(context, dict) else ""
    artifact_id = module.safe_artifact_name(path, f"file-{index:02d}")
    module.hardened.write_debug_json_artifact_safely(
        projected,
        f"metadata/per-file/{index:02d}-{artifact_id}-request-telemetry.json",
        {"path": path, **telemetry},
    )
    return dict(telemetry)


def _patch_per_file_review(module: Any) -> None:
    storage = "_dcoir_review_v47_original_review_single_file_context"
    original = getattr(module, storage, None)
    if original is None:
        original = getattr(module, "review_single_file_context", None)
        if callable(original):
            setattr(module, storage, original)
    if not callable(original):
        raise RuntimeError("DCOIR v47 could not locate review_single_file_context")

    def review_single_file_context(
        index,
        context,
        pr,
        diff,
        schema,
        config,
        risk_sentinels,
        review_mode,
    ):
        projected = project_per_file_review_config(config)
        try:
            result = original(
                index,
                context,
                pr,
                diff,
                schema,
                projected,
                risk_sentinels,
                review_mode,
            )
        except Exception:
            # Preserve provider/finish/usage/cost evidence for capped failures
            # before allowing the existing fail-closed coverage path to handle
            # the exception.
            _write_request_telemetry(module, projected, index, context)
            raise

        telemetry = _write_request_telemetry(module, projected, index, context)
        if isinstance(result, dict) and isinstance(telemetry, dict):
            result["request_telemetry"] = telemetry
        return result

    module.review_single_file_context = review_single_file_context


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    _patch_config_loader(module)
    _patch_payload_builder(module)
    _patch_per_file_review(module)
    setattr(module, APPLIED_MARKER, True)
