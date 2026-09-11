"""Shared deterministic provider transport fixtures; no live network calls."""

from __future__ import annotations

import http.client
import json
import urllib.error


class FakeResponse:
    def __init__(
        self,
        payload: dict | None = None,
        *,
        read_error: Exception | None = None,
    ) -> None:
        if payload is None and read_error is None:
            raise ValueError("fake response requires payload or read_error")
        self._raw = (
            json.dumps(payload).encode("utf-8") if payload is not None else b""
        )
        self._read_error = read_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        if self._read_error is not None:
            raise self._read_error
        return self._raw

    def close(self) -> None:
        pass


class Reporter:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def update(self, stage: str, message: str) -> None:
        self.events.append((stage, message))


def provider_response(summary: str, model: str) -> dict:
    content = json.dumps({"summary": summary, "findings": []})
    return {
        "model": model,
        "provider": "test-provider",
        "service_tier": "default",
        "choices": [{"finish_reason": "stop", "message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001},
    }


def review_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "findings": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["summary", "findings"],
        "additionalProperties": False,
    }


def fresh_config(review, models: list[str], attempts: int = 2):
    config = review.load_pareto_context_config(
        ".github/dcoir_review/openrouter-pr-review-pareto.yml"
    )
    config.model_stack = list(models)
    config.fallback_models = []
    config.ignored_providers = []
    config.openrouter_max_attempts = attempts
    config.openrouter_retry_max_seconds = 1
    config.openrouter_capture_request_telemetry = True
    config.openrouter_require_stop_finish_reason = False
    config.openrouter_require_object_response = True
    config._openrouter_request_attempt_count = 0
    config._openrouter_request_telemetry_events = []
    config._openrouter_request_attempt_telemetry_events = []
    config._openrouter_last_request_telemetry = {}
    return config


def install_sequence(review, sequence):
    calls: list[object] = []
    remaining = list(sequence)

    def fake_urlopen(request, timeout=180):
        calls.append(request)
        if not remaining:
            raise AssertionError("unexpected extra provider request")
        item = remaining.pop(0)
        if isinstance(item, FakeResponse):
            return item
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)

    review.hardened.urllib.request.urlopen = fake_urlopen
    return calls, remaining


def attempt_events(config) -> list[dict]:
    values = getattr(config, "_openrouter_request_attempt_telemetry_events", [])
    return [dict(item) for item in values if isinstance(item, dict)]


def interrupted_credit_error() -> urllib.error.HTTPError:
    # Even a parseable partial body must be discarded, not used to classify 402.
    partial = b'{"error":{"message":"Insufficient credits. Add credits to continue."}}'
    return urllib.error.HTTPError(
        "https://openrouter.ai/api/v1/chat/completions",
        402,
        "payment required",
        {"Retry-After": "1"},
        FakeResponse(read_error=http.client.IncompleteRead(partial, len(partial) + 10)),
    )
