"""Bounded adaptive concurrency for DCOIR per-file first-pass work.

The scheduler preserves complete first-attempt coverage while avoiding an
unbounded executor queue at a concurrency level that OpenRouter has already
signaled is too aggressive for the current in-flight credit window. It never
cancels already-running work and never increases concurrency during a run.
Only the caller-supplied transient-saturation predicate may reduce the active
feed window.
"""

from __future__ import annotations

import concurrent.futures
import threading
from collections import deque
from collections.abc import Callable
from typing import Any


Task = tuple[int, dict[str, Any]]
SaturationFailure = tuple[int, dict[str, Any], str]


class CreditAwareThreadPoolExecutor:
    """Thread-pool facade that can reduce its active feed window on saturation."""

    def __init__(
        self,
        max_workers: int,
        *,
        adaptive: bool,
        is_saturation_error: Callable[[Exception], bool],
    ) -> None:
        initial = max(1, int(max_workers))
        self._inner = concurrent.futures.ThreadPoolExecutor(max_workers=initial)
        self._adaptive = bool(adaptive)
        self._is_saturation_error = is_saturation_error
        self._lock = threading.RLock()
        self._pending: deque[
            tuple[concurrent.futures.Future[Any], Callable[..., Any], tuple[Any, ...], dict[str, Any]]
        ] = deque()
        self._active: dict[concurrent.futures.Future[Any], concurrent.futures.Future[Any]] = {}
        self._initial_limit = initial
        self._current_limit = initial
        self._minimum_limit = initial
        self._reduction_count = 0
        self._saturation_event_count = 0
        self._shutdown = False

    def __enter__(self) -> "CreditAwareThreadPoolExecutor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.shutdown(wait=True)

    def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> concurrent.futures.Future[Any]:
        outer: concurrent.futures.Future[Any] = concurrent.futures.Future()
        with self._lock:
            if self._shutdown:
                raise RuntimeError("cannot schedule new futures after shutdown")
            self._pending.append((outer, fn, args, kwargs))
            self._dispatch_locked()
        return outer

    def _dispatch_locked(self) -> None:
        while self._pending and len(self._active) < self._current_limit:
            outer, fn, args, kwargs = self._pending.popleft()
            inner = self._inner.submit(fn, *args, **kwargs)
            self._active[inner] = outer
            inner.add_done_callback(self._on_done)

    def _on_done(self, inner: concurrent.futures.Future[Any]) -> None:
        error = inner.exception()

        with self._lock:
            outer = self._active.pop(inner)
            if isinstance(error, Exception) and self._is_saturation_error(error):
                self._saturation_event_count += 1
                if self._adaptive and self._current_limit > 1:
                    self._current_limit = max(1, self._current_limit // 2)
                    self._minimum_limit = min(self._minimum_limit, self._current_limit)
                    self._reduction_count += 1
            self._dispatch_locked()

        if inner.cancelled():
            outer.cancel()
        elif error is not None:
            outer.set_exception(error)
        else:
            outer.set_result(inner.result())

    def shutdown(self, wait: bool = True) -> None:
        with self._lock:
            self._shutdown = True
        self._inner.shutdown(wait=wait)

    def telemetry(self) -> dict[str, Any]:
        with self._lock:
            return {
                "adaptive_enabled": self._adaptive,
                "initial_primary_concurrency": self._initial_limit,
                "minimum_primary_concurrency": self._minimum_limit,
                "final_primary_concurrency": self._current_limit,
                "primary_concurrency_reduction_count": self._reduction_count,
                "primary_saturation_event_count": self._saturation_event_count,
            }


def _path(context: dict[str, Any]) -> str:
    return str(context.get("path", "") or "")


def run_credit_aware_primary_wave(
    contexts: list[dict[str, Any]],
    worker: Callable[[int, dict[str, Any]], dict[str, Any]],
    *,
    configured_concurrency: int,
    adaptive: bool,
    is_saturation_error: Callable[[Exception], bool],
    reporter: Any,
    hardened: Any,
    config: Any,
    safe_artifact_name: Callable[[str, str], str],
) -> dict[str, Any]:
    """Run every first attempt while reducing future feed rate after saturation."""

    executor = CreditAwareThreadPoolExecutor(
        max_workers=min(max(1, int(configured_concurrency)), len(contexts)),
        adaptive=adaptive,
        is_saturation_error=is_saturation_error,
    )
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    saturation_failures: list[SaturationFailure] = []

    with executor:
        future_map = {
            executor.submit(worker, index, context): (index, context)
            for index, context in enumerate(contexts, start=1)
        }
        for future in concurrent.futures.as_completed(future_map):
            index, context = future_map[future]
            path = _path(context)
            try:
                results.append(future.result())
                reporter.update("per-file-result", f"{path}: completed")
            except Exception as exc:
                if is_saturation_error(exc):
                    saturation_failures.append((index, context, str(exc)))
                    hardened.write_debug_json_artifact_safely(
                        config,
                        f"responses/per-file/{index:02d}-{safe_artifact_name(path, f'file-{index:02d}')}-transient-saturation.json",
                        {"path": path, "error": str(exc), "recovery": "queued-for-low-concurrency-retry"},
                    )
                    reporter.update(
                        "per-file-result",
                        f"{path}: transient in-flight-credit saturation; queued for bounded recovery",
                    )
                else:
                    failures.append(f"{path}: {str(exc)[:240]}")
                    hardened.write_debug_json_artifact_safely(
                        config,
                        f"responses/per-file/{index:02d}-{safe_artifact_name(path, f'file-{index:02d}')}-error.json",
                        {"path": path, "error": str(exc)},
                    )
                    reporter.update(
                        "per-file-result",
                        f"{path}: failed; coverage will fail closed after remaining files complete",
                    )

    telemetry = executor.telemetry()
    telemetry["configured_primary_concurrency"] = max(1, int(configured_concurrency))
    if int(telemetry["primary_concurrency_reduction_count"]) > 0:
        reporter.update(
            "per-file-concurrency",
            (
                "transient in-flight-credit saturation reduced the primary feed window "
                f"from {telemetry['initial_primary_concurrency']} to {telemetry['final_primary_concurrency']}"
            ),
        )
    return {
        "results": results,
        "failures": failures,
        "saturation_failures": saturation_failures,
        "telemetry": telemetry,
    }


def run_bounded_saturation_recovery(
    saturation_failures: list[SaturationFailure],
    worker: Callable[[int, dict[str, Any]], dict[str, Any]],
    *,
    recovery_concurrency: int,
    is_saturation_error: Callable[[Exception], bool],
    reporter: Any,
    hardened: Any,
    config: Any,
    safe_artifact_name: Callable[[str, str], str],
) -> dict[str, Any]:
    """Retain v40 low-concurrency then one-final-serial recovery semantics."""

    if not saturation_failures:
        return {
            "results": [],
            "failures": [],
            "low_concurrency_recovered_file_count": 0,
            "serial_recovered_saturation_file_count": 0,
        }

    recovery_workers = max(1, min(int(recovery_concurrency), len(saturation_failures)))
    reporter.update(
        "per-file-recovery",
        (
            f"parallel wave settled; retrying {len(saturation_failures)} transient in-flight-credit "
            f"saturation failure(s) with recovery concurrency={recovery_workers}"
        ),
    )
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    serial_saturation_failures: list[SaturationFailure] = []
    low_recovered = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=recovery_workers) as recovery_executor:
        future_map = {
            recovery_executor.submit(worker, index, context): (index, context, initial_error)
            for index, context, initial_error in saturation_failures
        }
        for future in concurrent.futures.as_completed(future_map):
            index, context, initial_error = future_map[future]
            path = _path(context)
            try:
                results.append(future.result())
                low_recovered += 1
                reporter.update("per-file-recovery", f"{path}: recovered at low concurrency")
            except Exception as exc:
                if is_saturation_error(exc):
                    serial_saturation_failures.append((index, context, str(exc)))
                    reporter.update(
                        "per-file-recovery",
                        f"{path}: still saturated; queued for one final serial recovery attempt",
                    )
                else:
                    failures.append(f"{path}: {str(exc)[:240]}")
                    hardened.write_debug_json_artifact_safely(
                        config,
                        f"responses/per-file/{index:02d}-{safe_artifact_name(path, f'file-{index:02d}')}-error.json",
                        {
                            "path": path,
                            "initial_error": initial_error,
                            "recovery_error": str(exc),
                            "recovery": "low-concurrency-retry-failed",
                        },
                    )
                    reporter.update("per-file-recovery", f"{path}: low-concurrency recovery failed")

    serial_recovered = 0
    if serial_saturation_failures:
        reporter.update(
            "per-file-recovery",
            (
                "low-concurrency recovery wave settled; serially retrying "
                f"{len(serial_saturation_failures)} still-saturated file(s) once"
            ),
        )
        for index, context, recovery_error in serial_saturation_failures:
            path = _path(context)
            try:
                results.append(worker(index, context))
                serial_recovered += 1
                reporter.update("per-file-recovery", f"{path}: recovered serially")
            except Exception as exc:
                failures.append(f"{path}: {str(exc)[:240]}")
                hardened.write_debug_json_artifact_safely(
                    config,
                    f"responses/per-file/{index:02d}-{safe_artifact_name(path, f'file-{index:02d}')}-error.json",
                    {
                        "path": path,
                        "initial_error": recovery_error,
                        "recovery_error": str(exc),
                        "recovery": "final-serial-retry-failed",
                    },
                )
                reporter.update("per-file-recovery", f"{path}: final serial recovery failed")

    return {
        "results": results,
        "failures": failures,
        "low_concurrency_recovered_file_count": low_recovered,
        "serial_recovered_saturation_file_count": serial_recovered,
    }
