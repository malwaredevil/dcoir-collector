#!/usr/bin/env python3
"""DCOIR Review v58: bounded retry for interrupted provider transport reads.

Issue #548 proved that a chunked HTTP response can fail inside ``response.read()``
with ``http.client.IncompleteRead``. That exception bypassed the existing
provider retry loop even though the request had remaining attempts. This
post-composition overlay maps only narrowly classified transient transport
failures onto the existing bounded empty-response retry lane, while preserving
the original HTTP-status, JSON/schema, routing, and fail-closed behavior.
"""

from __future__ import annotations

import http.client
import ssl
import threading
import urllib.error
from typing import Any


APPLIED_MARKER = "_dcoir_v58_transport_retry_applied"
REQUEST_STORAGE = "_dcoir_v58_original_openrouter_request_once"
TELEMETRY_STORAGE = "_dcoir_v58_original_record_openrouter_attempt_telemetry"
TRANSPORT_FAILURE_CLASS = "transport_error"
_RETRYABLE_HTTP_EXCEPTIONS = (
    http.client.IncompleteRead,
    http.client.RemoteDisconnected,
)
_TRANSPORT_STATE = threading.local()


def _is_retryable_transport_exception(exc: Exception) -> bool:
    """Return whether *exc* is an explicitly retryable transport failure.

    HTTP status failures stay owned by the existing ``HTTPError`` branch. Broad
    ``http.client.HTTPException`` subclasses are intentionally not accepted:
    invalid URL, client-state, unsupported-protocol, and similar local failures
    are not transient response-read interruptions. TLS certificate verification
    failures are also intentionally excluded.
    """

    if isinstance(exc, urllib.error.HTTPError):
        return False
    if isinstance(exc, ssl.SSLCertVerificationError):
        return False
    if isinstance(exc, _RETRYABLE_HTTP_EXCEPTIONS):
        return True
    if isinstance(exc, (TimeoutError, ConnectionError, ssl.SSLEOFError)):
        return True
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            return False
        return isinstance(
            reason,
            _RETRYABLE_HTTP_EXCEPTIONS
            + (TimeoutError, ConnectionError, ssl.SSLEOFError),
        )
    return False


def _request_attempt_count(config: Any) -> int:
    try:
        return max(
            0,
            int(getattr(config, "_openrouter_request_attempt_count", 0) or 0),
        )
    except (OverflowError, TypeError, ValueError):
        return 0


def _set_transport_marker(config: Any) -> None:
    _TRANSPORT_STATE.marker = (id(config), _request_attempt_count(config))


def _take_transport_marker(config: Any) -> bool:
    marker = getattr(_TRANSPORT_STATE, "marker", None)
    try:
        delattr(_TRANSPORT_STATE, "marker")
    except AttributeError:
        pass
    if not isinstance(marker, tuple) or len(marker) != 2:
        return False
    config_id, attempt_count = marker
    return config_id == id(config) and attempt_count == _request_attempt_count(config)


def _patch_request_boundary(module: Any) -> None:
    hardened = module.hardened
    original = getattr(hardened, REQUEST_STORAGE, None)
    if original is None:
        original = getattr(hardened, "openrouter_request_once", None)
        if callable(original):
            setattr(hardened, REQUEST_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v58 could not locate hardened openrouter_request_once")

    def openrouter_request_once(prompt, schema, config, ignored_providers, model):
        try:
            return original(prompt, schema, config, ignored_providers, model)
        except Exception as exc:
            if not _is_retryable_transport_exception(exc):
                raise
            _set_transport_marker(config)
            # The historical retry loop already retries bounded empty-response
            # RuntimeError failures. Reuse that lane instead of duplicating the
            # model/attempt/backoff policy here. Never inspect or recover
            # IncompleteRead.partial bytes: a partial provider envelope is not
            # trustworthy model output.
            raise RuntimeError(
                "OpenRouter returned an empty response after retryable transport failure "
                f"({type(exc).__name__})"
            ) from exc

    hardened.openrouter_request_once = openrouter_request_once
    if hasattr(module, "openrouter_request_once"):
        module.openrouter_request_once = openrouter_request_once


def _patch_attempt_telemetry(module: Any) -> None:
    hardened = module.hardened
    original = getattr(hardened, TELEMETRY_STORAGE, None)
    if original is None:
        original = getattr(hardened, "_record_openrouter_attempt_telemetry", None)
        if callable(original):
            setattr(hardened, TELEMETRY_STORAGE, original)
    if not callable(original):
        raise RuntimeError("DCOIR v58 could not locate provider attempt telemetry recorder")

    def record_openrouter_attempt_telemetry(config, event):
        transport_failure = _take_transport_marker(config)
        revised = dict(event) if isinstance(event, dict) else {}
        if transport_failure and revised.get("failure_class") == "empty_response":
            revised["failure_class"] = TRANSPORT_FAILURE_CLASS
        original(config, revised)

    hardened._record_openrouter_attempt_telemetry = record_openrouter_attempt_telemetry


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    _patch_request_boundary(module)
    _patch_attempt_telemetry(module)
    setattr(module, APPLIED_MARKER, True)
