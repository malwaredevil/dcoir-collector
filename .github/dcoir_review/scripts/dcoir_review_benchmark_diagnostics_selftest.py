"""No-network hostile diagnostics checks, also run by the evaluator selftest."""
from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import Mock

import dcoir_review_first_pass_candidate_eval as evaluation
from dcoir_review_benchmark_diagnostics import provider_error_details, safe_scalar, REDACTED


def run_tests() -> None:
    api_key = "test/+key"
    error = {"code": 429, "message": "Provider capacity exhausted", "metadata": {
        "provider_name": "Example", "error_type": "rate_limit_exceeded",
        "provider_code": "busy", "raw": {"secret": api_key}, "flagged_input": api_key,
    }}
    for status in (200, 429):
        body = {"id": "test-id", "error": error, "usage": {"cost": .012}}
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.status = status
        response.headers = {"Retry-After": "12"}
        response.read.return_value = json.dumps(body).encode()
        opener = Mock(return_value=response)
        if status == 429:
            opener.side_effect = urllib.error.HTTPError(
                "https://example.invalid", status, "rate limit", {"Retry-After": "12"},
                io.BytesIO(json.dumps(body).encode()),
            )
        result = evaluation.call_openrouter({}, api_key, timeout_seconds=1, opener=opener)
        assert not result["ok"] and result["error"] == "provider-error"
        assert result["error_details"]["error_type"] == "rate_limit_exceeded"
        assert result["error_details"]["message"] == "Provider capacity exhausted"
        assert result["usage"]["cost_usd"] == .012
        assert result["retry_after_seconds"] == 12
        assert api_key not in json.dumps(result) and "flagged_input" not in json.dumps(result)
        assert opener.call_count == 1
    for field in ("error_type", "provider_code", "provider_name", "limit_source"):
        details = provider_error_details({"error": {"metadata": {field: api_key}}}, api_key)
        assert details[field] == REDACTED
    for field in ("code", "message", "type"):
        assert provider_error_details({"error": {field: api_key}}, api_key)[field] == REDACTED
    for message in ("Bearer abc", "api_key=abc", "password: abc", api_key,
                    "https://user:pass@example.com", "https://example.com?sig=abcd"):
        assert safe_scalar(message, api_key) == REDACTED
    from urllib.parse import quote
    import base64
    for variant in (quote(api_key, safe=""), base64.b64encode(api_key.encode()).decode()):
        assert safe_scalar(variant, api_key) == REDACTED
    assert len(safe_scalar("x" * 600, api_key)) == 512
    assert "oversize" in safe_scalar("x" * 9000 + api_key, api_key)
    for invalid in (None, [], True, {"raw": api_key}):
        assert safe_scalar(invalid, api_key) is None
        assert api_key not in json.dumps(provider_error_details({"error": invalid}, api_key))
    for retry in ("-1", "9999999", "1.5", api_key):
        from dcoir_review_benchmark_diagnostics import retry_after_seconds
        assert retry_after_seconds({"Retry-After": retry}) is None
    # Non-JSON error pages retain status/retry hints without persisting raw text.
    opener = Mock(side_effect=urllib.error.HTTPError(
        "https://example.invalid", 503, "unavailable", {"Retry-After": "20"},
        io.BytesIO(("<html>" + api_key + "</html>").encode()),
    ))
    invalid = evaluation.call_openrouter({}, api_key, timeout_seconds=1, opener=opener)
    assert invalid["http_status"] == 503 and invalid["retry_after_seconds"] == 20
    assert api_key not in json.dumps(invalid) and not invalid["ok"]
    assert opener.call_count == 1
    # Malformed usage cannot erase the original actionable error diagnostic.
    response.read.return_value = json.dumps({"error": error, "usage": {"cost": "malformed"}}).encode()
    response.status = 200
    opener = Mock(return_value=response)
    result = evaluation.call_openrouter({}, api_key, timeout_seconds=1, opener=opener)
    assert result["error_details"]["code"] == 429 and not result["ok"]


if __name__ == "__main__":
    run_tests()
    print("benchmark diagnostics selftest passed (no network)")
