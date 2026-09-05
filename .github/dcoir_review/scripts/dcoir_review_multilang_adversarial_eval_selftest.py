#!/usr/bin/env python3
"""Deterministic no-network selftest for dcoir_review_multilang_adversarial_eval.py."""

from __future__ import annotations

import json

import dcoir_review_first_pass_candidate_eval as base
import dcoir_review_multilang_adversarial_eval as target


def ok_result(*findings: dict) -> dict:
    return {
        "ok": True,
        "latency_seconds": 0.01,
        "selected_provider": "fixture-provider",
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "reasoning_tokens": 2,
            "cached_prompt_tokens": 0,
            "cache_write_tokens": 0,
            "total_tokens": 15,
            "cost_usd": 0.001,
        },
        "result": {"summary": "fixture", "findings": list(findings)},
    }


def finding(text: str) -> dict:
    return {
        "title": text,
        "severity": "high",
        "confidence": 0.99,
        "path": "evaluation/fixture",
        "line": 1,
        "body": text,
        "validation": text,
        "suggested_replacement": "",
    }


def main() -> int:
    corpus, cases = target.load_cases()
    assert corpus["schema_version"] == target.CORPUS_SCHEMA
    assert len(cases) == 40
    assert sum(case["expected"] == "finding" for case in cases) == 30
    assert sum(case["expected"] == "clean" for case in cases) == 10
    assert sum(case["difficulty"] in {"hard", "adversarial"} for case in cases) == 29

    by_id = {case["id"]: case for case in cases}
    ps_case = by_id["ps-contains-direction-membership"]
    prompt = target.build_case_prompt(ps_case)
    assert ps_case["review_contract"] in prompt
    assert ps_case["counterexample"] in prompt
    assert ps_case["ground_truth_rationale"] not in prompt
    assert "ground_truth_rationale" not in prompt
    assert "expected disposition" in prompt.lower()  # instruction says not to mention it, but does not reveal its value.
    assert "Synthetic evaluation path: src/Test-RoleAllowed.ps1" in prompt

    matrix = base.load_matrix()
    request_contract = matrix["request_contract"]
    system_prompt = base.SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    review_schema = base.load_json(base.REVIEW_SCHEMA_PATH)
    sonnet = base.candidate_by_id(matrix, "sonnet5-high")
    opus = base.candidate_by_id(matrix, "opus5-xhigh-control")
    sonnet_payload = target.build_payload(sonnet, ps_case, system_prompt, review_schema, request_contract, max_tokens_override=32768)
    opus_payload = target.build_payload(opus, ps_case, system_prompt, review_schema, request_contract)
    assert sonnet_payload["model"] == "anthropic/claude-sonnet-5"
    assert sonnet_payload["reasoning"]["effort"] == "high"
    assert sonnet_payload["max_tokens"] == 32768
    assert "temperature" not in sonnet_payload
    assert sonnet_payload["provider"]["sort"] == "price"
    assert sonnet_payload["provider"]["require_parameters"] is True
    assert sonnet_payload["tools"] == []
    assert opus_payload["temperature"] == 0.2
    assert opus_payload["reasoning"]["effort"] == "xhigh"
    assert "max_tokens" not in opus_payload

    good = target.score_case(
        ps_case,
        ok_result(finding("PowerShell -contains membership uses the wrong direction: AllowedRoles collection must be on the left.")),
    )
    assert good["correct"] is True and good["disposition"] == "finding-detected"

    unrelated = target.score_case(ps_case, ok_result(finding("This function could use a shorter parameter name.")))
    assert unrelated["correct"] is False
    assert unrelated["ambiguous"] is True
    assert unrelated["disposition"] == "finding-present-but-contract-match-needs-review"

    extras = target.score_case(
        ps_case,
        ok_result(
            finding("PowerShell -contains membership direction is reversed for the AllowedRoles collection."),
            finding("Unrelated style concern."),
        ),
    )
    assert extras["correct"] is False and extras["disposition"] == "extra-findings"

    clean_case = by_id["ps-clean-collection-membership"]
    clean = target.score_case(clean_case, ok_result())
    assert clean["correct"] is True and clean["disposition"] == "clean"
    false_positive = target.score_case(clean_case, ok_result(finding("Invented issue")))
    assert false_positive["correct"] is False and false_positive["disposition"] == "false-positive"

    ps_cases = target.select_cases(cases, case_ids=[], surfaces=["powershell"], difficulties=[])
    assert len(ps_cases) == 12
    hard_ps = target.select_cases(cases, case_ids=[], surfaces=["powershell"], difficulties=["hard", "adversarial"])
    assert len(hard_ps) == 8
    one = target.select_cases(cases, case_ids=["py-head-checked-only-before-long-review"], surfaces=[], difficulties=[])
    assert [case["id"] for case in one] == ["py-head-checked-only-before-long-review"]

    rows = [
        {
            "expected": "finding",
            "score": good,
            "request": ok_result(finding("PowerShell -contains membership uses the wrong direction: AllowedRoles collection must be on the left.")),
        },
        {"expected": "clean", "score": clean, "request": ok_result()},
    ]
    summary = target.aggregate_candidate(sonnet, rows)
    assert summary["total_cases"] == 2
    assert summary["correct_cases"] == 2
    assert summary["known_defects_detected"] == 1
    assert summary["known_defects_total"] == 1
    assert summary["clean_controls_correct"] == 1
    assert summary["clean_controls_total"] == 1
    assert summary["usage"]["total_tokens"] == 30
    assert abs(summary["exact_cost_usd"] - 0.002) < 1e-12

    print(json.dumps({"status": "pass", "cases": len(cases), "network_requests_made": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
