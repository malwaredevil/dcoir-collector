#!/usr/bin/env python3
"""Deterministic regressions for stable DCOIR Review run telemetry."""

from __future__ import annotations

import copy
import importlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from dcoir_review.entrypoint import DcoirReviewEntrypoint
from dcoir_review.per_file_routing import PER_FILE_PROJECTION_ATTR
from dcoir_review import structured_result_disposition as structured_disposition
from dcoir_review import progress_reporting


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
        self.steps: list[tuple[str, str]] = []
        self.bodies: list[str] = []

    def update(self, stage: str, message: str) -> None:
        self.updates.append((stage, message))

    def _record(self, stage: str, message: str) -> None:
        self.steps.append((stage, message))

    def _body(self, state: str, final_lines=None) -> str:
        return "\n".join([state, *(final_lines or [])])

    def _update_comment(self, body: str) -> None:
        self.bodies.append(body)

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
            config._openrouter_request_attempt_telemetry_events = [
                {
                    "request_attempt_count": 1,
                    "requested_model": "model-a",
                    "model_index": 1,
                    "model_count": 2,
                    "attempt_in_model": 1,
                    "attempt_limit": 2,
                    "outcome": "retry",
                    "failure_class": "http_error",
                    "http_status": 503,
                },
                {
                    "request_attempt_count": 2,
                    "requested_model": "model-a",
                    "model_index": 1,
                    "model_count": 2,
                    "attempt_in_model": 2,
                    "attempt_limit": 2,
                    "outcome": "terminal_failure",
                    "failure_class": "runtime_error",
                },
            ]
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
        if "retry-call" in text:
            config._openrouter_request_attempt_telemetry_events = [
                {
                    "request_attempt_count": 1,
                    "requested_model": "model-a",
                    "model_index": 1,
                    "model_count": 2,
                    "attempt_in_model": 1,
                    "attempt_limit": 2,
                    "outcome": "retry",
                    "failure_class": "empty_response",
                },
                {
                    "request_attempt_count": 2,
                    "requested_model": "model-a",
                    "model_index": 1,
                    "model_count": 2,
                    "attempt_in_model": 2,
                    "attempt_limit": 2,
                    "outcome": "success",
                },
            ]
        else:
            config._openrouter_request_attempt_telemetry_events = [
                {
                    "request_attempt_count": 1,
                    "requested_model": "model-a",
                    "model_index": 1,
                    "model_count": 2,
                    "attempt_in_model": 1,
                    "attempt_limit": 1,
                    "outcome": "success",
                }
            ]
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
    from dcoir_review import review_telemetry as telemetry

    # Production config initialization now uses the stable telemetry owner.
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    production_config = review.load_pareto_context_config(
        ".github/dcoir_review/openrouter-pr-review-pareto.yml"
    )
    assert production_config.debug is False
    assert progress_reporting.telemetry is telemetry
    assert isinstance(getattr(production_config, telemetry.SINK_ATTR, None), telemetry.RunTelemetrySink)

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
    progress_reporting.apply_pareto_context_module(fake)
    config = fake.load_pareto_context_config("unused")
    # Synthetic component fixtures bypass the canonical production config loader.
    # Production initialization is asserted above; initialize the shared sink explicitly here.
    telemetry.ensure_sink(config)
    assert isinstance(getattr(config, telemetry.SINK_ATTR, None), telemetry.RunTelemetrySink)

    def run_review(prompt, schema, call_config, reporter=None):
        state = telemetry.prepare_review_call(prompt, schema, call_config)
        active_config = state.staged_config if state is not None else call_config
        try:
            result = fake.hardened.openrouter_review(
                prompt, schema, active_config, reporter
            )
        except Exception:
            telemetry.finish_review_call(state, "failed")
            raise
        telemetry.finish_review_call(state, "success")
        return result

    # Terminal telemetry is strictly observational. Even an unexpected failure
    # of the extracted helper itself must not block canonical completion/failure.
    original_terminal_emit = telemetry.emit_run_telemetry
    def broken_terminal_emit(_module, _reporter):
        raise RuntimeError("synthetic terminal telemetry failure")
    telemetry.emit_run_telemetry = broken_terminal_emit
    try:
        failsoft_complete = fake.hardened.ProgressReporter(None, 519, "/dcoir-review", config)
        failsoft_complete.complete("model-a", 0, "COMMENT")
        assert failsoft_complete.completed is True
        failsoft_fail = fake.hardened.ProgressReporter(None, 519, "/dcoir-review", config)
        failsoft_fail.fail("synthetic original failure")
        assert failsoft_fail.failed is True
    finally:
        telemetry.emit_run_telemetry = original_terminal_emit

    # Stage classification uses only schema/config/ephemeral prompt markers and
    # stores no prompt body in the sink.
    per_file = copy.copy(config)
    setattr(per_file, PER_FILE_PROJECTION_ATTR, True)
    assert telemetry.classify_stage("anything", review_schema(), per_file) == "per-file-first-pass"
    stage_tagged = copy.copy(config)
    stage_tagged._dcoir_v54_stage_label = "independent-challenger"
    assert telemetry.classify_stage("probe", review_schema(), stage_tagged) == "independent-challenger"
    stage_tagged._dcoir_v54_stage_label = "semantic-adjudicator"
    assert telemetry.classify_stage("probe", review_schema(), stage_tagged) == "semantic-adjudicator"
    bounded = copy.copy(config)
    bounded._dcoir_v54_stage_label = "semantic-adjudicator"
    setattr(bounded, structured_disposition.PENDING_ATTR, {"candidate_count": 1})
    assert telemetry.classify_stage("probe", review_schema(), bounded) == "bounded-low-confidence-disposition"
    assert telemetry.classify_stage("probe", verifier_schema(), config) == "verifier"
    assert telemetry.classify_stage("probe", repair_author_schema(), config) == "repair-author"
    assert telemetry.classify_stage("probe", critic_schema(), config) == "repair-critic"
    stage_tagged._dcoir_v54_stage_label = "broad-quality-retry"
    assert telemetry.classify_stage("probe", review_schema(), stage_tagged) == "broad-quality-retry"
    assert telemetry.classify_stage("ordinary", review_schema(), config) == "primary-semantic"
    assert telemetry.classify_stage("unknown", {"properties": {}}, config) == "unclassified"
    for synthetic_filename, synthetic_function in (
        ("part_05_debug_and_merge.py", "openrouter_review_with_quality_retry"),
        ("dcoir_review_required_runtime_patch_v22.py", "openrouter_review_with_hybrid_first_pass"),
    ):
        namespace: dict[str, object] = {"telemetry": telemetry}
        exec(
            compile(
                f"""
def {synthetic_function}(prompt, schema, config):
    retry_prompt = prompt
    return telemetry.classify_stage(prompt, schema, config)
""",
                synthetic_filename,
                "exec",
            ),
            namespace,
        )
        assert namespace[synthetic_function]("probe", review_schema(), config) == "broad-quality-retry"
    namespace: dict[str, object] = {"telemetry": telemetry}
    exec(
        compile(
            """
def openrouter_review_with_hybrid_first_pass(prompt, schema, config):
    return telemetry.classify_stage(prompt, schema, config)
""",
            "dcoir_review_required_runtime_patch_v44_execution.py",
            "exec",
        ),
        namespace,
    )
    assert (
        namespace["openrouter_review_with_hybrid_first_pass"]("probe", review_schema(), config)
        == "primary-semantic"
    )
    namespace = {"telemetry": telemetry}
    exec(
        compile(
            """
def adversarial_confirmation_stage(prompt, schema, config):
    confirmation_prompt = prompt
    return telemetry.classify_stage(prompt, schema, config)
""",
            "dcoir_review_required_runtime_patch_v32.py",
            "exec",
        ),
        namespace,
    )
    assert (
        namespace["adversarial_confirmation_stage"]("probe", review_schema(), config)
        == "independent-challenger"
    )
    namespace = {"telemetry": telemetry}
    exec(
        compile(
            """
def semantic_adjudication_stage(wrapper_prompt, schema, config):
    prompt = wrapper_prompt
    return telemetry.classify_stage(prompt, schema, config)
""",
            "dcoir_review_required_runtime_patch_v35.py",
            "exec",
        ),
        namespace,
    )
    assert (
        namespace["semantic_adjudication_stage"]("probe", review_schema(), config)
        == "semantic-adjudicator"
    )

    # One retrying call records only returned provider metadata and explicitly
    # accounts for the attempt lacking response telemetry.
    result = run_review(
        "Review quality retry:\nretry-call SECRET_PROMPT_MUST_NOT_SURVIVE",
        review_schema(),
        config,
    )
    assert result[0]["findings"] == []
    summary = telemetry.summarize_sink(config)
    assert summary["review_calls"] == 1
    assert summary["request_attempts"] == 2
    assert summary["provider_response_events"] == 1
    assert summary["attempts_without_response_telemetry"] == 1
    assert summary["stages"]["primary-semantic"]["attempts_without_response_telemetry"] == 1
    assert summary["stages"]["primary-semantic"]["attempt_outcomes"] == {
        "retry": 1,
        "success": 1,
    }
    assert summary["stages"]["primary-semantic"]["attempt_requested_models"] == {"model-a": 2}
    assert summary["attempt_requested_models"] == {"model-a": 2}
    assert summary["stages"]["primary-semantic"]["attempt_failure_classes"] == {"empty_response": 1}
    assert summary["stages"]["primary-semantic"]["attempt_http_statuses"] == {}
    assert summary["attempt_failure_classes"] == {"empty_response": 1}
    assert summary["attempt_http_statuses"] == {}
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
        run_review("fail-call", review_schema(), config)
    except RuntimeError as exc:
        assert "synthetic transport failure" in str(exc)
    else:
        raise AssertionError("synthetic failed call did not re-raise")
    summary = telemetry.summarize_sink(config)
    assert summary["review_calls"] == 2
    assert summary["failed_review_calls"] == 1
    assert summary["request_attempts"] == 4
    assert summary["provider_response_events"] == 1
    assert summary["attempts_without_response_telemetry"] == 3
    assert summary["stages"]["primary-semantic"]["attempt_outcomes"] == {
        "retry": 2,
        "success": 1,
        "terminal_failure": 1,
    }
    assert summary["stages"]["primary-semantic"]["attempt_failure_classes"] == {
        "empty_response": 1,
        "http_error": 1,
        "runtime_error": 1,
    }
    assert summary["stages"]["primary-semantic"]["attempt_http_statuses"] == {"503": 1}
    assert summary["attempt_failure_classes"] == {
        "empty_response": 1,
        "http_error": 1,
        "runtime_error": 1,
    }
    assert summary["attempt_http_statuses"] == {"503": 1}
    assert summary["metrics"]["cost"]["observed_events"] == 1

    # Shallow stage configs share one lock-protected sink under concurrent
    # per-file execution. Each worker still receives its own capture projection.
    def run_worker(index: int) -> None:
        staged = copy.copy(config)
        setattr(staged, PER_FILE_PROJECTION_ATTR, True)
        run_review(
            f"worker-{index}", review_schema(), staged
        )
        # v47 compatibility: telemetry remains readable from the caller's stage
        # config even though v54 used a second shallow request projection.
        assert staged._openrouter_last_request_telemetry["provider"] == "Provider A"

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(run_worker, range(12)))
    summary = telemetry.summarize_sink(config)
    assert summary["review_calls"] == 14
    assert summary["stages"]["per-file-first-pass"]["calls"] == 12
    assert summary["provider_response_events"] == 13

    # Missing usage remains explicitly missing rather than converted to zeros.
    missing = telemetry.normalize_event(
        {"requested_model": "m", "served_model": "m", "provider": "p", "usage": {}},
        "primary-semantic",
        "success",
    )
    assert missing["prompt_tokens"] is None
    assert missing["reasoning_tokens"] is None
    assert missing["cached_tokens"] is None
    assert missing["cache_write_tokens"] is None
    assert missing["cost"] is None

    # Stable telemetry facade keeps request-attempt normalization available.
    normalized_attempt = telemetry.normalize_attempt(
        {"request_attempt_count": 2, "outcome": "retry", "requested_model": "m"}
    )
    assert normalized_attempt["attempt"] == 2
    assert normalized_attempt["outcome"] == "retry"

    # Missing categorical response metadata is explicit, not silently filtered.
    missing_config = fake.load_pareto_context_config("unused")
    missing_sink = telemetry.ensure_sink(missing_config)
    missing_event = telemetry.normalize_event(
        {"usage": {}}, "primary-semantic", "success"
    )
    missing_sink.add_call(
        {
            "stage": "primary-semantic",
            "outcome": "success",
            "request_attempts": 1,
            "response_events": 1,
            "attempts_without_response_telemetry": 0,
            "attempt_records": [
                {"attempt": 1, "outcome": "success", "requested_model": "model-a"}
            ],
        },
        [missing_event],
    )
    missing_summary = telemetry.summarize_sink(missing_config)
    assert missing_summary["providers"] == {"unknown": 1}
    assert missing_summary["requested_models"] == {"unknown": 1}
    assert missing_summary["served_models"] == {"unknown": 1}
    assert missing_summary["finish_reasons"] == {"unknown": 1}
    assert missing_summary["service_tiers"] == {"unknown": 1}
    assert missing_summary["metadata_coverage"]["provider"] == {
        "observed_events": 0, "missing_events": 1
    }
    assert "metadata_missing=" in telemetry.compact_summary(missing_summary)

    # Errors raised on shallow stage projections must surface on the root config.
    error_config = fake.load_pareto_context_config("unused")
    telemetry.ensure_sink(error_config)
    shallow_error_config = copy.copy(error_config)
    telemetry.note_telemetry_error(shallow_error_config)
    assert telemetry.telemetry_error_count(error_config) == 1
    assert telemetry.summarize_sink(error_config)["telemetry_status"] == "partial"

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
    assert "attempt_outcomes=" in telemetry_updates[0]
    assert "attempt_models=" in telemetry_updates[0]
    assert "failure_classes=" in telemetry_updates[0]
    assert "http_statuses=" in telemetry_updates[0]
    assert "metadata_missing=" in telemetry_updates[0]
    assert "requested_models=" in telemetry_updates[0]
    assert "served_models=" in telemetry_updates[0]
    assert "finish_reasons=" in telemetry_updates[0]
    assert "structured_output_recovery=" in telemetry_updates[0]
    assert len(telemetry_updates[0]) <= 1800
    assert getattr(config, telemetry.SUMMARY_ATTR)["review_calls"] == 14

    # Copilot follow-up regression: mandatory failure/status diagnostics must
    # remain complete even when lower-priority telemetry would exceed the
    # terminal 1,800-character budget.
    bloated_summary = copy.deepcopy(getattr(config, telemetry.SUMMARY_ATTR))
    bloated_summary["attempt_failure_classes"] = {
        "http_error": 9,
        "transport_error": 3,
    }
    bloated_summary["attempt_http_statuses"] = {"404": 2, "503": 7}
    bloated_summary["requested_models"] = {f"model-{i}-" + ("x" * 80): 1 for i in range(30)}
    bloated_summary["served_models"] = {f"served-{i}-" + ("y" * 80): 1 for i in range(30)}
    compact_bloated = telemetry.compact_summary(bloated_summary)
    assert len(compact_bloated) <= 1800
    assert "failure_classes=http_error:9,transport_error:3" in compact_bloated
    assert "http_statuses=404:2,503:7" in compact_bloated
    assert "optional_telemetry=[truncated]" in compact_bloated


    # Telemetry faults are side-channel failures only: they must never replace a
    # successful review result or mask the provider's original exception.
    original_drain = telemetry._drain_call
    def broken_drain(*_args, **_kwargs):
        raise RuntimeError("synthetic telemetry drain failure")
    telemetry._drain_call = broken_drain
    try:
        before_errors = telemetry.telemetry_error_count(config)
        preserved = run_review("ordinary", review_schema(), config)
        assert preserved[0]["findings"] == []
        assert telemetry.telemetry_error_count(config) == before_errors + 1
        try:
            run_review("fail-call", review_schema(), config)
        except RuntimeError as exc:
            assert "synthetic transport failure" in str(exc)
        else:
            raise AssertionError("telemetry failure masked provider failure semantics")
        assert telemetry.telemetry_error_count(config) == before_errors + 2
    finally:
        telemetry._drain_call = original_drain

    # Terminal telemetry summarization is also fail-soft. The original reporter
    # complete/fail methods must run, and a bounded unavailable marker is emitted.
    original_summarize = telemetry.summarize_sink
    def broken_summary(_config):
        raise RuntimeError("synthetic telemetry summary failure")
    telemetry.summarize_sink = broken_summary
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
        telemetry.summarize_sink = original_summarize

    # Loader-side telemetry initialization and patch wiring are best-effort too.
    original_ensure = telemetry.ensure_sink
    def broken_ensure(_config):
        raise RuntimeError("synthetic telemetry sink failure")
    telemetry.ensure_sink = broken_ensure
    try:
        # Loader-side initialization now belongs to canonical review_config, not telemetry.
        # Exercise the real canonical production loader while sink creation is broken.
        fallback_config = review.load_pareto_context_config(
            ".github/dcoir_review/openrouter-pr-review-pareto.yml"
        )
        assert fallback_config.debug is False
        assert telemetry.telemetry_error_count(fallback_config) >= 1
    finally:
        telemetry.ensure_sink = original_ensure

    # Provider-side attempt telemetry itself is bounded and prompt-free.
    provider_probe = copy.copy(production_config)
    provider_probe.openrouter_capture_request_telemetry = True
    provider_probe._openrouter_request_attempt_count = 1
    review.hardened._record_openrouter_attempt_telemetry(
        provider_probe,
        {
            "requested_model": "model-a",
            "model_index": 1,
            "model_count": 2,
            "attempt_in_model": 1,
            "attempt_limit": 4,
            "outcome": "fallback",
            "failure_class": "http_error",
            "http_status": 503,
            "provider": "Provider A",
            "prompt": "SECRET_PROMPT_MUST_NOT_SURVIVE",
        },
    )
    provider_attempt = provider_probe._openrouter_request_attempt_telemetry_events[0]
    assert provider_attempt["outcome"] == "fallback"
    assert provider_attempt["http_status"] == 503
    assert "prompt" not in provider_attempt

    print("dcoir_review_review_telemetry_selftest: PASS")


if __name__ == "__main__":
    main()
