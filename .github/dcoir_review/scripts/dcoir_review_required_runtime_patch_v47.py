"""DCOIR Review v47 stage-local first-pass routing projection for issue #457.

The #485 calibration showed that routine per-file first-pass review can use
Claude Sonnet 5 at high reasoning with a 32,768-token output cap and price-sorted
provider selection while the mature premium challenger, adjudicator, verifier,
and escalation stages remain on their existing Opus/Sol contracts.

v47 keeps that distinction explicit.  New per-file configuration is projected
onto a shallow copy only for ``review_single_file_context``.  The shared global
configuration is left unchanged for every later semantic stage.  The projected
request also enables Response Healing explicitly, preserves strict structured
output and ``require_parameters=true``, omits the generic sampling temperature
for Sonnet 5, and fails closed when an output-capped completion does not finish
with ``stop``.

The overlay adds no publication, branch-write, commit, workflow-dispatch, or
paid-evaluation capability.  Existing operator gates continue to own live
review invocation.
"""

from __future__ import annotations

import copy
import json
import re
import urllib.request
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
        raw_effort = data.get("per_file_review_reasoning_effort")
        config.per_file_review_reasoning_effort = None if raw_effort in (None, "") else str(raw_effort).strip()
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

        # Sonnet 5 reasoning requests in the calibrated contract do not send the
        # generic sampling temperature.  With require_parameters=true, retaining
        # an unsupported sampling field can make otherwise healthy providers
        # ineligible before inference.
        if _is_claude_sonnet_5(model):
            payload.pop("temperature", None)

        return payload

    hardened.build_openrouter_payload = build_openrouter_payload
    if hasattr(module, "build_openrouter_payload"):
        module.build_openrouter_payload = build_openrouter_payload


def _response_provider(data: dict[str, Any]) -> str:
    provider = str(data.get("provider", "") or "").strip()
    if provider:
        return provider
    metadata = data.get("openrouter_metadata")
    if not isinstance(metadata, dict):
        return ""
    endpoints = metadata.get("endpoints")
    if not isinstance(endpoints, dict):
        return ""
    available = endpoints.get("available")
    if not isinstance(available, list):
        return ""
    selected = next(
        (item for item in available if isinstance(item, dict) and bool(item.get("selected"))),
        None,
    )
    if not isinstance(selected, dict):
        return ""
    return str(selected.get("provider", "") or selected.get("name", "") or "").strip()


def _patch_request_once(module: Any) -> None:
    hardened = module.hardened
    base = module.base
    storage = "_dcoir_review_v47_original_openrouter_request_once"
    original = getattr(hardened, storage, None)
    if original is None:
        original = getattr(hardened, "openrouter_request_once", None)
        if callable(original):
            setattr(hardened, storage, original)
    if not callable(original):
        raise RuntimeError("DCOIR v47 could not locate hardened openrouter_request_once")

    def openrouter_request_once(prompt, schema, config, ignored_providers, model):
        # Preserve the historical request implementation for all non-projected
        # stages.  This keeps v47 backward-compatible when the new per-file keys
        # are absent and confines stricter finish-reason handling to the capped
        # first-pass request contract.
        if not bool(getattr(config, "dcoir_v47_per_file_projection", False)):
            return original(prompt, schema, config, ignored_providers, model)

        attempt_count = int(getattr(config, "_dcoir_v47_request_attempt_count", 0) or 0) + 1
        setattr(config, "_dcoir_v47_request_attempt_count", attempt_count)

        api_key = base.env_required("OPENROUTER_API_KEY")
        payload = hardened.build_openrouter_payload(prompt, schema, config, ignored_providers, model)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/DCOIR-Collector/dcoir-collector",
            "X-OpenRouter-Title": base.REVIEW_DISPLAY_NAME,
        }
        sticky_session = hardened.session_id(config)
        if sticky_session:
            headers["X-Session-Id"] = sticky_session

        req = urllib.request.Request(
            hardened.OPENROUTER_API,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=180) as response:
            raw = response.read().decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise RuntimeError("OpenRouter returned a non-object response")

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise RuntimeError("OpenRouter returned an invalid choices payload")
        choice = choices[0]
        finish_reason = str(choice.get("finish_reason", "") or "").strip()
        model_used = str(data.get("model", model))
        service_tier = str(data.get("service_tier", "") or "")
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        telemetry = {
            "requested_model": str(model),
            "served_model": model_used,
            "provider": _response_provider(data),
            "service_tier": service_tier,
            "finish_reason": finish_reason,
            "usage": usage,
            "request_attempt_count": attempt_count,
            "response_healing_pipeline": (
                data.get("openrouter_metadata", {}).get("pipeline", [])
                if isinstance(data.get("openrouter_metadata"), dict)
                else []
            ),
        }
        setattr(config, "_dcoir_v47_last_request_telemetry", telemetry)

        if bool(getattr(config, "openrouter_require_stop_finish_reason", False)) and finish_reason != "stop":
            reason = finish_reason or "missing"
            raise RuntimeError(f"OpenRouter capped completion did not finish with stop: finish_reason={reason}")

        message = choice.get("message")
        content = message.get("content", "") if isinstance(message, dict) else ""
        if not content:
            raise RuntimeError("OpenRouter returned an empty response")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, flags=re.DOTALL)
            if not match:
                raise
            parsed = json.loads(match.group(1))
        if not isinstance(parsed, dict):
            raise RuntimeError("OpenRouter structured output did not have an object root")
        return parsed, model_used, service_tier

    hardened.openrouter_request_once = openrouter_request_once
    if hasattr(module, "openrouter_request_once"):
        module.openrouter_request_once = openrouter_request_once


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
        telemetry = getattr(projected, "_dcoir_v47_last_request_telemetry", None)
        if isinstance(result, dict) and isinstance(telemetry, dict):
            result["request_telemetry"] = dict(telemetry)
            path = str(context.get("path", "") or "") if isinstance(context, dict) else ""
            artifact_id = module.safe_artifact_name(path, f"file-{index:02d}")
            module.hardened.write_debug_json_artifact_safely(
                projected,
                f"metadata/per-file/{index:02d}-{artifact_id}-request-telemetry.json",
                {"path": path, **telemetry},
            )
        return result

    module.review_single_file_context = review_single_file_context


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    _patch_config_loader(module)
    _patch_payload_builder(module)
    _patch_request_once(module)
    _patch_per_file_review(module)
    setattr(module, APPLIED_MARKER, True)
