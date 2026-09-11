#!/usr/bin/env python3
"""DCOIR Review v58: bounded retry for interrupted provider transport reads.

Issue #548 proved that a chunked HTTP response can fail inside ``response.read()``
with ``http.client.IncompleteRead``. That exception bypassed the existing
provider retry loop even though the request had remaining attempts. This
post-composition overlay maps only narrowly classified transient transport
failures onto the existing bounded empty-response retry lane, while preserving
the original HTTP-status, JSON/schema, routing, and fail-closed behavior.

The same protection also covers interrupted reads of ``HTTPError`` response
bodies. Retryable HTTP statuses keep their status in attempt telemetry while the
interrupted body is treated as transport failure; non-retryable statuses remain
owned by the historical HTTP-status path.
"""

from __future__ import annotations

import http.client
import io
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
_RETRYABLE_HTTP_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
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


def _set_transport_marker(config: Any, *, http_status: int | None = None) -> None:
    _TRANSPORT_STATE.marker = (
        id(config),
        _request_attempt_count(config),
        http_status if isinstance(http_status, int) and not isinstance(http_status, bool) else None,
    )


def _take_transport_marker(config: Any) -> tuple[bool, int | None]:
    marker = getattr(_TRANSPORT_STATE, "marker", None)
    try:
        delattr(_TRANSPORT_STATE, "marker")
    except AttributeError:
        pass
    if not isinstance(marker, tuple) or len(marker) != 3:
        return False, None
    config_id, attempt_count, http_status = marker
    if config_id != id(config) or attempt_count != _request_attempt_count(config):
        return False, None
    if not isinstance(http_status, int) or isinstance(http_status, bool):
        http_status = None
    return True, http_status


def _replay_http_error(exc: urllib.error.HTTPError, body: bytes) -> urllib.error.HTTPError:
    """Return a readable HTTPError preserving the historical status surface."""

    url = getattr(exc, "url", None)
    if not url:
        try:
            url = exc.geturl()
        except Exception:
            url = ""
    reason = getattr(exc, "reason", None) or str(exc)
    headers = getattr(exc, "headers", None)
    return urllib.error.HTTPError(url, exc.code, reason, headers, io.BytesIO(body))


def _transport_runtime_error(exc: Exception, *, http_status: int | None = None) -> RuntimeError:
    status_note = f"; http_status={http_status}" if http_status is not None else ""
    return RuntimeError(
        "OpenRouter returned an empty response after retryable transport failure "
        f"({type(exc).__name__}{status_note})"
    )


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
        except urllib.error.HTTPError as exc:
            # The historical openrouter_review loop owns HTTP status policy and
            # parses the response body after catching HTTPError. Buffer a readable
            # body here so a transport interruption during that later exc.read()
            # cannot escape the loop. If the body read itself is interrupted, only
            # statuses already retryable without body-derived semantics enter the
            # bounded transport retry lane. Other statuses remain HTTP errors with
            # an empty untrusted body and preserve their original status metadata.
            try:
                body = exc.read()
            except Exception as read_exc:
                if not _is_retryable_transport_exception(read_exc):
                    raise
                status = exc.code if isinstance(exc.code, int) and not isinstance(exc.code, bool) else None
                if status in _RETRYABLE_HTTP_STATUS_CODES:
                    _set_transport_marker(config, http_status=status)
                    raise _transport_runtime_error(read_exc, http_status=status) from read_exc
                raise _replay_http_error(exc, b"") from read_exc
            raise _replay_http_error(exc, body) from exc
        except Exception as exc:
            if not _is_retryable_transport_exception(exc):
                raise
            _set_transport_marker(config)
            # The historical retry loop already retries bounded empty-response
            # RuntimeError failures. Reuse that lane instead of duplicating the
            # model/attempt/backoff policy here. Never inspect or recover
            # IncompleteRead.partial bytes: a partial provider envelope is not
            # trustworthy model output.
            raise _transport_runtime_error(exc) from exc

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
        transport_failure, http_status = _take_transport_marker(config)
        revised = dict(event) if isinstance(event, dict) else {}
        if transport_failure and revised.get("failure_class") == "empty_response":
            revised["failure_class"] = TRANSPORT_FAILURE_CLASS
            if http_status is not None:
                revised["http_status"] = http_status
        original(config, revised)

    hardened._record_openrouter_attempt_telemetry = record_openrouter_attempt_telemetry


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    _patch_request_boundary(module)
    _patch_attempt_telemetry(module)
    setattr(module, APPLIED_MARKER, True)
