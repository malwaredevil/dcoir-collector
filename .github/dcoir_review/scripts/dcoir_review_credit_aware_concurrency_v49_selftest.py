#!/usr/bin/env python3
"""Deterministic checks for #457 credit-aware per-file concurrency."""

from __future__ import annotations

import concurrent.futures
import threading
from pathlib import Path

from dcoir_review.pareto_context.credit_aware_concurrency import (
    CreditAwareThreadPoolExecutor,
    run_bounded_saturation_recovery,
    run_credit_aware_primary_wave,
)


SYNC_TIMEOUT_SECONDS = 30

TRANSIENT = RuntimeError(
    "review provider API failed with HTTP 402: This request would exceed your available credits "
    "given your current in-flight requests. Retry after in-flight requests settle, or add credits."
)
PERMANENT = RuntimeError(
    "review provider API failed with HTTP 402: Insufficient credits. Add credits to continue."
)


def is_saturation_error(exc: Exception) -> bool:
    message = " ".join(str(exc).lower().split())
    return (
        "http 402" in message
        and "current in-flight requests" in message
        and "retry after in-flight requests settle" in message
    )


class FakeHardened:
    artifacts: dict[str, object] = {}

    @classmethod
    def write_debug_json_artifact_safely(cls, _config, path, value):
        cls.artifacts[path] = value


class Reporter:
    def __init__(self, release_initial: threading.Event | None = None):
        self.events: list[tuple[str, str]] = []
        self.release_initial = release_initial

    def update(self, stage: str, message: str) -> None:
        self.events.append((stage, message))
        if self.release_initial and "queued for bounded recovery" in message:
            self.release_initial.set()


def safe_artifact_name(path: str, fallback: str) -> str:
    return path.replace("/", "-") or fallback


def test_primary_wave_reduces_future_feed() -> None:
    contexts = [{"path": f"{name}.py"} for name in "abcdef"]
    initial_barrier = threading.Barrier(4)
    release_initial = threading.Event()
    lock = threading.Lock()
    attempts = {item["path"]: 0 for item in contexts}
    initial_completed = 0
    late_start_completed_counts: list[int] = []

    def worker(index, context):
        nonlocal initial_completed
        path = str(context["path"])
        with lock:
            attempts[path] += 1
            attempt = attempts[path]
        if attempt == 1 and path in {"a.py", "b.py", "c.py", "d.py"}:
            initial_barrier.wait(timeout=SYNC_TIMEOUT_SECONDS)
            if path == "a.py":
                raise TRANSIENT
            release_initial.wait(timeout=SYNC_TIMEOUT_SECONDS)
            with lock:
                initial_completed += 1
        elif attempt == 1 and path in {"e.py", "f.py"}:
            with lock:
                late_start_completed_counts.append(initial_completed)
        return {
            "result": {"findings": [{"path": path}]},
            "service_tier": "test",
            "prompt_chars": 10,
        }

    reporter = Reporter(release_initial)
    FakeHardened.artifacts.clear()
    primary = run_credit_aware_primary_wave(
        contexts,
        worker,
        configured_concurrency=4,
        adaptive=True,
        is_saturation_error=is_saturation_error,
        reporter=reporter,
        hardened=FakeHardened,
        config=object(),
        safe_artifact_name=safe_artifact_name,
    )
    telemetry = primary["telemetry"]
    assert len(primary["results"]) == 5
    assert len(primary["saturation_failures"]) == 1
    assert primary["failures"] == []
    assert telemetry["initial_primary_concurrency"] == 4
    assert telemetry["final_primary_concurrency"] == 2
    assert telemetry["minimum_primary_concurrency"] == 2
    assert telemetry["primary_concurrency_reduction_count"] == 1
    assert telemetry["primary_saturation_event_count"] == 1
    assert late_start_completed_counts and min(late_start_completed_counts) >= 2, (
        "new work was fed at the old four-way rate after saturation was observed"
    )
    assert attempts["a.py"] == 1
    assert all(attempts[f"{name}.py"] == 1 for name in "bcdef")

    recovery = run_bounded_saturation_recovery(
        primary["saturation_failures"],
        worker,
        recovery_concurrency=min(2, int(telemetry["final_primary_concurrency"])),
        is_saturation_error=is_saturation_error,
        reporter=reporter,
        hardened=FakeHardened,
        config=object(),
        safe_artifact_name=safe_artifact_name,
    )
    assert len(recovery["results"]) == 1
    assert recovery["failures"] == []
    assert recovery["low_concurrency_recovered_file_count"] == 1
    assert recovery["serial_recovered_saturation_file_count"] == 0
    assert attempts["a.py"] == 2


def test_repeated_saturation_can_reduce_to_serial() -> None:
    barrier = threading.Barrier(4)

    def worker(name: str) -> str:
        if name in {"a", "b", "c", "d"}:
            barrier.wait(timeout=SYNC_TIMEOUT_SECONDS)
        if name in {"a", "b"}:
            raise TRANSIENT
        return name

    executor = CreditAwareThreadPoolExecutor(
        4,
        adaptive=True,
        is_saturation_error=is_saturation_error,
    )
    with executor:
        futures = [executor.submit(worker, name) for name in "abcdefgh"]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except RuntimeError as exc:
                assert is_saturation_error(exc)
    telemetry = executor.telemetry()
    assert telemetry["primary_saturation_event_count"] == 2
    assert telemetry["primary_concurrency_reduction_count"] == 2
    assert telemetry["final_primary_concurrency"] == 1
    assert telemetry["minimum_primary_concurrency"] == 1


def test_cancelled_inner_future_cancels_outer_future() -> None:
    executor = CreditAwareThreadPoolExecutor(
        1,
        adaptive=True,
        is_saturation_error=is_saturation_error,
    )
    with executor:
        outer = concurrent.futures.Future()
        inner = concurrent.futures.Future()
        executor._active[inner] = outer
        assert inner.cancel()
        executor._on_done(inner)
        assert outer.cancelled()
    assert executor.telemetry()["final_primary_concurrency"] == 1


def test_non_transient_and_disabled_behavior() -> None:
    executor = CreditAwareThreadPoolExecutor(
        2,
        adaptive=True,
        is_saturation_error=is_saturation_error,
    )
    with executor:
        failed = executor.submit(lambda: (_ for _ in ()).throw(PERMANENT))
        passed = executor.submit(lambda: "ok")
        try:
            failed.result(timeout=5)
        except RuntimeError as exc:
            assert "Insufficient credits" in str(exc)
        else:
            raise AssertionError("permanent-credit error unexpectedly succeeded")
        assert passed.result(timeout=5) == "ok"
    telemetry = executor.telemetry()
    assert telemetry["primary_saturation_event_count"] == 0
    assert telemetry["primary_concurrency_reduction_count"] == 0
    assert telemetry["final_primary_concurrency"] == 2

    disabled = CreditAwareThreadPoolExecutor(
        2,
        adaptive=False,
        is_saturation_error=is_saturation_error,
    )
    with disabled:
        failed = disabled.submit(lambda: (_ for _ in ()).throw(TRANSIENT))
        passed = disabled.submit(lambda: "ok")
        try:
            failed.result(timeout=5)
        except RuntimeError as exc:
            assert is_saturation_error(exc)
        else:
            raise AssertionError("transient saturation unexpectedly succeeded")
        assert passed.result(timeout=5) == "ok"
    telemetry = disabled.telemetry()
    assert telemetry["primary_saturation_event_count"] == 1
    assert telemetry["primary_concurrency_reduction_count"] == 0
    assert telemetry["final_primary_concurrency"] == 2


def test_source_boundaries() -> None:
    root = Path(".github/dcoir_review/scripts")
    helper = root / "dcoir_review/pareto_context/credit_aware_concurrency.py"
    hybrid = root / "dcoir_review/pareto_context/part_05a_hybrid_review.py"
    assert helper.stat().st_size < 15000
    assert hybrid.stat().st_size < 15000
    helper_source = helper.read_text(encoding="utf-8")
    hybrid_source = hybrid.read_text(encoding="utf-8")
    assert "CreditAwareThreadPoolExecutor" in helper_source
    assert "run_credit_aware_primary_wave" in hybrid_source
    assert "credit-aware-concurrency.json" in hybrid_source
    for forbidden in ("git push", "create_commit(", "update_file(", "merge_pull_request"):
        assert forbidden not in helper_source
        assert forbidden not in hybrid_source


def main() -> None:
    assert is_saturation_error(TRANSIENT)
    assert not is_saturation_error(PERMANENT)
    test_primary_wave_reduces_future_feed()
    test_repeated_saturation_can_reduce_to_serial()
    test_non_transient_and_disabled_behavior()
    test_source_boundaries()
    print("dcoir_review_credit_aware_concurrency_v49_selftest passed")


if __name__ == "__main__":
    main()
