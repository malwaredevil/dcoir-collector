#!/usr/bin/env python3
"""Deterministic no-network regression checks for first-pass candidate evaluation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import dcoir_review_first_pass_candidate_eval as evaluation


class FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def main() -> None:
    matrix = evaluation.load_matrix()
    cases = evaluation.load_cases(matrix)
    candidates = evaluation.selected_candidates(matrix, "all")

    assert [item["id"] for item in candidates] == [
        "opus5-xhigh-control",
        "opus5-high",
        "sonnet5-high",
    ]
    generalized = [case for case in cases if case["corpus"] == "generalized-controlled"]
    naturalistic = [case for case in cases if case["corpus"] == "naturalistic-known-defect"]
    assert len(generalized) == 12
    assert sum(case["expected"] == "finding" for case in generalized) == 10
    assert sum(case["expected"] == "clean" for case in generalized) == 2
    assert len(naturalistic) == 2
    assert {case["id"] for case in naturalistic} == {
        "pr448-lane-separation-binding",
        "pr448-numbered-lifecycle-duplicate",
    }

    old_key = os.environ.pop("OPENROUTER_API_KEY", None)
    try:
        plan = evaluation.plan_report(matrix, cases, candidates)
        assert plan["mode"] == "plan-no-network"
        assert plan["network_calls"] == 0
        assert plan["no_publication"] is True
        assert plan["case_counts"]["planned_total_requests"] == 42
        try:
            evaluation.run_live(matrix, cases[:1], candidates[:1], timeout_seconds=1)
        except RuntimeError as exc:
            assert "OPENROUTER_API_KEY" in str(exc)
        else:
            raise AssertionError("Live mode must require OPENROUTER_API_KEY")
    finally:
        if old_key is not None:
            os.environ["OPENROUTER_API_KEY"] = old_key

    system_prompt = evaluation.SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    schema = evaluation.load_json(evaluation.REVIEW_SCHEMA_PATH)
    contract = matrix["request_contract"]
    lane_case = next(case for case in naturalistic if case["id"] == "pr448-lane-separation-binding")

    control = evaluation.candidate_by_id(matrix, "opus5-xhigh-control")
    control_payload = evaluation.build_payload(control, lane_case, system_prompt, schema, contract)
    assert control_payload["model"] == "anthropic/claude-opus-5"
    assert control_payload["provider"] == {
        "allow_fallbacks": True,
        "require_parameters": True,
        "sort": "price",
    }
    assert control_payload["plugins"] == [{"id": "response-healing", "enabled": True}]
    assert control_payload["tools"] == []
    assert control_payload["stream"] is False
    assert control_payload["temperature"] == 0.2
    assert control_payload["reasoning"] == {"enabled": True, "effort": "xhigh", "exclude": True}
    assert control_payload["response_format"]["type"] == "json_schema"
    assert "max_tokens" not in control_payload
    assert "session_id" not in control_payload

    high = evaluation.candidate_by_id(matrix, "opus5-high")
    high_payload = evaluation.build_payload(high, lane_case, system_prompt, schema, contract)
    assert high_payload["reasoning"]["effort"] == "high"
    assert high_payload["temperature"] == 0.2
    sonnet = evaluation.candidate_by_id(matrix, "sonnet5-high")
    sonnet_payload = evaluation.build_payload(sonnet, lane_case, system_prompt, schema, contract)
    assert sonnet_payload["model"] == "anthropic/claude-sonnet-5"
    assert sonnet_payload["reasoning"]["effort"] == "high"
    assert "temperature" not in sonnet_payload

    invalid_temperature = dict(sonnet)
    invalid_temperature["temperature"] = 2.1
    try:
        evaluation.build_payload(invalid_temperature, lane_case, system_prompt, schema, contract)
    except ValueError as exc:
        assert "temperature" in str(exc)
    else:
        raise AssertionError("Out-of-range candidate temperature must fail closed")

    headers = evaluation.request_headers("unit-test-key")
    assert headers["X-OpenRouter-Metadata"] == "enabled"
    assert headers["X-OpenRouter-Cache"] == "false"
    assert headers["Authorization"] == "Bearer unit-test-key"

    fake_payload = {
        "id": "gen-unit-test",
        "model": "anthropic/claude-opus-5",
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "summary": "One semantic defect.",
                            "findings": [
                                {
                                    "title": "Bind separation to the execution lanes",
                                    "severity": "high",
                                    "confidence": 0.95,
                                    "path": "evaluation/pr448-lane-separation-binding.py",
                                    "line": 1,
                                    "body": "The unrelated separate marker is not bound to the endpoint/local lane relationship.",
                                    "suggested_replacement": "",
                                    "validation": "Check that same-shell lane mixing is rejected.",
                                }
                            ],
                        }
                    )
                }
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 25,
            "total_tokens": 125,
            "cost": 0.0125,
            "prompt_tokens_details": {"cached_tokens": 7, "cache_write_tokens": 3},
            "completion_tokens_details": {"reasoning_tokens": 11},
        },
        "openrouter_metadata": {
            "requested": "anthropic/claude-opus-5",
            "strategy": "direct",
            "attempt": 1,
            "endpoints": {
                "available": [
                    {"provider": "Anthropic", "model": "anthropic/claude-opus-5", "selected": True}
                ]
            },
            "attempts": [{"provider": "Anthropic", "model": "anthropic/claude-opus-5", "status": 200}],
            "pipeline": [
                {
                    "type": "response_healing",
                    "name": "response-healing",
                    "data": {"mode": "json_schema", "healed": False},
                }
            ],
        },
    }

    def fake_opener(_request, timeout):
        assert timeout == 9
        return FakeResponse(fake_payload)

    request_result = evaluation.call_openrouter(
        control_payload,
        "unit-test-key",
        timeout_seconds=9,
        opener=fake_opener,
    )
    assert request_result["ok"] is True
    assert request_result["selected_provider"] == "Anthropic"
    assert request_result["usage"] == {
        "prompt_tokens": 100,
        "completion_tokens": 25,
        "reasoning_tokens": 11,
        "cached_prompt_tokens": 7,
        "cache_write_tokens": 3,
        "total_tokens": 125,
        "cost_usd": 0.0125,
    }
    assert request_result["pipeline"][0]["name"] == "response-healing"

    scored = evaluation.score_case(lane_case, request_result)
    assert scored["correct"] is True
    assert scored["ambiguous"] is False
    assert scored["disposition"] == "finding-detected"

    unrelated_result = dict(request_result)
    unrelated_result["result"] = {
        "summary": "Other concern",
        "findings": [
            {
                "title": "Unrelated documentation concern",
                "body": "This documentation could be clearer.",
                "validation": "Read it.",
            }
        ],
    }
    ambiguous = evaluation.score_case(lane_case, unrelated_result)
    assert ambiguous["correct"] is False
    assert ambiguous["ambiguous"] is True

    clean_case = next(case for case in generalized if case["expected"] == "clean")
    clean_result = dict(request_result)
    clean_result["result"] = {"summary": "Clean", "findings": []}
    assert evaluation.score_case(clean_case, clean_result)["correct"] is True
    false_positive = evaluation.score_case(clean_case, request_result)
    assert false_positive["correct"] is False
    assert false_positive["disposition"] == "false-positive"

    error_score = evaluation.score_case(lane_case, {"ok": False, "error": "unit test"})
    assert error_score["correct"] is False
    assert error_score["disposition"] == "request-error"

    source_text = Path(evaluation.__file__).read_text(encoding="utf-8")
    assert "GITHUB_TOKEN" not in source_text
    assert "api.github.com" not in source_text
    assert "subprocess" not in source_text
    assert "pulls/" not in source_text
    assert "--execute-live" in source_text

    print(
        "dcoir_review_first_pass_candidate_eval_selftest passed: "
        "3 candidates, 12 controlled cases, 2 frozen naturalistic cases, candidate-specific temperature, no network/publication"
    )


if __name__ == "__main__":
    main()
