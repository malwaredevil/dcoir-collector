#!/usr/bin/env python3
"""Deterministic regressions for DCOIR Review provider transport retries (#548)."""

from __future__ import annotations

import http.client
import importlib
import io
import json
import os
import urllib.error

from dcoir_review.entrypoint import DcoirReviewEntrypoint


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


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    post_telemetry = entrypoint.post_telemetry_patch_module_names
    assert "dcoir_review_required_runtime_patch_v58" in post_telemetry
    assert post_telemetry[-3:] == (
        "dcoir_review_required_runtime_patch_v55",
        "dcoir_review_required_runtime_patch_v56",
        "dcoir_review_required_runtime_patch_v57",
    )

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v54 = importlib.import_module("dcoir_review_required_runtime_patch_v54")
    v58 = importlib.import_module("dcoir_review_required_runtime_patch_v58")
    assert getattr(review, v58.APPLIED_MARKER, False) is True

    original_urlopen = review.hardened.urllib.request.urlopen
    original_sleep = review.hardened.time.sleep
    previous_key = os.environ.get("OPENROUTER_API_KEY")
    os.environ["OPENROUTER_API_KEY"] = "v58-selftest-key"
    review.hardened.time.sleep = lambda _seconds: None
    schema = review_schema()

    # Use the pre-v54 provider-review loop for deterministic attempt telemetry.
    # v58 patches its live request and telemetry globals after composition, so
    # this exercises the same bounded model/attempt loop without v54's shallow
    # stage-config projection hiding the per-attempt history from the test.
    retry_loop = getattr(review.hardened, v54.REVIEW_STORAGE)
    assert callable(retry_loop)

    try:
        # Exact production failure shape: urlopen returns a response object and
        # response.read() raises IncompleteRead on the first attempt, followed by a
        # clean same-model response. The partial bytes contain valid-looking JSON
        # and must never be parsed as model output.
        config = fresh_config(review, ["model-a"], attempts=2)
        partial = json.dumps(
            provider_response("must-not-be-used", "model-a")
        ).encode("utf-8")
        calls, remaining = install_sequence(
            review,
            [
                FakeResponse(
                    read_error=http.client.IncompleteRead(
                        partial, len(partial) + 10
                    )
                ),
                provider_response("retry-success", "model-a"),
            ],
        )
        result, model, _tier = retry_loop("probe", schema, config, Reporter())
        assert result["summary"] == "retry-success" and model == "model-a"
        assert len(calls) == 2 and not remaining
        events = attempt_events(config)
        assert [item["outcome"] for item in events] == ["retry", "success"]
        assert events[0]["failure_class"] == v58.TRANSPORT_FAILURE_CLASS

        # Adjacent connection-abort failures receive the same bounded retry.
        config = fresh_config(review, ["model-a"], attempts=2)
        calls, remaining = install_sequence(
            review,
            [
                ConnectionResetError("connection reset by peer"),
                provider_response("reset-retry-success", "model-a"),
            ],
        )
        result, model, _tier = retry_loop("probe", schema, config, Reporter())
        assert result["summary"] == "reset-retry-success" and model == "model-a"
        assert len(calls) == 2 and not remaining
        events = attempt_events(config)
        assert events[0]["failure_class"] == v58.TRANSPORT_FAILURE_CLASS
        assert events[0]["outcome"] == "retry"

        # URLError is retryable only when its wrapped reason is independently
        # classified as a transient transport failure.
        config = fresh_config(review, ["model-a"], attempts=2)
        calls, remaining = install_sequence(
            review,
            [
                urllib.error.URLError(ConnectionResetError("wrapped reset")),
                provider_response("urlerror-retry-success", "model-a"),
            ],
        )
        result, model, _tier = retry_loop("probe", schema, config, Reporter())
        assert result["summary"] == "urlerror-retry-success" and model == "model-a"
        assert len(calls) == 2 and not remaining
        assert attempt_events(config)[0]["failure_class"] == v58.TRANSPORT_FAILURE_CLASS

        # Exhaust the current model's retry budget, then preserve configured
        # model-stack fallback order.
        config = fresh_config(review, ["model-a", "model-b"], attempts=2)
        calls, remaining = install_sequence(
            review,
            [
                http.client.IncompleteRead(b"partial-a1", 30),
                ConnectionResetError("reset-a2"),
                provider_response("fallback-success", "model-b"),
            ],
        )
        result, model, _tier = retry_loop("probe", schema, config, Reporter())
        assert result["summary"] == "fallback-success" and model == "model-b"
        assert len(calls) == 3 and not remaining
        events = attempt_events(config)
        assert [item["outcome"] for item in events] == ["retry", "fallback", "success"]
        assert all(
            item.get("failure_class", "") == v58.TRANSPORT_FAILURE_CLASS
            for item in events[:2]
        )

        # If every bounded transport attempt fails and no model remains, the
        # review stays fail-closed.
        config = fresh_config(review, ["model-a"], attempts=2)
        calls, remaining = install_sequence(
            review,
            [
                http.client.IncompleteRead(b"one", 9),
                ConnectionAbortedError("aborted"),
            ],
        )
        try:
            retry_loop("probe", schema, config, Reporter())
        except RuntimeError as exc:
            assert "retryable transport failure" in str(exc)
        else:
            raise AssertionError("exhausted transport failures did not fail closed")
        assert len(calls) == 2 and not remaining
        events = attempt_events(config)
        assert [item["outcome"] for item in events] == ["retry", "terminal_failure"]
        assert all(
            item["failure_class"] == v58.TRANSPORT_FAILURE_CLASS for item in events
        )

        # A direct request-boundary probe must not leave transport telemetry that
        # can contaminate a later provider attempt on the same config.
        config = fresh_config(review, ["model-a"], attempts=2)
        calls, remaining = install_sequence(
            review,
            [
                FakeResponse(
                    read_error=http.client.IncompleteRead(b"direct-partial", 30)
                )
            ],
        )
        try:
            review.hardened.openrouter_request_once(
                "probe", schema, config, [], "model-a"
            )
        except RuntimeError as exc:
            assert "retryable transport failure" in str(exc)
        else:
            raise AssertionError("direct transport probe unexpectedly succeeded")
        assert len(calls) == 1 and not remaining
        calls, remaining = install_sequence(
            review,
            [provider_response("after-direct-probe", "model-a")],
        )
        result, model, _tier = retry_loop("probe", schema, config, Reporter())
        assert result["summary"] == "after-direct-probe" and model == "model-a"
        assert len(calls) == 1 and not remaining
        events = attempt_events(config)
        assert [item["outcome"] for item in events] == ["success"]
        assert events[0].get("failure_class", "") == ""

        # A retryable HTTP status whose error-body read is itself interrupted must
        # stay inside the same bounded retry loop. The interrupted body is not
        # parsed, while status metadata remains attached to transport telemetry.
        config = fresh_config(review, ["model-a"], attempts=2)
        interrupted_503 = urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/chat/completions",
            503,
            "service unavailable",
            {"Retry-After": "1"},
            FakeResponse(
                read_error=http.client.IncompleteRead(b"partial-error-body", 80)
            ),
        )
        calls, remaining = install_sequence(
            review,
            [
                interrupted_503,
                provider_response("http-body-retry-success", "model-a"),
            ],
        )
        result, model, _tier = retry_loop("probe", schema, config, Reporter())
        assert result["summary"] == "http-body-retry-success" and model == "model-a"
        assert len(calls) == 2 and not remaining
        events = attempt_events(config)
        assert [item["outcome"] for item in events] == ["retry", "success"]
        assert events[0]["failure_class"] == v58.TRANSPORT_FAILURE_CLASS
        assert events[0]["http_status"] == 503

        # A non-retryable status does not become retryable merely because its body
        # read was interrupted. It remains on the historical HTTP status path.
        config = fresh_config(review, ["model-a"], attempts=2)
        interrupted_400 = urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/chat/completions",
            400,
            "bad request",
            {},
            FakeResponse(
                read_error=http.client.IncompleteRead(b"partial-bad-request", 80)
            ),
        )
        calls, remaining = install_sequence(review, [interrupted_400])
        try:
            retry_loop("probe", schema, config, Reporter())
        except RuntimeError:
            pass
        else:
            raise AssertionError("interrupted non-retryable HTTP status unexpectedly retried")
        assert len(calls) == 1 and not remaining
        events = attempt_events(config)
        assert len(events) == 1
        assert events[0]["failure_class"] == "http_error"
        assert events[0]["http_status"] == 400
        assert events[0]["outcome"] == "terminal_failure"

        # Readable HTTP status errors remain owned by the historical HTTPError path.
        config = fresh_config(review, ["model-a"], attempts=2)
        http_error = urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/chat/completions",
            400,
            "bad request",
            {},
            io.BytesIO(b'{"error":{"message":"bad request"}}'),
        )
        calls, remaining = install_sequence(review, [http_error])
        try:
            retry_loop("probe", schema, config, Reporter())
        except RuntimeError:
            pass
        else:
            raise AssertionError("non-retryable HTTP status unexpectedly succeeded")
        assert len(calls) == 1 and not remaining
        events = attempt_events(config)
        assert len(events) == 1 and events[0]["failure_class"] == "http_error"
        assert events[0]["http_status"] == 400

        # Generic HTTPException subclasses that describe local/client-state
        # failures are not transient response-read interruptions and must escape
        # without consuming the provider retry budget.
        config = fresh_config(review, ["model-a"], attempts=2)
        invalid_url = http.client.InvalidURL("invalid provider URL")
        calls, remaining = install_sequence(review, [invalid_url])
        try:
            retry_loop("probe", schema, config, Reporter())
        except http.client.InvalidURL:
            pass
        else:
            raise AssertionError("non-transient HTTPException was converted into a retry")
        assert len(calls) == 1 and not remaining
        assert attempt_events(config) == []

        # Full production wrapper composition also has transport retry active.
        config = fresh_config(review, ["model-a"], attempts=2)
        calls, remaining = install_sequence(
            review,
            [
                FakeResponse(
                    read_error=http.client.IncompleteRead(b"prod-partial", 99)
                ),
                provider_response("production-success", "model-a"),
            ],
        )
        result, model, _tier = review.hardened.openrouter_review(
            "probe", schema, config, Reporter()
        )
        assert result["summary"] == "production-success" and model == "model-a"
        assert len(calls) == 2 and not remaining
    finally:
        review.hardened.urllib.request.urlopen = original_urlopen
        review.hardened.time.sleep = original_sleep
        if previous_key is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = previous_key

    print("dcoir_review_provider_transport_retry_selftest passed")


if __name__ == "__main__":
    main()
