#!/usr/bin/env python3
"""Resilient OpenRouter request adapter for evaluation-only DCOIR harnesses.

This module is intentionally outside the production reviewer path. It converts
transport, JSON, and structured-output failures into per-request records so a
single malformed response cannot erase the rest of a paid evaluation batch.
When DCOIR_EVAL_REQUEST_CHECKPOINT is set, each completed request is appended
as one JSON object per line for crash-safe evidence recovery.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any
import urllib.error
import urllib.request


def _append_checkpoint(result: dict[str, Any]) -> None:
    raw_path = os.environ.get("DCOIR_EVAL_REQUEST_CHECKPOINT", "").strip()
    if not raw_path:
        return
    path = Path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, sort_keys=True) + "\n")
        handle.flush()


def _metadata(base: Any, data: dict[str, Any]) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    metadata = data.get("openrouter_metadata") if isinstance(data.get("openrouter_metadata"), dict) else {}
    provider = base.selected_provider(metadata)
    pipeline = base.pipeline_summary(metadata)
    return metadata, provider, pipeline


def _finish_reason(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    return str(choices[0].get("finish_reason", "") or "").strip().lower()


def call_openrouter(
    base: Any,
    payload: dict[str, Any],
    api_key: str,
    *,
    timeout_seconds: int,
    opener: Any = urllib.request.urlopen,
) -> dict[str, Any]:
    """Make one evaluation request and always return a structured evidence row."""
    started = time.monotonic()
    request = urllib.request.Request(
        base.OPENROUTER_API,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=base.request_headers(api_key),
    )
    try:
        with opener(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            status = int(getattr(response, "status", 200) or 200)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        elapsed = time.monotonic() - started
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"error": {"message": raw[:1000]}}
        if not isinstance(data, dict):
            data = {
                "error": {
                    "message": f"OpenRouter HTTP error response root must be a JSON object, got {type(data).__name__}"
                }
            }
        metadata, provider, pipeline = _metadata(base, data)
        result = {
            "ok": False,
            "error_kind": "http-error",
            "http_status": int(exc.code),
            "latency_seconds": elapsed,
            "error": data.get("error", data),
            "openrouter_metadata": metadata,
            "selected_provider": provider,
            "pipeline": pipeline,
        }
        _append_checkpoint(result)
        return result
    except Exception as exc:  # network/timeout failures are evidence, not batch-fatal
        result = {
            "ok": False,
            "error_kind": "transport-error",
            "http_status": 0,
            "latency_seconds": time.monotonic() - started,
            "error": {"type": type(exc).__name__, "message": str(exc)[:1000]},
        }
        _append_checkpoint(result)
        return result

    elapsed = time.monotonic() - started
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        result = {
            "ok": False,
            "error_kind": "response-json-error",
            "http_status": status,
            "latency_seconds": elapsed,
            "requested_model": str(payload.get("model", "") or ""),
            "error": {"type": type(exc).__name__, "message": str(exc)[:1000]},
        }
        _append_checkpoint(result)
        return result
    if not isinstance(data, dict):
        result = {
            "ok": False,
            "error_kind": "response-json-error",
            "http_status": status,
            "latency_seconds": elapsed,
            "requested_model": str(payload.get("model", "") or ""),
            "error": {
                "type": "InvalidResponseRoot",
                "message": f"OpenRouter response root must be a JSON object, got {type(data).__name__}",
            },
        }
        _append_checkpoint(result)
        return result

    metadata, provider, pipeline = _metadata(base, data)
    finish_reason = _finish_reason(data)
    common = {
        "http_status": status,
        "latency_seconds": elapsed,
        "generation_id": str(data.get("id", "") or ""),
        "requested_model": str(payload.get("model", "") or ""),
        "served_model": str(data.get("model", payload.get("model", "")) or ""),
        "selected_provider": provider,
        "openrouter_metadata": metadata,
        "pipeline": pipeline,
        "usage": base.usage_summary(data),
        "finish_reason": finish_reason,
    }
    if finish_reason == "length":
        result = {
            "ok": False,
            "error_kind": "output-budget-exhausted",
            **common,
            "error": {
                "type": "FinishReasonLength",
                "message": "Completion stopped because the output-token budget was exhausted",
            },
        }
        _append_checkpoint(result)
        return result
    if finish_reason != "stop":
        result = {
            "ok": False,
            "error_kind": "non-stop-finish-reason",
            **common,
            "error": {
                "type": "NonStopFinishReason",
                "message": f"Completion did not finish with stop: {finish_reason or 'missing'}",
            },
        }
        _append_checkpoint(result)
        return result
    try:
        parsed = base.parse_content(data)
    except Exception as exc:
        result = {
            "ok": False,
            "error_kind": "structured-output-error",
            **common,
            "error": {"type": type(exc).__name__, "message": str(exc)[:1000]},
        }
        _append_checkpoint(result)
        return result

    result = {"ok": True, **common, "result": parsed}
    _append_checkpoint(result)
    return result


def install(base: Any) -> None:
    """Monkey-patch an evaluation module's shared request helper only."""
    base.call_openrouter = lambda payload, api_key, *, timeout_seconds, opener=urllib.request.urlopen: call_openrouter(
        base,
        payload,
        api_key,
        timeout_seconds=timeout_seconds,
        opener=opener,
    )
