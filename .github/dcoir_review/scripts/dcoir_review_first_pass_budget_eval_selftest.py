#!/usr/bin/env python3
"""Deterministic no-network checks for first-pass output-budget evaluation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import dcoir_review_first_pass_budget_eval as budget
import dcoir_review_first_pass_candidate_eval as base


class FakeResponse:
    def __init__(self, payload: object, status: int = 200, raw: bytes | None = None) -> None:
        self.payload = payload
        self.status = status
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        if self.raw is not None:
            return self.raw
        return json.dumps(self.payload).encode("utf-8")


def valid_payload(content: str, *, finish_reason: str = "stop") -> dict:
    return {
        "id": "gen-budget-unit-test",
        "model": "anthropic/claude-sonnet-5",
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {"content": content},
            }
        ],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 40,
            "total_tokens": 160,
            "cost": 0.004,
            "completion_tokens_details": {"reasoning_tokens": 12},
        },
        "openrouter_metadata": {
            "endpoints": {
                "available": [
                    {
                        "provider": "Claude Platform on AWS",
                        "model": "anthropic/claude-sonnet-5",
                        "selected": True,
                    }
                ]
            }
        },
    }


def main() -> None:
    policy = budget.load_policy()
    assert policy["stage"] == "first_pass_detector"
    assert policy["selected_candidate_for_budget_test"]["max_tokens"] == 32768

    matrix = base.load_matrix()
    candidate = base.candidate_by_id(matrix, "sonnet5-high")
    cases = base.load_cases(matrix)
    lane_case = next(case for case in cases if case["id"] == "pr448-lane-separation-binding")
    system_prompt = base.SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    schema = base.load_json(base.REVIEW_SCHEMA_PATH)

    bounded = budget.budgeted_candidate(candidate, 32768)
    payload = base.build_payload(bounded, lane_case, system_prompt, schema, matrix["request_contract"])
    assert payload["model"] == "anthropic/claude-sonnet-5"
    assert payload["reasoning"] == {"enabled": True, "effort": "high", "exclude": True}
    assert payload["max_tokens"] == 32768
    assert "temperature" not in payload

    try:
        budget.budgeted_candidate(candidate, 0)
    except ValueError as exc:
        assert "max_tokens" in str(exc)
    else:
        raise AssertionError("Non-positive output budget must fail closed")

    plan = budget.plan_report(matrix, cases, candidate, 32768, policy)
    assert plan["mode"] == "plan-no-network"
    assert plan["network_calls"] == 0
    assert plan["no_publication"] is True
    assert plan["max_tokens"] == 32768
    assert plan["case_counts"]["total"] == 14

    old_key = os.environ.pop("OPENROUTER_API_KEY", None)
    try:
        try:
            budget.run_live(
                matrix,
                cases[:1],
                candidate,
                max_tokens=32768,
                timeout_seconds=1,
                policy=policy,
            )
        except RuntimeError as exc:
            assert "OPENROUTER_API_KEY" in str(exc)
        else:
            raise AssertionError("Live budget mode must require OPENROUTER_API_KEY")
    finally:
        if old_key is not None:
            os.environ["OPENROUTER_API_KEY"] = old_key

    valid_content = json.dumps(
        {
            "summary": "One defect.",
            "findings": [
                {
                    "title": "Bind separation to the execution lanes",
                    "severity": "high",
                    "confidence": 0.95,
                    "path": "evaluation/pr448-lane-separation-binding.py",
                    "line": 1,
                    "body": "The unrelated separate marker is not bound to the endpoint/local lane relationship.",
                    "suggested_replacement": "",
                    "validation": "Reject same-shell lane mixing.",
                }
            ],
        }
    )

    def valid_opener(_request, timeout):
        assert timeout == 9
        return FakeResponse(valid_payload(valid_content))

    success = budget.call_openrouter_budgeted(payload, "unit-test-key", timeout_seconds=9, opener=valid_opener)
    assert success["ok"] is True
    assert success["finish_reason"] == "stop"
    assert success["selected_provider"] == "Claude Platform on AWS"
    assert success["usage"]["reasoning_tokens"] == 12
    assert base.score_case(lane_case, success)["correct"] is True

    def length_opener(_request, timeout):
        assert timeout == 9
        return FakeResponse(valid_payload(valid_content, finish_reason="length"))

    exhausted = budget.call_openrouter_budgeted(payload, "unit-test-key", timeout_seconds=9, opener=length_opener)
    assert exhausted["ok"] is False
    assert exhausted["error_type"] == "output-budget-exhausted"
    assert exhausted["finish_reason"] == "length"
    assert exhausted["usage"]["completion_tokens"] == 40
    exhausted_score = base.score_case(lane_case, exhausted)
    assert exhausted_score["correct"] is False
    assert exhausted_score["disposition"] == "request-error"

    malformed = valid_payload('{"findings":', finish_reason="stop")

    def malformed_opener(_request, timeout):
        assert timeout == 9
        return FakeResponse(malformed)

    invalid_structured = budget.call_openrouter_budgeted(
        payload,
        "unit-test-key",
        timeout_seconds=9,
        opener=malformed_opener,
    )
    assert invalid_structured["ok"] is False
    assert invalid_structured["error_type"] == "invalid-structured-output"
    assert invalid_structured["finish_reason"] == "stop"

    missing_findings = valid_payload(json.dumps({"summary": "No findings member"}), finish_reason="stop")

    def missing_findings_opener(_request, timeout):
        assert timeout == 9
        return FakeResponse(missing_findings)

    missing = budget.call_openrouter_budgeted(
        payload,
        "unit-test-key",
        timeout_seconds=9,
        opener=missing_findings_opener,
    )
    assert missing["ok"] is False
    assert missing["error_type"] == "invalid-structured-output"

    def non_stop_opener(_request, timeout):
        assert timeout == 9
        return FakeResponse(valid_payload(valid_content, finish_reason="content_filter"))

    non_stop = budget.call_openrouter_budgeted(
        payload,
        "unit-test-key",
        timeout_seconds=9,
        opener=non_stop_opener,
    )
    assert non_stop["ok"] is False
    assert non_stop["error_type"] == "non-stop-finish-reason"

    def invalid_json_opener(_request, timeout):
        assert timeout == 9
        return FakeResponse({}, raw=b"not-json")

    invalid_json = budget.call_openrouter_budgeted(
        payload,
        "unit-test-key",
        timeout_seconds=9,
        opener=invalid_json_opener,
    )
    assert invalid_json["ok"] is False
    assert invalid_json["error_type"] == "invalid-response-json"

    source_text = Path(budget.__file__).read_text(encoding="utf-8")
    assert "GITHUB_TOKEN" not in source_text
    assert "api.github.com" not in source_text
    assert "subprocess" not in source_text
    assert "pulls/" not in source_text
    assert "--execute-live" in source_text

    print(
        "dcoir_review_first_pass_budget_eval_selftest passed: "
        "32768-token first-pass plan, length/invalid-structure fail closed, no network/publication"
    )


if __name__ == "__main__":
    main()
