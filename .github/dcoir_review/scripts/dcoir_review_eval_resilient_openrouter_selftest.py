#!/usr/bin/env python3
"""Deterministic no-network tests for resilient evaluation request capture."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile

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
        "choices": [{"message": {"content": json.dumps({"summary": "missing findings"})}}],
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
    assert result["http_status"] == 200
    assert result["generation_id"] == "gen-malformed"
    assert result["selected_provider"] == "Anthropic"
    assert result["usage"]["total_tokens"] == 110
    assert result["usage"]["cost_usd"] == 0.0123
    assert "missing findings array" in result["error"]["message"]

    valid = dict(malformed)
    valid["id"] = "gen-valid"
    valid["choices"] = [{"message": {"content": json.dumps({"summary": "clean", "findings": []})}}]
    ok = resilient.call_openrouter(
        base,
        payload,
        "unit-test-key",
        timeout_seconds=3,
        opener=lambda _request, timeout: FakeResponse(valid),
    )
    assert ok["ok"] is True
    assert ok["generation_id"] == "gen-valid"
    assert ok["result"]["findings"] == []

    print("dcoir_review_eval_resilient_openrouter_selftest passed: malformed structured output is preserved as a per-request error")


if __name__ == "__main__":
    main()
