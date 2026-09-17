#!/usr/bin/env python3
"""Deterministic ownership/order regressions for canonical provider review."""

from __future__ import annotations

import copy
import importlib
from types import SimpleNamespace

from dcoir_review.entrypoint import DcoirReviewEntrypoint


HISTORICAL_REVIEW_STORAGES = (
    "_dcoir_review_structured_result_provider_prior_openrouter_review",
    "_dcoir_review_v54_original_openrouter_review",
    "_dcoir_review_v57_original_openrouter_review",
)


def assert_production_ownership() -> None:
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    owner = review.hardened.openrouter_review
    assert owner.__module__ == "dcoir_review.provider_review", owner.__module__
    assert getattr(owner, "_dcoir_review_provider_review_owner", False) is True
    for storage in HISTORICAL_REVIEW_STORAGES:
        assert not hasattr(review.hardened, storage), storage


class FakeHardened:
    def __init__(self, events: list[str], provider_error: Exception | None = None) -> None:
        self.events = events
        self.provider_error = provider_error

    def openrouter_review(self, prompt, schema, config, reporter=None):
        self.events.append("provider-call")
        provider_error = self.provider_error
        if provider_error is not None:
            raise provider_error
        return {"summary": "clean", "findings": []}, "model-a", ""


class FakeModule:
    def __init__(self, events: list[str], provider_error: Exception | None = None) -> None:
        self.hardened = FakeHardened(events, provider_error)


def exercise_order(provider_error: Exception | None = None) -> tuple[list[str], object | None]:
    provider_review = importlib.import_module("dcoir_review.provider_review")
    final_policy = provider_review.final_adjudication_policy
    telemetry = provider_review.review_telemetry
    recovery = provider_review.structured_result_provider
    events: list[str] = []
    module = FakeModule(events, provider_error)
    sentinel_state = SimpleNamespace(staged_config=SimpleNamespace())
    originals = (
        final_policy.project_review_call,
        telemetry.prepare_review_call,
        telemetry.finish_review_call,
        recovery.reset_review_recovery,
        recovery.report_review_recovery,
    )

    def project_review_call(_module, prompt, config):
        events.append("final-policy-project")
        return f"projected:{prompt}", copy.copy(config)

    def prepare_review_call(_prompt, _schema, _config):
        events.append("telemetry-prepare")
        return sentinel_state

    def finish_review_call(_state, outcome):
        events.append(f"telemetry-finish-{outcome}")

    def reset_review_recovery(_config):
        return None

    def report_review_recovery(_config, _reporter):
        events.append("structured-recovery-report")

    final_policy.project_review_call = project_review_call
    telemetry.prepare_review_call = prepare_review_call
    telemetry.finish_review_call = finish_review_call
    recovery.reset_review_recovery = reset_review_recovery
    recovery.report_review_recovery = report_review_recovery
    raised: object | None = None
    try:
        provider_review.apply_pareto_context_module(module)
        config = SimpleNamespace()
        try:
            module.hardened.openrouter_review("probe", {}, config, None)
        except Exception as exc:  # exact identity is part of the contract.
            raised = exc
    finally:
        (
            final_policy.project_review_call,
            telemetry.prepare_review_call,
            telemetry.finish_review_call,
            recovery.reset_review_recovery,
            recovery.report_review_recovery,
        ) = originals
    return events, raised


def assert_call_order() -> None:
    events, raised = exercise_order()
    assert raised is None
    assert events == [
        "final-policy-project",
        "telemetry-prepare",
        "provider-call",
        "structured-recovery-report",
        "telemetry-finish-success",
    ], events


def assert_failure_order_and_identity() -> None:
    expected = RuntimeError("synthetic provider failure")
    events, raised = exercise_order(expected)
    assert raised is expected
    assert events == [
        "final-policy-project",
        "telemetry-prepare",
        "provider-call",
        "telemetry-finish-failed",
    ], events


def assert_unexpected_telemetry_finish_is_observational() -> None:
    provider_review = importlib.import_module("dcoir_review.provider_review")
    telemetry = provider_review.review_telemetry
    original_finish = telemetry.finish_review_call
    telemetry_failure = RuntimeError("synthetic telemetry helper failure")

    def broken_finish(_state, _outcome):
        raise telemetry_failure

    telemetry.finish_review_call = broken_finish
    try:
        success_module = FakeModule([])
        provider_review.apply_pareto_context_module(success_module)
        result = success_module.hardened.openrouter_review(
            "probe", {}, SimpleNamespace(), None
        )
        assert result[0]["findings"] == []

        provider_failure = RuntimeError("synthetic provider failure")
        failed_module = FakeModule([], provider_failure)
        provider_review.apply_pareto_context_module(failed_module)
        try:
            failed_module.hardened.openrouter_review(
                "probe", {}, SimpleNamespace(), None
            )
        except RuntimeError as exc:
            assert exc is provider_failure
        else:
            raise AssertionError("telemetry helper failure masked provider failure")
    finally:
        telemetry.finish_review_call = original_finish

def main() -> None:
    assert_production_ownership()
    assert_call_order()
    assert_failure_order_and_identity()
    assert_unexpected_telemetry_finish_is_observational()
    print("dcoir_review_provider_review_selftest passed")


if __name__ == "__main__":
    main()
