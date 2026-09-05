#!/usr/bin/env python3
"""No-publication DCOIR first-pass output-budget evaluation harness.

This runner reuses the frozen first-pass candidate corpus and request construction
from ``dcoir_review_first_pass_candidate_eval.py`` while adding an explicit
per-request ``max_tokens`` ceiling and fail-closed completion handling.

Normal invocation is plan-only and makes zero network calls. ``--execute-live``
uses OpenRouter inference only, writes a local JSON report, and has no GitHub
publication or repository mutation path. Paid/live execution remains separately
operator controlled.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
import urllib.error
import urllib.request


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import dcoir_review_first_pass_candidate_eval as base


POLICY_PATH = base.DCOIR_ROOT / "evaluation" / "first_pass_output_budget_experiment_v1.json"
REPORT_SCHEMA = "dcoir_review_first_pass_budget_eval_report_v1"


def load_policy() -> dict[str, Any]:
    policy = base.load_json(POLICY_PATH)
    if policy.get("schema_version") != "dcoir_review_first_pass_output_budget_experiment_v1":
        raise ValueError("Unexpected first-pass output-budget policy schema")
    selected = policy.get("selected_candidate_for_budget_test")
    if not isinstance(selected, dict):
        raise ValueError("Output-budget policy has no selected candidate")
    max_tokens = int(selected.get("max_tokens", 0) or 0)
    if max_tokens <= 0:
        raise ValueError("Output-budget policy max_tokens must be positive")
    return policy


def budgeted_candidate(candidate: dict[str, Any], max_tokens: int) -> dict[str, Any]:
    max_tokens_int = int(max_tokens)
    if max_tokens_int <= 0:
        raise ValueError("max_tokens must be positive")
    result = dict(candidate)
    result["max_tokens"] = max_tokens_int
    return result


def _metadata(data: dict[str, Any]) -> dict[str, Any]:
    value = data.get("openrouter_metadata")
    return value if isinstance(value, dict) else {}


def _finish_reason(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    return str(choices[0].get("finish_reason", "") or "").strip().lower()


def _failure_result(
    *,
    error_type: str,
    message: str,
    status: int,
    elapsed: float,
    payload: dict[str, Any],
    data: dict[str, Any] | None = None,
    finish_reason: str = "",
) -> dict[str, Any]:
    response_data = data if isinstance(data, dict) else {}
    metadata = _metadata(response_data)
    result: dict[str, Any] = {
        "ok": False,
        "http_status": int(status),
        "latency_seconds": elapsed,
        "error_type": error_type,
        "error": message,
        "requested_model": str(payload.get("model", "") or ""),
        "selected_provider": base.selected_provider(metadata),
        "openrouter_metadata": metadata,
        "pipeline": base.pipeline_summary(metadata),
        "finish_reason": finish_reason,
    }
    if response_data:
        result["served_model"] = str(response_data.get("model", payload.get("model", "")) or "")
        result["generation_id"] = str(response_data.get("id", "") or "")
        result["usage"] = base.usage_summary(response_data)
    return result


def call_openrouter_budgeted(
    payload: dict[str, Any],
    api_key: str,
    *,
    timeout_seconds: int,
    opener: Any = urllib.request.urlopen,
) -> dict[str, Any]:
    """Call OpenRouter and fail closed on budget exhaustion or bad structure."""

    if "max_tokens" not in payload or int(payload.get("max_tokens", 0) or 0) <= 0:
        raise ValueError("Budgeted request requires positive max_tokens")

    started = time.monotonic()
    request = urllib.request.Request(
        base.OPENROUTER_API,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=base.request_headers(api_key),
    )
    try:
        with opener(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            status = int(getattr(response, "status", 200) or 200)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        elapsed = time.monotonic() - started
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
        error_value = data.get("error") if isinstance(data, dict) else None
        if isinstance(error_value, dict):
            message = str(error_value.get("message", error_value) or "")
        else:
            message = str(error_value or raw[:1000])
        return _failure_result(
            error_type="http-error",
            message=message,
            status=int(exc.code),
            elapsed=elapsed,
            payload=payload,
            data=data if isinstance(data, dict) else None,
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return _failure_result(
            error_type="transport-error",
            message=str(exc),
            status=0,
            elapsed=time.monotonic() - started,
            payload=payload,
        )

    elapsed = time.monotonic() - started
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _failure_result(
            error_type="invalid-response-json",
            message=f"OpenRouter response was not valid JSON: {exc}",
            status=status,
            elapsed=elapsed,
            payload=payload,
        )
    if not isinstance(data, dict):
        return _failure_result(
            error_type="invalid-response-json",
            message="OpenRouter response root is not a JSON object",
            status=status,
            elapsed=elapsed,
            payload=payload,
        )

    finish_reason = _finish_reason(data)
    if finish_reason == "length":
        return _failure_result(
            error_type="output-budget-exhausted",
            message="Completion stopped because the output-token budget was exhausted",
            status=status,
            elapsed=elapsed,
            payload=payload,
            data=data,
            finish_reason=finish_reason,
        )
    if finish_reason != "stop":
        return _failure_result(
            error_type="non-stop-finish-reason",
            message=f"Completion did not finish with stop: {finish_reason or 'missing'}",
            status=status,
            elapsed=elapsed,
            payload=payload,
            data=data,
            finish_reason=finish_reason,
        )

    try:
        parsed = base.parse_content(data)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return _failure_result(
            error_type="invalid-structured-output",
            message=str(exc),
            status=status,
            elapsed=elapsed,
            payload=payload,
            data=data,
            finish_reason=finish_reason,
        )

    metadata = _metadata(data)
    return {
        "ok": True,
        "http_status": status,
        "latency_seconds": elapsed,
        "generation_id": str(data.get("id", "") or ""),
        "requested_model": str(payload.get("model", "") or ""),
        "served_model": str(data.get("model", payload.get("model", "")) or ""),
        "selected_provider": base.selected_provider(metadata),
        "openrouter_metadata": metadata,
        "pipeline": base.pipeline_summary(metadata),
        "usage": base.usage_summary(data),
        "finish_reason": finish_reason,
        "result": parsed,
    }


def selected_cases(matrix: dict[str, Any], case_ids: list[str]) -> list[dict[str, Any]]:
    cases = base.load_cases(matrix)
    if not case_ids:
        return cases
    wanted = set(case_ids)
    available = {str(item["id"]) for item in cases}
    missing = sorted(wanted - available)
    if missing:
        raise ValueError(f"Unknown case id(s): {', '.join(missing)}")
    return [item for item in cases if item["id"] in wanted]


def plan_report(
    matrix: dict[str, Any],
    cases: list[dict[str, Any]],
    candidate: dict[str, Any],
    max_tokens: int,
    policy: dict[str, Any],
) -> dict[str, Any]:
    generalized = [case for case in cases if case["corpus"] == "generalized-controlled"]
    naturalistic = [case for case in cases if case["corpus"] == "naturalistic-known-defect"]
    return {
        "schema_version": REPORT_SCHEMA,
        "mode": "plan-no-network",
        "no_publication": True,
        "network_calls": 0,
        "stage": policy["stage"],
        "candidate": budgeted_candidate(candidate, max_tokens),
        "max_tokens": int(max_tokens),
        "case_counts": {
            "generalized_controlled": len(generalized),
            "naturalistic_known_defects": len(naturalistic),
            "total": len(cases),
        },
        "fail_closed_contract": policy["fail_closed_contract"],
        "request_contract": matrix["request_contract"],
    }


def run_live(
    matrix: dict[str, Any],
    cases: list[dict[str, Any]],
    candidate: dict[str, Any],
    *,
    max_tokens: int,
    timeout_seconds: int,
    policy: dict[str, Any],
) -> dict[str, Any]:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required only for --execute-live")

    bounded_candidate = budgeted_candidate(candidate, max_tokens)
    system_prompt = base.SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    review_schema = base.load_json(base.REVIEW_SCHEMA_PATH)
    request_contract = matrix["request_contract"]
    started = time.time()
    case_results: list[dict[str, Any]] = []

    for case in cases:
        payload = base.build_payload(
            bounded_candidate,
            case,
            system_prompt,
            review_schema,
            request_contract,
        )
        request_result = call_openrouter_budgeted(
            payload,
            api_key,
            timeout_seconds=timeout_seconds,
        )
        score = base.score_case(case, request_result)
        case_results.append(
            {
                "case_id": case["id"],
                "corpus": case["corpus"],
                "defect_class": case.get("defect_class"),
                "source_ref": case.get("source_ref"),
                "historical_disposition": case.get("dcoir_historical_disposition"),
                "request": request_result,
                "score": score,
            }
        )

    aggregate = base.aggregate_candidate(bounded_candidate, case_results)
    aggregate["budget_failures"] = {
        "output_budget_exhausted_case_ids": [
            item["case_id"]
            for item in case_results
            if item["request"].get("error_type") == "output-budget-exhausted"
        ],
        "invalid_structured_output_case_ids": [
            item["case_id"]
            for item in case_results
            if item["request"].get("error_type") in {"invalid-response-json", "invalid-structured-output"}
        ],
        "non_stop_finish_reason_case_ids": [
            item["case_id"]
            for item in case_results
            if item["request"].get("error_type") == "non-stop-finish-reason"
        ],
    }
    return {
        "schema_version": REPORT_SCHEMA,
        "mode": "live-no-publication",
        "no_publication": True,
        "stage": policy["stage"],
        "max_tokens": int(max_tokens),
        "fail_closed_contract": policy["fail_closed_contract"],
        "request_contract": request_contract,
        "started_epoch_seconds": started,
        "completed_epoch_seconds": time.time(),
        "candidate": aggregate,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    policy = load_policy()
    selected = policy["selected_candidate_for_budget_test"]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        default=str(selected["candidate_id"]),
        help="Candidate id from first_pass_candidate_matrix_v1.json.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=int(selected["max_tokens"]),
        help="Positive first-pass completion-token ceiling.",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="Optional case id filter. Repeat to select multiple cases.",
    )
    parser.add_argument(
        "--execute-live",
        action="store_true",
        help="Actually call OpenRouter. Paid/live use requires separate operator approval.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.max_tokens <= 0:
        raise SystemExit("--max-tokens must be positive")

    policy = load_policy()
    matrix = base.load_matrix()
    candidate = base.candidate_by_id(matrix, args.candidate)
    cases = selected_cases(matrix, args.case)
    if not cases:
        raise SystemExit("No evaluation cases selected")

    if args.execute_live:
        report = run_live(
            matrix,
            cases,
            candidate,
            max_tokens=args.max_tokens,
            timeout_seconds=max(1, args.timeout_seconds),
            policy=policy,
        )
    else:
        report = plan_report(matrix, cases, candidate, args.max_tokens, policy)

    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
