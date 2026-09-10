#!/usr/bin/env python3
"""Deterministic regression checks for DCOIR Review v54 run telemetry."""

from __future__ import annotations

import copy
import importlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from dcoir_review.entrypoint import DcoirReviewEntrypoint


class FakeResponse:
    def __init__(self, value) -> None:
        self._raw = json.dumps(value).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._raw


class FakeProgressReporter:
    def __init__(self, _gh, _issue_number, _command, config) -> None:
        self.config = config
        self.updates: list[tuple[str, str]] = []
        self.completed = False
        self.failed = False

    def update(self, stage: str, message: str) -> None:
        self.updates.append((stage, message))

    def complete(self, _model_used: str, _findings_count: int, _review_event: str) -> None:
        self.completed = True

    def fail(self, _message: str) -> None:
        self.failed = True


class FakeHardened:
    ProgressReporter = FakeProgressReporter

    def openrouter_review(self, prompt, schema, config, reporter=None):
        # v54 must not mutate routing/model semantics; it should only give the
        # provider path a shallow capture-enabled projection.
        assert getattr(config, "openrouter_capture_request_telemetry", False) is True
        assert config.model == "model-a"
        assert config.model_stack == ["model-a", "model-b"]
        assert config.openrouter_provider_sort == "price"
        assert config.review_reasoning_effort == "high"

        text = str(prompt)
        if "fail-call" in text:
            config._openrouter_request_attempt_count = 2
            config._openrouter_request_telemetry_events = []
            raise RuntimeError("synthetic transport failure")

        config._openrouter_request_attempt_count = 2 if "retry-call" in text else 1
        raw = {
            "requested_model": "model-a",
            "served_model": "model-a",
            "served_model_differs_from_requested": False,
            "provider": "Provider A",
            "service_tier": "",
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_tokens_details": {
                    "cached_tokens": 40,
                    "cache_write_tokens": 5,
                },
                "completion_tokens_details": {"reasoning_tokens": 7},
                "cost": 0.0125,
            },
            "cost": 0.0125,
            "request_attempt_count": config._openrouter_request_attempt_count,
            "response_healing_observed": True,
            "structured_output_recovery": "balanced-envelope",
            # These values deliberately must not survive normalization.
            "prompt": "SECRET_PROMPT_MUST_NOT_SURVIVE",
            "raw_response": "SECRET_RESPONSE_MUST_NOT_SURVIVE",
            "authorization": "Bearer SECRET_TOKEN_MUST_NOT_SURVIVE",
        }
        config._openrouter_request_telemetry_events = [raw]
        config._openrouter_last_request_telemetry = {
            **raw,
            "request_events": [dict(raw)],
            "aggregate_cost": 0.0125,
        }
        return {"summary": "clean", "findings": []}, "model-a", ""


class FakeModule:
    def __init__(self) -> None:
        self.hardened = FakeHardened()
        self.base = SimpleNamespace(emit_status=lambda *_args: None)
        self.load_pareto_context_config = lambda _path: SimpleNamespace(
            model="model-a",
            model_stack=["model-a", "model-b"],
            openrouter_provider_sort="price",
            review_reasoning_effort="high",
            debug=False,
            post_progress_comment=False,
        )


def review_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "findings": {"type": "array"},
        },
    }


def repair_author_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["repair_set", "no_safe_repair"]},
            "edits": {"type": "array"},
        },
    }


def verifier_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "supported": {"type": "boolean"},
            "confidence": {"type": "number"},
            "reason": {"type": "string"},
        },
    }


def critic_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "accepted": {"type": "boolean"},
            "confidence": {"type": "number"},
            "reason": {"type": "string"},
        },
    }


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.execution_policy_patch_module_names[-1] == "dcoir_review_required_runtime_patch_v53"
    assert entrypoint.telemetry_patch_module_names == (
        "dcoir_review_required_runtime_patch_v54",
    )

    v54 = importlib.import_module("dcoir_review_required_runtime_patch_v54")

    # Production composition applies v54 after the existing execution-policy
    # chain without redefining the older ordering contract.
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    assert getattr(review, v54.APPLIED_MARKER, False) is True
    production_config = review.load_pareto_context_config(
        ".github/dcoir_review/openrouter-pr-review-pareto.yml"
    )
    assert production_config.debug is False
    assert isinstance(getattr(production_config, v54.SINK_ATTR, None), v54.RunTelemetrySink)

    # Capture-only telemetry must be observational. It must not select v47's
    # stricter stop/object response-enforcement branch for ordinary premium
    # stages. The same response therefore parses the same with capture off/on,
    # and an empty choices list retains the historical IndexError in both modes.
    original_urlopen = review.hardened.urllib.request.urlopen
    previous_key = os.environ.get("OPENROUTER_API_KEY")
    os.environ["OPENROUTER_API_KEY"] = "v54-selftest-key"

    def install_response(value) -> None:
        review.hardened.urllib.request.urlopen = lambda _req, timeout=180: FakeResponse(value)

    try:
        valid_payload = {
            "model": "anthropic/claude-opus-5",
            "provider": "Anthropic",
            "service_tier": "",
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {"content": json.dumps({"summary": "clean", "findings": []})},
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 4,
                "total_tokens": 16,
                "prompt_tokens_details": {"cached_tokens": 3},
                "completion_tokens_details": {"reasoning_tokens": 2},
                "cost": 0.004,
            },
        }
        uncaptured = copy.copy(production_config)
        uncaptured.openrouter_capture_request_telemetry = False
        install_response(valid_payload)
        plain_result = review.hardened.openrouter_request_once(
            "probe", review_schema(), uncaptured, [], "anthropic/claude-opus-5"
        )

        captured = copy.copy(production_config)
        captured.openrouter_capture_request_telemetry = True
        install_response(valid_payload)
        captured_result = review.hardened.openrouter_request_once(
            "probe", review_schema(), captured, [], "anthropic/claude-opus-5"
        )
        assert captured_result == plain_result
        assert captured._openrouter_last_request_telemetry["finish_reason"] == "length"
        assert captured._openrouter_last_request_telemetry["usage"]["prompt_tokens"] == 12
        assert captured._openrouter_last_request_telemetry["cost"] == 0.004

        empty_choices = {
            "model": "anthropic/claude-opus-5",
            "provider": "Anthropic",
            "choices": [],
            "usage": {"prompt_tokens": 2, "completion_tokens": 0, "cost": 0.001},
        }
        failures: list[type[BaseException]] = []
        for capture in (False, True):
            compatibility = copy.copy(production_config)
            compatibility.openrouter_capture_request_telemetry = capture
            install_response(empty_choices)
            try:
                review.hardened.openrouter_request_once(
                    "probe", review_schema(), compatibility, [], "anthropic/claude-opus-5"
                )
            except Exception as exc:  # noqa: BLE001 - compare exact historical failure class.
                failures.append(type(exc))
            else:
                raise AssertionError("empty choices unexpectedly returned successfully")
        assert failures == [IndexError, IndexError]
    finally:
        review.hardened.urllib.request.urlopen = original_urlopen
        if previous_key is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = previous_key

    fake = FakeModule()
    v54.apply_pareto_context_module(fake)
    config = fake.load_pareto_context_config("unused")
    assert isinstance(getattr(config, v54.SINK_ATTR, None), v54.RunTelemetrySink)

    # Stage classification uses only schema/config/ephemeral prompt markers and
    # stores no prompt body in the sink.
    per_file = copy.copy(config)
    per_file.dcoir_v47_per_file_projection = True
    assert v54.classify_stage("anything", review_schema(), per_file) == "per-file-first-pass"
    stage_tagged = copy.copy(config)
    stage_tagged._dcoir_v54_stage_label = "independent-challenger"
    assert v54.classify_stage("probe", review_schema(), stage_tagged) == "independent-challenger"
    stage_tagged._dcoir_v54_stage_label = "semantic-adjudicator"
    assert v54.classify_stage("probe", review_schema(), stage_tagged) == "semantic-adjudicator"
    bounded = copy.copy(config)
    bounded._dcoir_v54_stage_label = "semantic-adjudicator"
    bounded._dcoir_v52_pending_low_confidence_disposition = {"candidate_count": 1}
    assert v54.classify_stage("probe", review_schema(), bounded) == "bounded-low-confidence-disposition"
    assert v54.classify_stage("probe", verifier_schema(), config) == "verifier"
    assert v54.classify_stage("probe", repair_author_schema(), config) == "repair-author"
    assert v54.classify_stage("probe", critic_schema(), config) == "repair-critic"
    stage_tagged._dcoir_v54_stage_label = "broad-quality-retry"
    assert v54.classify_stage("probe", review_schema(), stage_tagged) == "broad-quality-retry"
    assert v54.classify_stage("ordinary", review_schema(), config) == "primary-semantic"
    assert v54.classify_stage("unknown", {"properties": {}}, config) == "unclassified"

    # One retrying call records only returned provider metadata and explicitly
    # accounts for the attempt lacking response telemetry.
    result = fake.hardened.openrouter_review(
        "Review quality retry:\nretry-call SECRET_PROMPT_MUST_NOT_SURVIVE",
        review_schema(),
        config,
    )
    assert result[0]["findings"] == []
    summary = v54.summarize_sink(config)
    assert summary["review_calls"] == 1
    assert summary["request_attempts"] == 2
    assert summary["provider_response_events"] == 1
    assert summary["attempts_without_response_telemetry"] == 1
    assert summary["stages"]["primary-semantic"]["attempts_without_response_telemetry"] == 1
    assert summary["stages"]["primary-semantic"]["attempt_outcomes"] == {
        "response_telemetry_missing": 1,
        "response_telemetry_observed": 1,
    }
    assert summary["metrics"]["prompt_tokens"]["observed_total"] == 100
    assert summary["metrics"]["completion_tokens"]["observed_total"] == 20
    assert summary["metrics"]["total_tokens"]["observed_total"] == 120
    assert summary["metrics"]["reasoning_tokens"]["observed_total"] == 7
    assert summary["metrics"]["cached_tokens"]["observed_total"] == 40
    assert summary["metrics"]["cache_write_tokens"]["observed_total"] == 5
    assert abs(float(summary["metrics"]["cost"]["observed_total"]) - 0.0125) < 1e-9
    assert summary["providers"] == {"Provider A": 1}
    assert summary["service_tiers"] == {"unknown": 1}
    assert summary["stages"]["primary-semantic"]["service_tiers"] == {"unknown": 1}
    assert summary["structured_output_recovery"] == {"balanced-envelope": 1}
    assert summary["response_healing_events"] == 1
    serialized = repr(summary)
    assert "SECRET_PROMPT_MUST_NOT_SURVIVE" not in serialized
    assert "SECRET_RESPONSE_MUST_NOT_SURVIVE" not in serialized
    assert "SECRET_TOKEN_MUST_NOT_SURVIVE" not in serialized

    # Failed calls remain visible without fabricating provider, token, or cost
    # data that never returned from OpenRouter.
    try:
        fake.hardened.openrouter_review("fail-call", review_schema(), config)
    except RuntimeError as exc:
        assert "synthetic transport failure" in str(exc)
    else:
        raise AssertionError("synthetic failed call did not re-raise")
    summary = v54.summarize_sink(config)
    assert summary["review_calls"] == 2
    assert summary["failed_review_calls"] == 1
    assert summary["request_attempts"] == 4
    assert summary["provider_response_events"] == 1
    assert summary["attempts_without_response_telemetry"] == 3
    assert summary["stages"]["primary-semantic"]["attempt_outcomes"] == {
        "response_telemetry_missing": 3,
        "response_telemetry_observed": 1,
    }
    assert summary["metrics"]["cost"]["observed_events"] == 1

    # Shallow stage configs share one lock-protected sink under concurrent
    # per-file execution. Each worker still receives its own capture projection.
    def run_worker(index: int) -> None:
        staged = copy.copy(config)
        staged.dcoir_v47_per_file_projection = True
        fake.hardened.openrouter_review(
            f"worker-{index}", review_schema(), staged
        )
        # v47 compatibility: telemetry remains readable from the caller's stage
        # config even though v54 used a second shallow request projection.
        assert staged._openrouter_last_request_telemetry["provider"] == "Provider A"

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(run_worker, range(12)))
    summary = v54.summarize_sink(config)
    assert summary["review_calls"] == 14
    assert summary["stages"]["per-file-first-pass"]["calls"] == 12
    assert summary["provider_response_events"] == 13

    # Missing usage remains explicitly missing rather than converted to zeros.
    missing = v54.normalize_event(
        {"requested_model": "m", "served_model": "m", "provider": "p", "usage": {}},
        "primary-semantic",
        "success",
    )
    assert missing["prompt_tokens"] is None
    assert missing["reasoning_tokens"] is None
    assert missing["cached_tokens"] is None
    assert missing["cache_write_tokens"] is None
    assert missing["cost"] is None

    # The existing terminal progress surface is the durable production output;
    # it remains active with debug=false and does not depend on debug artifacts.
    reporter = fake.hardened.ProgressReporter(None, 519, "/dcoir-review", config)
    reporter.complete("model-a", 0, "COMMENT")
    assert reporter.completed is True
    telemetry_updates = [message for stage, message in reporter.updates if stage == "openrouter-telemetry"]
    assert len(telemetry_updates) == 1
    assert "schema=dcoir_openrouter_run_telemetry_v1" in telemetry_updates[0]
    assert "cached_tokens=" in telemetry_updates[0]
    assert "total_tokens=" in telemetry_updates[0]
    assert "cost=" in telemetry_updates[0]
    assert len(telemetry_updates[0]) <= 1800
    assert getattr(config, v54.SUMMARY_ATTR)["review_calls"] == 14


    # Telemetry faults are side-channel failures only: they must never replace a
    # successful review result or mask the provider's original exception.
    original_drain = v54._drain_call
    def broken_drain(*_args, **_kwargs):
        raise RuntimeError("synthetic telemetry drain failure")
    v54._drain_call = broken_drain
    try:
        before_errors = v54._telemetry_error_count(config)
        preserved = fake.hardened.openrouter_review("ordinary", review_schema(), config)
        assert preserved[0]["findings"] == []
        assert v54._telemetry_error_count(config) == before_errors + 1
        try:
            fake.hardened.openrouter_review("fail-call", review_schema(), config)
        except RuntimeError as exc:
            assert "synthetic transport failure" in str(exc)
        else:
            raise AssertionError("telemetry failure masked provider failure semantics")
        assert v54._telemetry_error_count(config) == before_errors + 2
    finally:
        v54._drain_call = original_drain

    # Terminal telemetry summarization is also fail-soft. The original reporter
    # complete/fail methods must run, and a bounded unavailable marker is emitted.
    original_summarize = v54.summarize_sink
    def broken_summary(_config):
        raise RuntimeError("synthetic telemetry summary failure")
    v54.summarize_sink = broken_summary
    try:
        complete_reporter = fake.hardened.ProgressReporter(None, 519, "/dcoir-review", config)
        complete_reporter.complete("model-a", 0, "COMMENT")
        assert complete_reporter.completed is True
        assert any(
            stage == "openrouter-telemetry" and "telemetry_status=unavailable" in message
            for stage, message in complete_reporter.updates
        )
        fail_reporter = fake.hardened.ProgressReporter(None, 519, "/dcoir-review", config)
        fail_reporter.fail("synthetic original failure")
        assert fail_reporter.failed is True
    finally:
        v54.summarize_sink = original_summarize

    # Loader-side telemetry initialization and patch wiring are best-effort too.
    original_ensure = v54._ensure_sink
    def broken_ensure(_config):
        raise RuntimeError("synthetic telemetry sink failure")
    v54._ensure_sink = broken_ensure
    try:
        fallback_config = fake.load_pareto_context_config("unused")
        assert fallback_config.model == "model-a"
        assert v54._telemetry_error_count(fallback_config) >= 1
    finally:
        v54._ensure_sink = original_ensure

    broken_module = SimpleNamespace(
        hardened=SimpleNamespace(),
        load_pareto_context_config=lambda _path: SimpleNamespace(model="sentinel"),
    )
    original_loader = broken_module.load_pareto_context_config
    v54.apply_pareto_context_module(broken_module)
    assert getattr(broken_module, v54.APPLIED_MARKER, False) is False
    assert set(getattr(broken_module, v54.PATCH_ERRORS_ATTR, ())) == {
        "openrouter-review", "progress-reporter"
    }
    assert broken_module.load_pareto_context_config is original_loader
    assert not hasattr(broken_module, v54.LOAD_STORAGE)

    print("dcoir_review_required_runtime_patch_v54_selftest: PASS")


if __name__ == "__main__":
    main()
