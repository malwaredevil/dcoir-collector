#!/usr/bin/env python3
"""Deterministic no-network tests for resilient evaluation request capture."""
from __future__ import annotations

import json

import dcoir_review_eval_resilient_openrouter as resilient
import dcoir_review_first_pass_candidate_eval as base


class FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def main() -> None:
    payload = {"model": "anthropic/claude-opus-5"}
    malformed = {
        "id": "gen-malformed",
        "model": "anthropic/claude-opus-5",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": json.dumps({"summary": "missing findings"})},
            }
        ],
        "usage": {
            "prompt_tokens": 101,
            "completion_tokens": 9,
            "total_tokens": 110,
            "cost": 0.0123,
            "completion_tokens_details": {"reasoning_tokens": 4},
        },
        "openrouter_metadata": {
            "endpoints": {"available": [{"provider": "Anthropic", "selected": True}]},
            "pipeline": [{"type": "response_healing", "name": "response-healing"}],
        },
    }

    result = resilient.call_openrouter(
        base,
        payload,
        "unit-test-key",
        timeout_seconds=3,
        opener=lambda _request, timeout: FakeResponse(malformed),
    )
    assert result["ok"] is False
    assert result["error_kind"] == "structured-output-error"
    assert result["finish_reason"] == "stop"
    assert result["http_status"] == 200
    assert result["generation_id"] == "gen-malformed"
    assert result["selected_provider"] == "Anthropic"
    assert result["usage"]["total_tokens"] == 110
    assert result["usage"]["cost_usd"] == 0.0123
    assert "missing findings array" in result["error"]["message"]

    valid = dict(malformed)
    valid["id"] = "gen-valid"
    valid["choices"] = [
        {
            "finish_reason": "stop",
            "message": {"content": json.dumps({"summary": "clean", "findings": []})},
        }
    ]
    ok = resilient.call_openrouter(
        base,
        payload,
        "unit-test-key",
        timeout_seconds=3,
        opener=lambda _request, timeout: FakeResponse(valid),
    )
    assert ok["ok"] is True
    assert ok["generation_id"] == "gen-valid"
    assert ok["finish_reason"] == "stop"
    assert ok["result"]["findings"] == []

    exhausted = dict(valid)
    exhausted["id"] = "gen-length"
    exhausted["choices"] = [
        {
            "finish_reason": "length",
            "message": {"content": json.dumps({"summary": "partial", "findings": []})},
        }
    ]
    length_result = resilient.call_openrouter(
        base,
        payload,
        "unit-test-key",
        timeout_seconds=3,
        opener=lambda _request, timeout: FakeResponse(exhausted),
    )
    assert length_result["ok"] is False
    assert length_result["error_kind"] == "output-budget-exhausted"
    assert length_result["finish_reason"] == "length"
    assert length_result["usage"]["total_tokens"] == 110

    filtered = dict(valid)
    filtered["id"] = "gen-filtered"
    filtered["choices"] = [
        {
            "finish_reason": "content_filter",
            "message": {"content": json.dumps({"summary": "clean", "findings": []})},
        }
    ]
    filtered_result = resilient.call_openrouter(
        base,
        payload,
        "unit-test-key",
        timeout_seconds=3,
        opener=lambda _request, timeout: FakeResponse(filtered),
    )
    assert filtered_result["ok"] is False
    assert filtered_result["error_kind"] == "non-stop-finish-reason"
    assert filtered_result["finish_reason"] == "content_filter"

    non_object_result = resilient.call_openrouter(
        base,
        payload,
        "unit-test-key",
        timeout_seconds=3,
        opener=lambda _request, timeout: FakeResponse([]),
    )
    assert non_object_result["ok"] is False
    assert non_object_result["error_kind"] == "response-json-error"
    assert non_object_result["error"]["type"] == "InvalidResponseRoot"

    print(
        "dcoir_review_eval_resilient_openrouter_selftest passed: "
        "structured-output/JSON-shape errors and non-stop/length completions fail closed with usage preserved"
    )


if __name__ == "__main__":
    main()
