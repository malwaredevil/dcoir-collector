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
    from dcoir_review_benchmark_diagnostics_selftest import run_tests
    run_tests()
    matrix = evaluation.load_matrix()
    cases = evaluation.load_cases(matrix)
    candidates = evaluation.selected_candidates(matrix, "all")

    expected_candidate_ids = [
        "opus5-xhigh-control",
        "opus5-xhigh-no-temp",
        "opus5-high",
        "sonnet5-high",
        "opus5.5-xhigh",
        "opus5.5-xhigh-prod-temp",
        "sonnet5.5-high",
        "sonnet5.5-high-prod-temp",
        "gpt5.6-sol-pro-control",
        "gpt5.6-terra-xhigh-control",
        "gpt6.1-sol-high",
        "gpt6.1-sol-pro",
        "gpt6-astra-xhigh",
        "gpt6-astra-xhigh-prod-temp",
        "qwen3.8-max",
        "glm5.3-high",
        "glm5.3-high-prod-temp",
        "deepseek-v4-pro-0813-high",
        "kimi-k3",
        "gemini3.8-flash-high",
        "glm5.3-flash-high",
        "gpt6-luna-high",
        "gpt6-luna-high-prod-temp",
        "deepseek-v4.1-flash",
        "mimo-v2.6-pro-xhigh",
        "mimo-v2.6-pro-xhigh-prod-temp",
        "mimo-v2.6-flash",
        "mimo-v2.6-flash-prod-high-temp",
        "kimi-k2.6",
        "auto-max",
        "pareto-code-080",
    ]
    assert [item["id"] for item in candidates] == expected_candidate_ids
    assert [item["id"] for item in evaluation.selected_candidates(matrix, "incumbents")] == [
        "opus5-xhigh-control",
        "opus5-high",
        "sonnet5-high",
    ]
    assert [item["id"] for item in evaluation.selected_candidates(matrix, "routine")] == [
        "sonnet5-high",
        "sonnet5.5-high",
        "gemini3.8-flash-high",
        "glm5.3-flash-high",
        "gpt6-luna-high",
        "deepseek-v4.1-flash",
        "mimo-v2.6-flash",
        "kimi-k2.6",
    ]
    assert [item["id"] for item in evaluation.selected_candidates(matrix, "gpt6-luna-high,glm5.3-flash-high")] == [
        "gpt6-luna-high",
        "glm5.3-flash-high",
    ]
    assert [item["id"] for item in evaluation.selected_candidates(matrix, "opus5-xhigh-no-temp,opus5.5-xhigh")] == [
        "opus5-xhigh-no-temp",
        "opus5.5-xhigh",
    ]
    assert [item["id"] for item in evaluation.selected_candidates(matrix, "deepseek-v4-pro-0813-high,kimi-k3,mimo-v2.6-flash")] == [
        "deepseek-v4-pro-0813-high",
        "kimi-k3",
        "mimo-v2.6-flash",
    ]
    assert [item["id"] for item in evaluation.selected_candidates(matrix, "gpt5.6-sol-pro-control,gpt5.6-terra-xhigh-control")] == [
        "gpt5.6-sol-pro-control",
        "gpt5.6-terra-xhigh-control",
    ]
    assert [item["id"] for item in evaluation.selected_candidates(matrix, "mimo-v2.6-pro-xhigh,mimo-v2.6-pro-xhigh-prod-temp")] == [
        "mimo-v2.6-pro-xhigh",
        "mimo-v2.6-pro-xhigh-prod-temp",
    ]
    advisor = evaluation.candidate_by_id(matrix, "mimo-v2.6-flash-advisor-opus5.5")
    assert advisor["explicit_only"] is True
    assert "mimo-v2.6-flash-advisor-opus5.5" not in {
        item["id"] for item in evaluation.selected_candidates(matrix, "all")
    }
    assert [item["id"] for item in evaluation.selected_candidates(matrix, "mimo-v2.6-flash-advisor-opus5.5")] == [
        "mimo-v2.6-flash-advisor-opus5.5"
    ]
    compatibility_selector = "opus5.5-xhigh-prod-temp,sonnet5.5-high-prod-temp,gpt6-astra-xhigh-prod-temp,glm5.3-high-prod-temp,gpt6-luna-high-prod-temp,mimo-v2.6-flash-prod-high-temp"
    assert [item["id"] for item in evaluation.selected_candidates(matrix, compatibility_selector)] == [
        "opus5.5-xhigh-prod-temp",
        "sonnet5.5-high-prod-temp",
        "gpt6-astra-xhigh-prod-temp",
        "glm5.3-high-prod-temp",
        "gpt6-luna-high-prod-temp",
        "mimo-v2.6-flash-prod-high-temp",
    ]
    recommended_ids = {item["id"] for item in evaluation.selected_candidates(matrix, "recommended")}
    assert {"deepseek-v4-pro-0813-high", "kimi-k3", "mimo-v2.6-flash"}.isdisjoint(recommended_ids)
    generalized = [case for case in cases if case["corpus"] == "generalized-controlled"]
    naturalistic = [case for case in cases if case["corpus"] == "naturalistic-known-defect"]
    assert len(generalized) == 12
    assert sum(case["expected"] == "finding" for case in generalized) == 10
    assert sum(case["expected"] == "clean" for case in generalized) == 2
    assert len(naturalistic) == 4
    assert {case["id"] for case in naturalistic} == {
        "pr448-lane-separation-binding",
        "pr448-numbered-lifecycle-duplicate",
        "pr581-usb-ticket-field-binding",
        "pr581-usb-complete-field-value",
    }

    production_suite_expectations = {
        "prmutation-all": (12, "prmutation--", "pr-mutation"),
        "prprecision-all": (10, "prprecision--", "pr-precision-v12"),
        "multilang-all": (40, "multilang--", "multilang-adversarial"),
    }
    for selector, (expected_count, prefix, suite_name) in production_suite_expectations.items():
        suite_cases, suite_complete = evaluation.resolve_case_selection(matrix, [selector])
        assert suite_complete is True
        assert len(suite_cases) == expected_count
        assert all(str(case["id"]).startswith(prefix) for case in suite_cases)
        assert all(case["_suite"] == suite_name for case in suite_cases)
        suite_plan = evaluation.plan_report(matrix, suite_cases, candidates[:1])
        assert suite_plan["mode"] == "plan-no-network"
        assert suite_plan["network_calls"] == 0
        assert suite_plan["no_publication"] is True
        assert suite_plan["case_counts"]["production_shaped_cases"] == expected_count
        assert suite_plan["case_counts"]["planned_total_requests"] == expected_count
        subset, subset_complete = evaluation.resolve_case_selection(matrix, [suite_cases[0]["id"]])
        assert len(subset) == 1
        assert subset_complete is False

    mutation_cases, _ = evaluation.resolve_case_selection(matrix, ["prmutation-all"])
    mutation_prompt = evaluation.build_case_prompt(mutation_cases[0])
    assert "Repository: DCOIR-Collector/dcoir-collector" in mutation_prompt
    assert "Unified diff:" in mutation_prompt
    assert "expected_findings" not in mutation_prompt
    assert "ground_truth" not in mutation_prompt.lower()
    mutation_error_score = evaluation.score_case(
        mutation_cases[0],
        {"ok": False},
    )
    assert mutation_error_score["expected"] in {"finding", "clean"}
    assert mutation_error_score["disposition"] == "request-error"

    precision_cases, _ = evaluation.resolve_case_selection(matrix, ["prprecision-all"])
    precision_prompt = evaluation.build_case_prompt(precision_cases[0])
    assert "Repository: DCOIR-Collector/dcoir-collector" in precision_prompt
    assert "Trusted repository guidance:" in precision_prompt
    precision_clean_score = evaluation.score_case(
        precision_cases[0],
        {"ok": True, "result": {"findings": []}},
    )
    assert precision_clean_score["expected"] == "clean"
    assert precision_clean_score["correct"] is True
    assert precision_clean_score["disposition"] == "clean"

    multilang_cases, _ = evaluation.resolve_case_selection(matrix, ["multilang-all"])
    multilang_prompt = evaluation.build_case_prompt(multilang_cases[0])
    assert "Evaluation-only adversarial first-pass semantic review case." in multilang_prompt
    assert "finding_term_groups" not in multilang_prompt
    assert "_suite_original_id" not in multilang_prompt

    old_key = os.environ.pop("OPENROUTER_API_KEY", None)
    try:
        plan = evaluation.plan_report(matrix, cases, candidates)
        assert plan["mode"] == "plan-no-network"
        assert plan["network_calls"] == 0
        assert plan["no_publication"] is True
        assert plan["case_counts"]["planned_total_requests"] == 496
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
    serialized_case = next(case for case in generalized if case["id"] == "serialized-marker-variant")
    advisor_payload = evaluation.build_payload(
        evaluation.candidate_by_id(matrix, "mimo-v2.6-flash-advisor-opus5.5"),
        serialized_case,
        system_prompt,
        schema,
        contract,
    )
    assert advisor_payload["model"] == "xiaomi/mimo-v2.6-flash"
    assert advisor_payload["tool_choice"] == "required"
    assert advisor_payload["tools"] == [{
        "type": "openrouter:advisor",
        "parameters": {
            "name": "semantic-reviewer",
            "model": "anthropic/claude-opus-5.5",
            "instructions": "Independently assess the supplied implementation and correctness contract. Identify only demonstrable semantic defects and give concise evidence to the executor.",
        },
    }]
    evaluation.validate_candidate_case_scope(
        evaluation.candidate_by_id(matrix, "mimo-v2.6-flash-advisor-opus5.5"),
        [serialized_case],
    )
    try:
        evaluation.validate_candidate_case_scope(
            evaluation.candidate_by_id(matrix, "mimo-v2.6-flash-advisor-opus5.5"),
            [next(case for case in generalized if case["id"] != "serialized-marker-variant")],
        )
    except ValueError as exc:
        assert "evaluation-scoped" in str(exc)
    else:
        raise AssertionError("Advisor probe must fail closed outside its synthetic case allowlist")

    invalid_tool_candidate = dict(evaluation.candidate_by_id(matrix, "mimo-v2.6-flash"))
    invalid_tool_candidate["id"] = "invalid-tool"
    invalid_tool_candidate["tools"] = [{"type": "openrouter:shell"}]
    try:
        evaluation.build_payload(invalid_tool_candidate, serialized_case, system_prompt, schema, contract)
    except ValueError as exc:
        assert "openrouter:advisor" in str(exc)
    else:
        raise AssertionError("Non-Advisor server tools must fail closed in this evaluator")

    alias_advisor_candidate = dict(evaluation.candidate_by_id(matrix, "mimo-v2.6-flash"))
    alias_advisor_candidate["id"] = "alias-advisor"
    alias_advisor_candidate["tools"] = [{
        "type": "openrouter:advisor",
        "parameters": {"model": "~anthropic/claude-opus-latest"},
    }]
    try:
        evaluation.build_payload(alias_advisor_candidate, serialized_case, system_prompt, schema, contract)
    except ValueError as exc:
        assert "pinned non-alias" in str(exc)
    else:
        raise AssertionError("Mutable Advisor model aliases must fail closed")

    lane_case = next(case for case in naturalistic if case["id"] == "pr448-lane-separation-binding")
    assert "def _iter_clauses" in lane_case["source"]
    assert "def _clause_has_endpoint_lane" in lane_case["source"]
    assert "def _clause_has_local_lane" in lane_case["source"]
    assert "False accept:" in lane_case["counterexample"]
    assert "False reject:" in lane_case["counterexample"]
    assert "response scope" in lane_case["review_contract"]

    control = evaluation.candidate_by_id(matrix, "opus5-xhigh-control")
    control_payload = evaluation.build_payload(control, lane_case, system_prompt, schema, contract)
    assert control_payload["model"] == "anthropic/claude-opus-5"
    assert control_payload["provider"] == {
        "allow_fallbacks": True,
        "require_parameters": True,
        "sort": "price",
        "zdr": True,
        "data_collection": "deny",
    }
    assert control_payload["plugins"] == [{"id": "response-healing", "enabled": True}]
    assert control_payload["tools"] == []
    assert control_payload["stream"] is False
    assert control_payload["temperature"] == 0.2
    assert control_payload["reasoning"] == {"enabled": True, "effort": "xhigh", "exclude": True}
    assert control_payload["response_format"]["type"] == "json_schema"
    assert "max_tokens" not in control_payload
    assert "session_id" not in control_payload

    no_temp = evaluation.candidate_by_id(matrix, "opus5-xhigh-no-temp")
    no_temp_payload = evaluation.build_payload(no_temp, lane_case, system_prompt, schema, contract)
    assert no_temp_payload["model"] == "anthropic/claude-opus-5"
    assert no_temp_payload["provider"] == control_payload["provider"]
    assert no_temp_payload["plugins"] == control_payload["plugins"]
    assert no_temp_payload["reasoning"] == {"enabled": True, "effort": "xhigh", "exclude": True}
    assert "temperature" not in no_temp_payload
    assert "max_tokens" not in no_temp_payload
    assert no_temp_payload["response_format"]["type"] == "json_schema"
    assert "opus5-xhigh-no-temp" not in {
        item["id"] for item in evaluation.selected_candidates(matrix, "recommended")
    }

    compatibility_ids = {
        "opus5.5-xhigh-prod-temp",
        "sonnet5.5-high-prod-temp",
        "gpt6-astra-xhigh-prod-temp",
        "glm5.3-high-prod-temp",
        "gpt6-luna-high-prod-temp",
        "mimo-v2.6-flash-prod-high-temp",
    }
    assert compatibility_ids.isdisjoint({
        item["id"] for item in evaluation.selected_candidates(matrix, "recommended")
    })
    for compatibility_id in compatibility_ids:
        probe = evaluation.candidate_by_id(matrix, compatibility_id)
        probe_payload = evaluation.build_payload(probe, lane_case, system_prompt, schema, contract)
        assert probe_payload["temperature"] == 0.2
        assert probe_payload["reasoning"]["enabled"] is True
        assert probe_payload["reasoning"]["effort"] in {"high", "xhigh"}

    high = evaluation.candidate_by_id(matrix, "opus5-high")
    high_payload = evaluation.build_payload(high, lane_case, system_prompt, schema, contract)
    assert high_payload["reasoning"]["effort"] == "high"
    assert high_payload["temperature"] == 0.2
    sonnet = evaluation.candidate_by_id(matrix, "sonnet5-high")
    sonnet_payload = evaluation.build_payload(sonnet, lane_case, system_prompt, schema, contract)
    assert sonnet_payload["model"] == "anthropic/claude-sonnet-5"
    assert sonnet_payload["reasoning"]["effort"] == "high"
    assert "temperature" not in sonnet_payload

    auto = evaluation.candidate_by_id(matrix, "auto-max")
    auto_payload = evaluation.build_payload(auto, lane_case, system_prompt, schema, contract)
    assert auto_payload["model"] == "openrouter/auto"
    assert auto_payload["plugins"] == [
        {"id": "auto-router", "cost_tier": "max"},
        {"id": "response-healing", "enabled": True},
    ]
    assert "reasoning" not in auto_payload

    pareto = evaluation.candidate_by_id(matrix, "pareto-code-080")
    pareto_payload = evaluation.build_payload(pareto, lane_case, system_prompt, schema, contract)
    assert pareto_payload["plugins"] == [
        {"id": "pareto-router", "min_coding_score": 0.8},
        {"id": "response-healing", "enabled": True},
    ]

    duplicate_selector_failed = False
    try:
        evaluation.selected_candidates(matrix, "sonnet5-high,sonnet5-high")
    except ValueError:
        duplicate_selector_failed = True
    assert duplicate_selector_failed

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

    # Malformed responses and transport failures must remain reportable, with
    # billed usage preserved and without repeating the paid request.
    for broken_content in ("not json", "null", '{"wrong": []}'):
        malformed = dict(fake_payload)
        malformed["choices"] = [{"message": {"content": broken_content}}]
        failure = evaluation.call_openrouter(
            control_payload, "unit-test-key", timeout_seconds=9,
            opener=lambda *args, **kwargs: FakeResponse(malformed),
        )
        assert failure["ok"] is False
        assert failure["usage"]["cost_usd"] == 0.0125
    def timed_out(*args, **kwargs):
        raise TimeoutError("unit-test-key must never appear in report")
    failure = evaluation.call_openrouter(
        control_payload, "unit-test-key", timeout_seconds=9, opener=timed_out,
    )
    assert failure["ok"] is False
    assert "unit-test-key" not in json.dumps(failure)
    for malformed in (None, [], {"choices": []}, {"usage": {"cost": "bad"}}):
        failure = evaluation.call_openrouter(
            control_payload, "unit-test-key", timeout_seconds=9,
            opener=lambda *args, **kwargs: FakeResponse(malformed),
        )
        assert failure["ok"] is False
    passing_rows = [
        {"case_id": case["id"], "corpus": case["corpus"],
         "request": {"ok": True},
         "score": {"expected": case["expected"], "correct": True}}
        for case in cases
    ]
    assert evaluation.aggregate_candidate(control, passing_rows)["quality"]["acceptance_eligible_quality_floor"]
    for incomplete in ([], passing_rows[:1], passing_rows[:-1], passing_rows + passing_rows[:1]):
        assert not evaluation.aggregate_candidate(control, incomplete)["quality"]["acceptance_eligible_quality_floor"]

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

    billed_failure = {
        "case_id": lane_case["id"],
        "corpus": lane_case["corpus"],
        "defect_class": lane_case.get("defect_class"),
        "source_ref": lane_case.get("source_ref"),
        "historical_disposition": lane_case.get("dcoir_historical_disposition"),
        "request": {
            "ok": False,
            "latency_seconds": 1.25,
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 40,
                "reasoning_tokens": 12,
                "cached_prompt_tokens": 0,
                "cache_write_tokens": 0,
                "total_tokens": 140,
                "cost_usd": 0.004,
            },
        },
        "score": error_score,
    }
    billed_aggregate = evaluation.aggregate_candidate(control, [billed_failure])
    assert billed_aggregate["economics"]["request_count"] == 1
    assert billed_aggregate["economics"]["successful_request_count"] == 0
    assert billed_aggregate["economics"]["total_tokens"] == 140
    assert billed_aggregate["economics"]["exact_cost_usd"] == 0.004

    source_text = Path(evaluation.__file__).read_text(encoding="utf-8")
    assert "GITHUB_TOKEN" not in source_text
    assert "api.github.com" not in source_text
    assert "subprocess" not in source_text
    assert "pulls/" not in source_text
    assert "--execute-live" in source_text

    print(
        "dcoir_review_first_pass_candidate_eval_selftest passed: "
        "31 candidates, reusable groups/router plugins, 12 controlled cases, 4 frozen naturalistic cases, billed failures included, no network/publication"
    )


if __name__ == "__main__":
    main()
