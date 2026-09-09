"""Provider-side deterministic structured-output recovery for DCOIR Review v52."""

from __future__ import annotations

import json as _stdlib_json
import types
from typing import Any

import dcoir_review_required_runtime_patch_v48_core as v48_core

RECOVERY_ATTR = "_dcoir_v52_last_structured_output_recovery"
_PROVIDER_STORAGE = "_dcoir_review_v52_prior_openrouter_request_once"
_REVIEW_STORAGE = "_dcoir_review_v52_prior_openrouter_review"
_V48_PROVIDER_STORAGE = "_dcoir_review_v48_original_openrouter_request_once"


def balanced_object_ranges(text: str) -> list[tuple[int, int]]:
    """Return top-level brace ranges while respecting JSON strings/escapes."""
    ranges: list[tuple[int, int]] = []
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
            continue
        if char == "}":
            if depth <= 0:
                return []
            depth -= 1
            if depth == 0:
                ranges.append((start, index + 1))
                start = -1
    if depth != 0 or in_string:
        return []
    return ranges


class RecoveryJsonProxy:
    """Keep the API envelope strict; recover one model-content object only."""

    def __init__(self, real_json: Any) -> None:
        self._json = real_json
        self.structured_mode = ""
        self._saw_fenced_failure = False
        self._loads_count = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._json, name)

    def loads(self, value: Any, *args: Any, **kwargs: Any) -> Any:
        self._loads_count += 1
        try:
            parsed = self._json.loads(value, *args, **kwargs)
        except self._json.JSONDecodeError as original_error:
            if not isinstance(value, str) or self._loads_count == 1:
                # The first loads() in the provider parses OpenRouter's own HTTP
                # JSON envelope and must remain strict. Recovery applies only to
                # the model message content parsed by later loads() calls.
                raise
            # Preserve the existing fenced-object recovery in the hardened
            # provider. Its next loads() call is labelled after extraction.
            if "```" in value:
                self._saw_fenced_failure = True
                raise
            ranges = balanced_object_ranges(value)
            if len(ranges) != 1:
                raise original_error
            start, end = ranges[0]
            try:
                parsed = self._json.loads(value[start:end], *args, **kwargs)
            except self._json.JSONDecodeError:
                raise original_error
            if not isinstance(parsed, dict):
                raise original_error
            self.structured_mode = "balanced-envelope"
            return parsed
        if self._saw_fenced_failure and isinstance(parsed, dict):
            self.structured_mode = "fenced-object"
            self._saw_fenced_failure = False
        return parsed


def clone_with_json_proxy(function: Any) -> tuple[Any, RecoveryJsonProxy]:
    real_json = function.__globals__.get("json", _stdlib_json)
    proxy = RecoveryJsonProxy(real_json)
    namespace = dict(function.__globals__)
    namespace["json"] = proxy
    clone = types.FunctionType(
        function.__code__,
        namespace,
        name=function.__name__,
        argdefs=function.__defaults__,
        closure=function.__closure__,
    )
    clone.__kwdefaults__ = getattr(function, "__kwdefaults__", None)
    return clone, proxy


def annotate_request_telemetry(config: Any, mode: str) -> None:
    setattr(config, RECOVERY_ATTR, mode)
    history = getattr(config, "_openrouter_request_telemetry_events", None)
    if not isinstance(history, list) or not history:
        return
    updated = [dict(item) if isinstance(item, dict) else item for item in history]
    if isinstance(updated[-1], dict):
        updated[-1]["structured_output_recovery"] = mode
    setattr(config, "_openrouter_request_telemetry_events", updated)
    last = getattr(config, "_openrouter_last_request_telemetry", None)
    if isinstance(last, dict):
        revised = dict(last)
        revised["structured_output_recovery"] = mode
        revised["request_events"] = [
            dict(item) if isinstance(item, dict) else item for item in updated
        ]
        setattr(config, "_openrouter_last_request_telemetry", revised)


def patch_provider(module: Any) -> None:
    """Replace the v48 provider boundary while preserving its exact-scope guard."""
    hardened = module.hardened
    current = getattr(hardened, "openrouter_request_once", None)
    if not callable(current):
        raise RuntimeError("DCOIR v52 could not locate hardened openrouter_request_once")
    if not hasattr(hardened, _PROVIDER_STORAGE):
        setattr(hardened, _PROVIDER_STORAGE, current)

    core_request = getattr(hardened, _V48_PROVIDER_STORAGE, None)
    if not callable(core_request):
        raise RuntimeError("DCOIR v52 requires the v48 exact-scope provider boundary")

    def openrouter_request_once(prompt, schema, config, ignored_providers, model):
        if v48_core._guard(module) is not None:
            v48_core.assert_current_review_scope(module, f"model request ({model})", config)
            v48_core.authorize_provider_request(module, config)
        clone, proxy = clone_with_json_proxy(core_request)
        try:
            result = clone(prompt, schema, config, ignored_providers, model)
        except Exception:
            annotate_request_telemetry(config, "failed")
            raise
        mode = proxy.structured_mode or "direct"
        annotate_request_telemetry(config, mode)
        if v48_core._guard(module) is not None:
            v48_core.assert_current_review_scope(module, f"model response ({model})", config)
        return result

    hardened.openrouter_request_once = openrouter_request_once
    if hasattr(module, "openrouter_request_once"):
        module.openrouter_request_once = openrouter_request_once

    current_review = getattr(hardened, "openrouter_review", None)
    if not callable(current_review):
        raise RuntimeError("DCOIR v52 could not locate hardened openrouter_review")
    if not hasattr(hardened, _REVIEW_STORAGE):
        setattr(hardened, _REVIEW_STORAGE, current_review)

    def openrouter_review(prompt, schema, config, reporter=None):
        setattr(config, RECOVERY_ATTR, "")
        result = current_review(prompt, schema, config, reporter)
        mode = str(getattr(config, RECOVERY_ATTR, "") or "")
        if reporter and mode not in {"", "direct"}:
            reporter.update(
                "structured-output-recovery",
                f"mode={mode}; deterministic envelope recovery avoided semantic replay",
            )
        return result

    hardened.openrouter_review = openrouter_review
    if hasattr(module, "openrouter_review"):
        module.openrouter_review = openrouter_review
