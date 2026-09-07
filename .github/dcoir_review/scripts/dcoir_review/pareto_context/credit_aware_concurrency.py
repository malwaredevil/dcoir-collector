"""Bounded adaptive concurrency for DCOIR per-file first-pass work.

The scheduler preserves complete first-attempt coverage while avoiding an
unbounded executor queue at a concurrency level that OpenRouter has already
signaled is too aggressive for the account's current in-flight credit window.
It never cancels already-running work and never increases concurrency during a
run. Only the caller-supplied transient-saturation predicate may reduce the
active feed window.
"""

from __future__ import annotations

import concurrent.futures
import threading
from collections import deque
from collections.abc import Callable
from typing import Any


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
        try:
            error = inner.exception()
        except BaseException as exc:  # pragma: no cover - defensive Future seam
            error = exc

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
            return
        if error is not None:
            outer.set_exception(error)
            return
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
