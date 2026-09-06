#!/usr/bin/env python3
"""Regression checks for DCOIR Review v47 stage-local first-pass routing."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

from dcoir_review.entrypoint import DcoirReviewEntrypoint


def _schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "findings": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["summary", "findings"],
        "additionalProperties": False,
    }


class FakeResponse:
    def __init__(self, value):
        self._raw = json.dumps(value).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._raw


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.post_terminal_patch_module_names[-1] == "dcoir_review_required_runtime_patch_v47"

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v47 = importlib.import_module("dcoir_review_required_runtime_patch_v47")
    assert getattr(review, v47.APPLIED_MARKER, False) is True

    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    assert config.model == "anthropic/claude-opus-5"
    assert config.model_stack == ["anthropic/claude-opus-5", "openai/gpt-5.6-sol-pro"]
    assert config.review_reasoning_effort == "xhigh"
    assert config.per_file_review_model_stack == ["anthropic/claude-sonnet-5"]
    assert config.per_file_review_reasoning_effort == "high"
    assert config.per_file_review_max_tokens == 32768
    assert config.per_file_review_provider_sort == "price"

    schema = _schema()
    global_payload = review.hardened.build_openrouter_payload(
        "global-probe", schema, config, [], config.model_stack[0]
    )
    assert global_payload["model"] == "anthropic/claude-opus-5"
    assert global_payload["temperature"] == 0.2
    assert global_payload["reasoning"] == {"enabled": True, "effort": "xhigh", "exclude": True}
    assert "max_tokens" not in global_payload
    assert "sort" not in global_payload["provider"]
    assert not any(
        isinstance(plugin, dict) and plugin.get("id") == "response-healing"
        for plugin in global_payload.get("plugins", [])
    )

    projected = v47.project_per_file_review_config(config)
    assert projected is not config
    assert projected.model == "anthropic/claude-sonnet-5"
    assert projected.model_stack == ["anthropic/claude-sonnet-5"]
    assert projected.review_reasoning_effort == "high"
    assert projected.openrouter_request_max_tokens == 32768
    assert projected.openrouter_provider_sort == "price"
    assert projected.openrouter_response_healing is True
    assert projected.openrouter_require_stop_finish_reason is True
    assert projected.dcoir_v47_per_file_projection is True
    assert not hasattr(config, "openrouter_request_max_tokens")
    assert not hasattr(config, "openrouter_provider_sort")
    assert config.model == "anthropic/claude-opus-5"
    assert config.review_reasoning_effort == "xhigh"

    per_file_payload = review.hardened.build_openrouter_payload(
        "per-file-probe", schema, projected, [], projected.model_stack[0]
    )
    assert per_file_payload["model"] == "anthropic/claude-sonnet-5"
    assert "temperature" not in per_file_payload
    assert per_file_payload["reasoning"] == {"enabled": True, "effort": "high", "exclude": True}
    assert per_file_payload["max_tokens"] == 32768
    assert per_file_payload["provider"]["sort"] == "price"
    assert per_file_payload["provider"]["require_parameters"] is True
    assert per_file_payload["response_format"]["type"] == "json_schema"
    assert per_file_payload["response_format"]["json_schema"]["strict"] is True
    assert per_file_payload["plugins"] == [{"id": "response-healing", "enabled": True}]

    # Absent optional stage keys preserve the historical global request contract.
    legacy = SimpleNamespace(
        model="anthropic/claude-opus-5",
        model_stack=["anthropic/claude-opus-5", "openai/gpt-5.6-sol-pro"],
        review_reasoning_effort="xhigh",
    )
    legacy_projected = v47.project_per_file_review_config(legacy)
    assert legacy_projected.model == legacy.model
    assert legacy_projected.model_stack == legacy.model_stack
    assert legacy_projected.review_reasoning_effort == "xhigh"
    assert not hasattr(legacy_projected, "dcoir_v47_per_file_projection")
    assert not hasattr(legacy_projected, "openrouter_request_max_tokens")
    assert not hasattr(legacy_projected, "openrouter_require_stop_finish_reason")

    # Prove the production per-file call receives the copy while the caller's
    # shared config remains untouched, and that request telemetry remains
    # available as a bounded debug artifact for later acceptance comparison.
    original_prompt = review.build_per_file_review_prompt
    original_openrouter_review = review.hardened.openrouter_review
    original_write_text = review.hardened.write_debug_text_artifact_safely
    original_write_json = review.hardened.write_debug_json_artifact_safely
    captured = {}

    def fake_openrouter_review(prompt, schema_arg, config_arg, reporter=None):
        captured["config"] = config_arg
        config_arg._dcoir_v47_last_request_telemetry = {
            "requested_model": config_arg.model,
            "served_model": config_arg.model,
            "provider": "Anthropic",
            "service_tier": "",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001},
            "request_attempt_count": 1,
            "response_healing_pipeline": [{"type": "response_healing", "name": "response-healing"}],
        }
        return {"summary": "clean", "findings": []}, config_arg.model, ""

    try:
        review.build_per_file_review_prompt = lambda *args, **kwargs: "per-file prompt"
        review.hardened.openrouter_review = fake_openrouter_review
        review.hardened.write_debug_text_artifact_safely = lambda *args, **kwargs: None
        review.hardened.write_debug_json_artifact_safely = (
            lambda cfg, path, value: captured.__setitem__(path, value)
        )
        result = review.review_single_file_context(
            1,
            {"path": "probe.py", "item": {"filename": "probe.py", "patch": "+print('x')"}, "text": "print('x')\n"},
            {"number": 457, "title": "probe"},
            "diff --git a/probe.py b/probe.py\n+print('x')\n",
            schema,
            config,
            [],
            "deep-forced",
        )
    finally:
        review.build_per_file_review_prompt = original_prompt
        review.hardened.openrouter_review = original_openrouter_review
        review.hardened.write_debug_text_artifact_safely = original_write_text
        review.hardened.write_debug_json_artifact_safely = original_write_json

    observed = captured["config"]
    assert observed.model_stack == ["anthropic/claude-sonnet-5"]
    assert observed.review_reasoning_effort == "high"
    assert observed.openrouter_request_max_tokens == 32768
    assert observed.openrouter_provider_sort == "price"
    assert result["model_used"] == "anthropic/claude-sonnet-5"
    assert result["request_telemetry"]["finish_reason"] == "stop"
    telemetry_artifact = captured["metadata/per-file/01-probe.py-request-telemetry.json"]
    assert telemetry_artifact["provider"] == "Anthropic"
    assert telemetry_artifact["usage"]["cost"] == 0.001
    assert config.model_stack[0] == "anthropic/claude-opus-5"
    assert config.review_reasoning_effort == "xhigh"

    # Capped first-pass completions must fail closed before JSON is scored, even
    # when a syntactically valid structured body survives Response Healing.
    original_urlopen = v47.urllib.request.urlopen
    previous_key = os.environ.get("OPENROUTER_API_KEY")
    os.environ["OPENROUTER_API_KEY"] = "selftest-key"

    def install_response(finish_reason, content, *, provider="Anthropic"):
        def fake_urlopen(req, timeout=180):
            return FakeResponse(
                {
                    "model": "anthropic/claude-sonnet-5",
                    "provider": provider,
                    "service_tier": "",
                    "choices": [
                        {
                            "finish_reason": finish_reason,
                            "message": {"content": content},
                        }
                    ],
                    "usage": {"prompt_tokens": 20, "completion_tokens": 7, "cost": 0.002},
                    "openrouter_metadata": {
                        "pipeline": [{"type": "response_healing", "name": "response-healing"}]
                    },
                }
            )

        v47.urllib.request.urlopen = fake_urlopen

    try:
        valid_content = json.dumps({"summary": "clean", "findings": []})
        for non_stop_reason in ("length", "content_filter"):
            capped = v47.project_per_file_review_config(config)
            install_response(non_stop_reason, valid_content)
            try:
                review.hardened.openrouter_request_once(
                    "probe", schema, capped, [], "anthropic/claude-sonnet-5"
                )
            except RuntimeError as exc:
                assert f"finish_reason={non_stop_reason}" in str(exc)
            else:
                raise AssertionError(f"non-stop completion {non_stop_reason!r} did not fail closed")
            assert capped._dcoir_v47_last_request_telemetry["finish_reason"] == non_stop_reason
            assert capped._dcoir_v47_last_request_telemetry["usage"]["cost"] == 0.002

        stopped = v47.project_per_file_review_config(config)
        install_response("stop", valid_content)
        parsed, served_model, service_tier = review.hardened.openrouter_request_once(
            "probe", schema, stopped, [], "anthropic/claude-sonnet-5"
        )
        assert parsed == {"summary": "clean", "findings": []}
        assert served_model == "anthropic/claude-sonnet-5"
        assert service_tier == ""
        assert stopped._dcoir_v47_last_request_telemetry["provider"] == "Anthropic"
        assert stopped._dcoir_v47_last_request_telemetry["finish_reason"] == "stop"
        assert stopped._dcoir_v47_last_request_telemetry["response_healing_pipeline"]

        invalid_root = v47.project_per_file_review_config(config)
        install_response("stop", "[]")
        try:
            review.hardened.openrouter_request_once(
                "probe", schema, invalid_root, [], "anthropic/claude-sonnet-5"
            )
        except RuntimeError as exc:
            assert "object root" in str(exc)
        else:
            raise AssertionError("non-object structured output did not fail closed")
    finally:
        v47.urllib.request.urlopen = original_urlopen
        if previous_key is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = previous_key

    patch_source = Path(
        ".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v47.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("git push", "merge_pull_request", "workflow_dispatch", "create_commit("):
        assert forbidden not in patch_source

    print("dcoir_review_required_runtime_patch_v47_selftest passed")


if __name__ == "__main__":
    main()
