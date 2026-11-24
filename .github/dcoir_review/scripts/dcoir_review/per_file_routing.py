"""Stable DCOIR Review stage-local first-pass routing projection.

The #485 calibration showed that routine per-file first-pass review can use
Claude Sonnet 5.5 at high reasoning with a 32,768-token output cap and price-sorted
provider selection while the mature premium challenger, adjudicator, verifier,
and escalation stages remain on their existing Opus/Sol contracts.

This owner keeps that distinction explicit. New per-file configuration is projected
onto a shallow copy only for ``review_single_file_context``. The shared global
configuration is left unchanged for every later semantic stage. The projected
payload enables Response Healing explicitly and preserves strict structured
output and ``require_parameters=true``. Sampling-temperature and reasoning
request shape for every stage, including omission of generic temperature for
Claude 5/5.5 adaptive reasoning, is owned by the canonical reasoning payload policy
applied first in ``build_openrouter_payload``. Generic hardened-provider controls
capture request evidence and enforce stop/object response contracts without
bypassing the mature request-wrapper chain.

The overlay adds no publication, branch-write, commit, workflow-dispatch, or
paid-evaluation capability. Existing operator gates continue to own live review
invocation.
"""

from __future__ import annotations

import copy
from typing import Any

from dcoir_review import reasoning_policy
from dcoir_review import review_scope_guard as scope_guard


RESPONSE_HEALING_PLUGIN_ID = "response-healing"
PER_FILE_PROJECTION_ATTR = "dcoir_v47_per_file_projection"


def _optional_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


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
        setattr(projected, PER_FILE_PROJECTION_ATTR, True)
    if max_tokens is not None:
        projected.openrouter_require_stop_finish_reason = True
    return projected


def install_payload_builder(module: Any) -> None:
    hardened = module.hardened
    base_builder = getattr(hardened, "build_openrouter_payload", None)
    if not callable(base_builder):
        raise RuntimeError("DCOIR per-file routing could not locate hardened build_openrouter_payload")

    def build_openrouter_payload(prompt, schema, config, ignored_providers, model):
        payload = base_builder(prompt, schema, config, ignored_providers, model)
        payload = reasoning_policy.apply_reasoning_payload_policy(payload, config, model)

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


def _stage_local_fallback_allowed(module: Any, projected: Any, config: Any, exc: Exception) -> bool:
    """Allow the shared-route fallback only for non-transient stage-local failures."""

    if not bool(getattr(projected, PER_FILE_PROJECTION_ATTR, False)):
        return False  # No stage-local route was applied; nothing to fall back from.
    if isinstance(exc, (TimeoutError, scope_guard.ReviewSupersededError, scope_guard.ReviewHeadVerificationError)):
        return False  # Run-level aborts must end the review.
    saturation = getattr(module, "_is_transient_inflight_credit_saturation_error", None)
    if callable(saturation) and saturation(exc):
        return False  # Owned by the bounded credit-saturation recovery.
    return bool(getattr(config, "per_file_shared_route_fallback", True))


def _write_fallback_record(module: Any, config: Any, index: int, context: Any, exc: Exception) -> None:
    path = str(context.get("path", "") or "") if isinstance(context, dict) else ""
    artifact_id = module.safe_artifact_name(path, f"file-{index:02d}")
    module.hardened.write_debug_json_artifact_safely(
        config,
        f"metadata/per-file/{index:02d}-{artifact_id}-shared-route-fallback.json",
        {
            "path": path,
            "stage_local_failure": module.hardened.sanitize_github_output(
                f"{exc.__class__.__name__}: {exc}"[:500], config
            ),
            "fallback_model_stack": list(getattr(config, "model_stack", []) or []),
        },
    )


def build_per_file_routing_stage(module: Any, next_review: Any) -> Any:
    """Compose stage-local routing and request telemetry around a per-file callable."""

    original = next_review
    if not callable(original):
        raise RuntimeError("DCOIR per-file routing requires a callable per-file review stage")

    def per_file_routing_stage(
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
        except Exception as exc:
            # Preserve provider/finish/usage/cost evidence for capped failures
            # before deciding whether the stage-local route may fall back.
            _write_request_telemetry(module, projected, index, context)
            if not _stage_local_fallback_allowed(module, projected, config, exc):
                raise
            # One bounded fallback on the shared premium review route for a
            # non-transient stage-local failure (for example a completion that
            # hit the stage-local output cap). A second failure still reaches
            # the fail-closed per-file coverage gate.
            _write_fallback_record(module, config, index, context, exc)
            return original(
                index,
                context,
                pr,
                diff,
                schema,
                config,
                risk_sentinels,
                review_mode,
            )

        telemetry = _write_request_telemetry(module, projected, index, context)
        if isinstance(result, dict) and isinstance(telemetry, dict):
            result["request_telemetry"] = telemetry
        return result

    return per_file_routing_stage


__all__ = [
    "PER_FILE_PROJECTION_ATTR",
    "build_per_file_routing_stage",
    "install_payload_builder",
    "project_per_file_review_config",
]
