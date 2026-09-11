#!/usr/bin/env python3
"""DCOIR Review v58: bounded retry for interrupted provider transport reads.

Issue #548 proved that a chunked HTTP response can fail inside ``response.read()``
with ``http.client.IncompleteRead``. That exception bypassed the existing
provider retry loop even though the request had remaining attempts. This
post-composition overlay maps only narrowly classified transient transport
failures onto the existing bounded retry machinery, while preserving the
original HTTP-status, JSON/schema, routing, and fail-closed behavior.

The same protection covers interrupted reads of ``HTTPError`` response bodies.
Those failures are replayed through the historical HTTP-status path so that
status-specific retry/backoff/fallback policy remains authoritative, while
telemetry still records the attempt as a transport failure with its HTTP status.
An explicit body-interruption signal lets the status policy retry an ambiguous
402 without inspecting partial bytes to distinguish in-flight from depleted credits.
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
_TRANSPORT_STATE = threading.local()


def _is_retryable_transport_exception(
    exc: Exception,
    *,
    review_timeout_error: type[BaseException] | None = None,
) -> bool:
    """Return whether *exc* is an explicitly retryable transport failure.

    HTTP status failures stay owned by the existing ``HTTPError`` branch. Broad
    ``http.client.HTTPException`` subclasses are intentionally not accepted:
    invalid URL, client-state, unsupported-protocol, and similar local failures
    are not transient response-read interruptions. TLS certificate verification
    failures are also intentionally excluded.
    """

    if review_timeout_error is not None and isinstance(exc, review_timeout_error):
        return False
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
        if review_timeout_error is not None and isinstance(reason, review_timeout_error):
            return False
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
    # Keep an identity-bearing reference until telemetry consumes the marker.
    # This prevents stale state from matching a later object after Python reuses
    # an object id.
    _TRANSPORT_STATE.marker = (
        config,
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
    marker_config, attempt_count, http_status = marker
    if marker_config is not config or attempt_count != _request_attempt_count(config):
        return False, None
    if not isinstance(http_status, int) or isinstance(http_status, bool):
        http_status = None
    return True, http_status


def _replay_http_error(exc: urllib.error.HTTPError, body: bytes) -> urllib.error.HTTPError:
    """Return a readable HTTPError preserving status, reason, and headers."""

    url = getattr(exc, "url", None)
    if not url:
        try:
            url = exc.geturl()
        except Exception:
            url = ""
    reason = getattr(exc, "reason", None) or str(exc)
    headers = getattr(exc, "headers", None)
    return urllib.error.HTTPError(url, exc.code, reason, headers, io.BytesIO(body))


def _safe_close_http_error(
    exc: urllib.error.HTTPError,
    *,
    review_timeout_error: type[BaseException] | None = None,
) -> None:
    """Close the original response without swallowing the runtime watchdog."""

    try:
        exc.close()
    except Exception as close_exc:
        if review_timeout_error is not None and isinstance(close_exc, review_timeout_error):
            raise


def _transport_runtime_error(exc: Exception) -> RuntimeError:
    return RuntimeError(
        "OpenRouter returned an empty response after retryable transport failure "
        f"({type(exc).__name__})"
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

    review_timeout_error = getattr(hardened, "ReviewTimeoutError", None)
    if not isinstance(review_timeout_error, type) or not issubclass(
        review_timeout_error, BaseException
    ):
        review_timeout_error = None

    def openrouter_request_once(prompt, schema, config, ignored_providers, model):
        try:
            return original(prompt, schema, config, ignored_providers, model)
        except urllib.error.HTTPError as exc:
            # The historical openrouter_review loop owns HTTP-status retry,
            # Retry-After, provider-skip, fallback, and terminal policy. Buffer
            # the error body here because that loop reads it after catching the
            # HTTPError. If the body read itself is interrupted, discard partial
            # bytes, mark the attempt as transport-failed, and replay the same
            # HTTPError with an empty readable body. The historical status path
            # then decides whether to retry or fall back. Preserve an explicit
            # interruption signal for statuses whose retry decision needs a body.
            try:
                body = exc.read()
            except Exception as read_exc:
                if not _is_retryable_transport_exception(
                    read_exc, review_timeout_error=review_timeout_error
                ):
                    raise
                status = exc.code if isinstance(exc.code, int) and not isinstance(exc.code, bool) else None
                replay = _replay_http_error(exc, b"")
                replay._dcoir_transport_body_interrupted = True
                _safe_close_http_error(
                    exc, review_timeout_error=review_timeout_error
                )
                _set_transport_marker(config, http_status=status)
                raise replay from read_exc
            raise _replay_http_error(exc, body) from exc
        except Exception as exc:
            if not _is_retryable_transport_exception(
                exc, review_timeout_error=review_timeout_error
            ):
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
        if transport_failure and revised.get("failure_class") in {"empty_response", "http_error"}:
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
