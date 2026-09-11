"""HTTP error-body interruption and credit retry contract regressions."""

from __future__ import annotations

import http.client
import io
import json
import urllib.error

from .fixtures import (
    FakeResponse, Reporter, attempt_events, fresh_config,
    install_sequence, interrupted_credit_error, provider_response, review_schema,
)


def run_http_error_cases(review, retry_loop, transport_failure_class: str) -> None:
    schema = review_schema()
    # A retryable HTTP status whose error-body read is itself interrupted must
    # stay inside the historical status-specific bounded retry loop. The
    # interrupted body is not parsed, while status metadata remains attached
    # to transport telemetry.
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
    assert events[0]["failure_class"] == transport_failure_class
    assert events[0]["http_status"] == 503

    # Interrupted 402 bodies cannot distinguish depleted credits from the
    # retryable in-flight-credit case. Retry the transport failure within the
    # existing attempt budget, preserving status and Retry-After handling.
    config = fresh_config(review, ["model-a"], attempts=2)
    calls, remaining = install_sequence(
        review,
        [interrupted_credit_error(), provider_response("credit-retry-success", "model-a")],
    )
    delays = []
    review.hardened.time.sleep = delays.append
    result, model, _tier = retry_loop("probe", schema, config, Reporter())
    review.hardened.time.sleep = lambda _seconds: None
    assert result["summary"] == "credit-retry-success" and model == "model-a"
    assert len(calls) == 2 and not remaining
    assert delays == [1.0]
    events = attempt_events(config)
    assert [item["outcome"] for item in events] == ["retry", "success"]
    assert events[0]["failure_class"] == transport_failure_class
    assert events[0]["http_status"] == 402

    # Repeated interruptions exhaust each model's budget and fail closed
    # after the last model, without a new retry counter or unlimited loop.
    config = fresh_config(review, ["model-a", "model-b"], attempts=2)
    calls, remaining = install_sequence(
        review, [interrupted_credit_error() for _ in range(4)]
    )
    try:
        retry_loop("probe", schema, config, Reporter())
    except RuntimeError as exc:
        assert "HTTP 402" in str(exc)
    else:
        raise AssertionError("interrupted 402 exhaustion did not fail closed")
    assert len(calls) == 4 and not remaining
    events = attempt_events(config)
    assert [item["outcome"] for item in events] == [
        "retry", "fallback", "retry", "terminal_failure"
    ]
    assert [json.loads(call.data)["model"] for call in calls] == [
        "model-a", "model-a", "model-b", "model-b"
    ]
    assert all(item["failure_class"] == transport_failure_class for item in events)
    assert all(item["http_status"] == 402 for item in events)

    # A complete 402 remains governed by its message. A previous interrupted
    # attempt must not make a later depleted-credit response retryable.
    for interrupted_first in (False, True):
        config = fresh_config(review, ["model-a"], attempts=3)
        depleted = urllib.error.HTTPError(
            "https://openrouter.ai/api/v1/chat/completions", 402,
            "payment required", {},
            io.BytesIO(b'{"error":{"message":"Insufficient credits. Add credits to continue."}}'),
        )
        sequence = [interrupted_credit_error(), depleted] if interrupted_first else [depleted]
        calls, remaining = install_sequence(review, sequence)
        try:
            retry_loop("probe", schema, config, Reporter())
        except RuntimeError as exc:
            assert "HTTP 402" in str(exc)
        else:
            raise AssertionError("depleted credits did not fail closed")
        assert len(calls) == len(sequence) and not remaining
        events = attempt_events(config)
        assert events[-1]["outcome"] == "terminal_failure"
        assert events[-1]["failure_class"] == "http_error"
        assert events[-1]["http_status"] == 402

    # A non-retryable status does not become retryable merely because its body
    # read was interrupted. Retry disposition still comes from the historical
    # HTTP status policy, while telemetry records that the body transport failed.
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
    assert events[0]["failure_class"] == transport_failure_class
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
