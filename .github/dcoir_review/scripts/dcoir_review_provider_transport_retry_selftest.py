#!/usr/bin/env python3
"""Deterministic regressions for DCOIR Review provider transport retries (#548)."""

from __future__ import annotations

import http.client
import importlib
import json
import os
import urllib.error

from dcoir_review.entrypoint import DcoirReviewEntrypoint
from dcoir_review.selftests.provider_transport.fixtures import (
    FakeResponse, Reporter, attempt_events, fresh_config, install_sequence,
    interrupted_credit_error, provider_response, review_schema,
)
from dcoir_review.selftests.provider_transport.http_errors import run_http_error_cases


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
        # can contaminate a later provider attempt on the same config. The marker
        # must retain the config object itself so Python object-id reuse cannot
        # make stale transport state match an unrelated later config.
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
        marker = getattr(v58._TRANSPORT_STATE, "marker", None)
        assert isinstance(marker, tuple) and len(marker) == 3
        assert marker[0] is config
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

        run_http_error_cases(review, retry_loop, v58.TRANSPORT_FAILURE_CLASS)

        # The script-level watchdog raises ReviewTimeoutError, which subclasses
        # TimeoutError but must still escape immediately so cleanup/failure
        # handling stays owned by the runtime timeout path.
        config = fresh_config(review, ["model-a"], attempts=2)
        calls, remaining = install_sequence(
            review,
            [FakeResponse(read_error=review.hardened.ReviewTimeoutError("script timeout"))],
        )
        try:
            retry_loop("probe", schema, config, Reporter())
        except review.hardened.ReviewTimeoutError:
            pass
        else:
            raise AssertionError("runtime watchdog timeout was converted into a retry")
        assert len(calls) == 1 and not remaining
        assert attempt_events(config) == []

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

        config = fresh_config(review, ["model-a"], attempts=2)
        calls, remaining = install_sequence(
            review,
            [interrupted_credit_error(), provider_response("production-credit-success", "model-a")],
        )
        result, model, _tier = review.hardened.openrouter_review(
            "probe", schema, config, Reporter()
        )
        assert result["summary"] == "production-credit-success" and model == "model-a"
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
