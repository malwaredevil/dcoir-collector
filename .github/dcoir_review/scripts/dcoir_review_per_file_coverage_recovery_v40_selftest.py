#!/usr/bin/env python3
"""Regression checks for DCOIR per-file coverage recovery hardening (v40)."""

from __future__ import annotations

import importlib
import threading
from pathlib import Path
from types import SimpleNamespace


def main() -> None:
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    config = review.load_pareto_context_config(
        ".github/dcoir_review/openrouter-pr-review-pareto.yml"
    )
    assert config.debug is False
    assert int(config.per_file_review_concurrency) >= 2

    transient = RuntimeError(
        "review provider API failed with HTTP 402: This request would exceed your "
        "available credits given your current in-flight requests. Retry after "
        "in-flight requests settle, or add credits. Provider skipped for retry: none."
    )
    permanent = RuntimeError(
        "review provider API failed with HTTP 402: Insufficient credits. Add credits to continue."
    )
    assert review._is_transient_inflight_credit_saturation_error(transient)
    assert not review._is_transient_inflight_credit_saturation_error(permanent)
    assert not review._is_transient_inflight_credit_saturation_error(
        RuntimeError("review provider API failed with HTTP 429: rate limited")
    )

    original = {
        "build_file_contexts": review.build_file_contexts,
        "review_single_file_context": review.review_single_file_context,
        "merge_many_review_results": review.merge_many_review_results,
        "compact_model_label": review.compact_model_label,
        "write_debug_text": review.hardened.write_debug_text_artifact_safely,
        "write_debug_json": review.hardened.write_debug_json_artifact_safely,
        "retry_reason": review.hardened.review_quality_retry_reason,
    }

    class Reporter:
        def __init__(self):
            self.events = []

        def update(self, stage, message):
            self.events.append((stage, message))

    captured_json = {}
    review.hardened.write_debug_text_artifact_safely = lambda *args, **kwargs: None
    review.hardened.write_debug_json_artifact_safely = (
        lambda cfg, path, value: captured_json.__setitem__(path, value)
    )
    review.hardened.review_quality_retry_reason = lambda *args, **kwargs: None
    review.merge_many_review_results = lambda items: {
        "findings": [
            finding
            for item in items
            for finding in item.get("findings", [])
        ],
        "summary": "coverage probe",
    }
    review.compact_model_label = lambda results, model: model

    contexts = [{"path": "a.py"}, {"path": "b.py"}, {"path": "c.py"}]
    review.build_file_contexts = lambda *args, **kwargs: list(contexts)
    lock = threading.Lock()
    primary_calls = 0
    calls = {item["path"]: 0 for item in contexts}

    def review_single_file_context(index, context, *args, **kwargs):
        nonlocal primary_calls
        path = str(context["path"])
        with lock:
            calls[path] += 1
            attempt = calls[path]
            if attempt == 1:
                primary_calls += 1
            observed_primary_calls = primary_calls

        if path == "b.py" and attempt == 1:
            raise transient
        if path == "b.py" and attempt == 2:
            assert observed_primary_calls == len(contexts), (
                "saturation recovery started before the parallel wave settled"
            )
        return {
            "result": {"findings": [{"path": path}]},
            "service_tier": "test-tier",
            "prompt_chars": 10,
        }

    review.review_single_file_context = review_single_file_context
    reporter = Reporter()
    probe_config = SimpleNamespace(per_file_review_concurrency=3, model="test-model")

    try:
        result, model, tier = review.openrouter_review_with_hybrid_first_pass(
            {},
            [],
            "",
            {},
            probe_config,
            reporter,
            [],
            {},
            "",
            "deep-forced",
            "",
            object(),
        )
        assert calls == {"a.py": 1, "b.py": 2, "c.py": 1}
        assert model == "test-model"
        assert tier == "test-tier"
        assert len(result["findings"]) == 3
        recovery = captured_json["responses/per-file/saturation-recovery.json"]
        assert recovery == {
            "transient_saturation_file_count": 1,
            "low_concurrency_recovered_file_count": 1,
            "serial_recovered_saturation_file_count": 0,
            "recovered_saturation_file_count": 1,
            "unrecovered_saturation_file_count": 0,
        }
        metadata = captured_json["metadata/01-initial-request.json"]
        assert metadata["completed_file_prompt_count"] == 3
        assert metadata["failed_file_count"] == 0
        assert any(
            stage == "per-file-recovery" and "b.py: recovered at low concurrency" in message
            for stage, message in reporter.events
        )

        # A file that is still saturated in the bounded low-concurrency wave gets
        # exactly one final serial attempt after that wave has fully settled.
        captured_json.clear()
        calls_serial = {"serial.py": 0}
        review.build_file_contexts = lambda *args, **kwargs: [{"path": "serial.py"}]

        def review_serial_recovery(index, context, *args, **kwargs):
            calls_serial["serial.py"] += 1
            if calls_serial["serial.py"] < 3:
                raise transient
            return {
                "result": {"findings": [{"path": "serial.py"}]},
                "service_tier": "test-tier",
                "prompt_chars": 10,
            }

        review.review_single_file_context = review_serial_recovery
        serial_reporter = Reporter()
        serial_result, _, _ = review.openrouter_review_with_hybrid_first_pass(
            {}, [], "", {}, probe_config, serial_reporter, [], {}, "", "deep-forced", "", object()
        )
        assert calls_serial["serial.py"] == 3
        assert len(serial_result["findings"]) == 1
        serial_recovery = captured_json["responses/per-file/saturation-recovery.json"]
        assert serial_recovery["low_concurrency_recovered_file_count"] == 0
        assert serial_recovery["serial_recovered_saturation_file_count"] == 1
        assert serial_recovery["unrecovered_saturation_file_count"] == 0
        assert any(
            stage == "per-file-recovery" and "serial.py: recovered serially" in message
            for stage, message in serial_reporter.events
        )

        # Permanent-credit 402 is materially different from transient in-flight
        # saturation and must remain fail-closed rather than being retried.
        review.build_file_contexts = lambda *args, **kwargs: [{"path": "permanent.py"}]
        review.review_single_file_context = lambda *args, **kwargs: (_ for _ in ()).throw(permanent)
        try:
            review.openrouter_review_with_hybrid_first_pass(
                {}, [], "", {}, probe_config, Reporter(), [], {}, "", "deep-forced", "", object()
            )
        except review.hardened.ReviewQualityError as exc:
            assert "coverage incomplete" in str(exc).lower()
        else:
            raise AssertionError("permanent-credit HTTP 402 did not fail closed")

        # Unrelated failures also remain fail-closed; v40 is not a generic retry
        # escape hatch for arbitrary provider or reviewer errors.
        review.build_file_contexts = lambda *args, **kwargs: [{"path": "other.py"}]
        review.review_single_file_context = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("unrelated provider failure")
        )
        try:
            review.openrouter_review_with_hybrid_first_pass(
                {}, [], "", {}, probe_config, Reporter(), [], {}, "", "deep-forced", "", object()
            )
        except review.hardened.ReviewQualityError as exc:
            assert "coverage incomplete" in str(exc).lower()
        else:
            raise AssertionError("unrelated per-file failure did not fail closed")
    finally:
        review.build_file_contexts = original["build_file_contexts"]
        review.review_single_file_context = original["review_single_file_context"]
        review.merge_many_review_results = original["merge_many_review_results"]
        review.compact_model_label = original["compact_model_label"]
        review.hardened.write_debug_text_artifact_safely = original["write_debug_text"]
        review.hardened.write_debug_json_artifact_safely = original["write_debug_json"]
        review.hardened.review_quality_retry_reason = original["retry_reason"]

    source = Path(
        ".github/dcoir_review/scripts/dcoir_review/pareto_context/part_05a_hybrid_review.py"
    ).read_text(encoding="utf-8")
    assert "queued for bounded recovery" in source
    assert "Per-file first-pass coverage incomplete after bounded recovery" in source
    for forbidden in ("git push", "create_commit(", "update_file(", "merge_pull_request"):
        assert forbidden not in source

    print("dcoir_review_per_file_coverage_recovery_v40_selftest passed")


if __name__ == "__main__":
    main()
