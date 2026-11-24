"""Bounded, credential-conscious diagnostics for offline model comparisons.

Only allowlisted scalar fields are persisted. Raw provider bodies, headers,
moderation inputs and debug payloads deliberately have no serialization path.
"""
from __future__ import annotations

import base64
import json
import re
from typing import Any
from urllib.parse import quote, quote_plus

MAX_FIELD_CHARS = 512
MAX_INPUT_CHARS = 8192
SENSITIVE = re.compile(
    r"(?i)authorization|\bbearer\b|\bbasic\s+|api[_ -]?key|"
    r"(?:access|refresh|session)[_ -]?token|password|secret|"
    r"\bsk[-_]|\bgh[pousr]_|github_pat_|AKIA[0-9A-Z]{16}|"
    r"-----BEGIN|https?://[^\s/]+@|[?&](?:sig|signature|token|credential)="
)
REDACTED = "[credential-bearing diagnostic omitted]"


def safe_scalar(value: Any, api_key: str) -> str | int | None:
    if type(value) is int:
        return value if abs(value) < 10**12 else None
    if not isinstance(value, str):
        return None
    # Oversize strings are omitted, not truncated before credential detection.
    if len(value) > MAX_INPUT_CHARS:
        return "[oversize diagnostic omitted]"
    if api_key:
        variants = {
            api_key, quote(api_key, safe=""), quote_plus(api_key),
            json.dumps(api_key)[1:-1],
            base64.b64encode(api_key.encode()).decode(),
            base64.urlsafe_b64encode(api_key.encode()).decode(),
        }
        if any(secret and secret in value for secret in variants):
            return REDACTED
    if SENSITIVE.search(value):
        return REDACTED
    # Prevent control characters and multiline Markdown from entering summaries.
    value = " ".join("".join(c if c.isprintable() else " " for c in value).split())
    return value[:MAX_FIELD_CHARS]


def provider_error_details(data: dict[str, Any], api_key: str) -> dict[str, Any]:
    error = data.get("error")
    if not isinstance(error, dict):
        return {"shape": "missing-or-non-object-error"}
    details: dict[str, Any] = {}
    for key in ("code", "message", "type"):
        value = safe_scalar(error.get(key), api_key)
        if value is not None:
            details[key] = value
    metadata = error.get("metadata")
    if isinstance(metadata, dict):
        for key in ("error_type", "provider_code", "provider_name", "limit_source"):
            value = safe_scalar(metadata.get(key), api_key)
            if value is not None:
                details[key] = value
    return details


def retry_after_seconds(headers: Any) -> int | None:
    """Record bounded numeric retry guidance without retrying a paid request."""
    value = headers.get("Retry-After") if hasattr(headers, "get") else None
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,5}", value.strip()):
        seconds = int(value)
        if seconds <= 86400:
            return seconds
    return None
