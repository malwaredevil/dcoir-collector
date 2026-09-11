#!/usr/bin/env python3
"""DCOIR Review v58: bounded retry for interrupted provider transport reads.

Issue #548 proved that a chunked HTTP response can fail inside ``response.read()``
with ``http.client.IncompleteRead``.  That exception bypassed the existing
provider retry loop even though the request had remaining attempts.  This
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
_TRANSPORT_STATE = threading.local()


def _transport_exception_name(exc: Exception) -> str:
    """Return a bounded retryable transport class name, or an empty string.

    HTTP status failures stay owned by the existing ``HTTPError`` branch.  TLS
    certificate verification failures are intentionally not converted into
    transient retries.  For ``URLError`` only an explicitly retryable wrapped
    reason is accepted.
    """

    if isinstance(exc, urllib.error.HTTPError):
        return ""
    if isinstance(exc, ssl.SSLCertVerificationError):
        return ""
    if isinstance(exc, http.client.HTTPException):
        return type(exc).__name__[:80]
    if isinstance(exc, (TimeoutError, ConnectionError, ssl.SSLEOFError)):
        return type(exc).__name__[:80]
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            return ""
        if isinstance(reason, http.client.HTTPException):
            return f"URLError[{type(reason).__name__}]"[:80]
        if isinstance(reason, (TimeoutError, ConnectionError, ssl.SSLEOFError)):
            return f"URLError[{type(reason).__name__}]"[:80]
    return ""


def _set_transport_marker(exception_name: str) -> None:
    _TRANSPORT_STATE.exception_name = exception_name[:80]


def _take_transport_marker() -> str:
    value = str(getattr(_TRANSPORT_STATE, "exception_name", "") or "")[:80]
    try:
        delattr(_TRANSPORT_STATE, "exception_name")
    except AttributeError:
        pass
    return value


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
            exception_name = _transport_exception_name(exc)
            if not exception_name:
                raise
            _set_transport_marker(exception_name)
            # The historical retry loop already retries bounded empty-response
            # RuntimeError failures. Reuse that lane instead of duplicating the
            # model/attempt/backoff policy here. Never inspect or recover
            # IncompleteRead.partial bytes: a partial provider envelope is not
            # trustworthy model output.
            raise RuntimeError(
                f"OpenRouter returned an empty response after retryable transport failure ({exception_name})"
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
        exception_name = _take_transport_marker()
        revised = dict(event) if isinstance(event, dict) else {}
        if exception_name and revised.get("failure_class") == "empty_response":
            revised["failure_class"] = TRANSPORT_FAILURE_CLASS
        original(config, revised)
        if not exception_name or revised.get("failure_class") != TRANSPORT_FAILURE_CLASS:
            return

        # The historical recorder intentionally whitelists fields. Append only
        # the bounded exception class to the event it just wrote; never record
        # exception text or partial response data.
        try:
            history = getattr(config, "_openrouter_request_attempt_telemetry_events", None)
            if not isinstance(history, list) or not history or not isinstance(history[-1], dict):
                return
            updated = [dict(item) if isinstance(item, dict) else item for item in history]
            updated[-1]["exception_type"] = exception_name
            setattr(config, "_openrouter_request_attempt_telemetry_events", updated)
        except Exception:
            note_error = getattr(hardened, "_note_openrouter_telemetry_error", None)
            if callable(note_error):
                note_error(config)

    hardened._record_openrouter_attempt_telemetry = record_openrouter_attempt_telemetry


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    _patch_request_boundary(module)
    _patch_attempt_telemetry(module)
    setattr(module, APPLIED_MARKER, True)
