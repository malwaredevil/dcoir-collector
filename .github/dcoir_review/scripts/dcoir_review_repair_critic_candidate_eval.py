#!/usr/bin/env python3
"""No-publication live benchmark for DCOIR Review repair critic candidates."""

from __future__ import annotations

import argparse
import copy
import importlib
import json
import os
from pathlib import Path
import statistics
import time
from typing import Any

from dcoir_review.entrypoint import DcoirReviewEntrypoint
import dcoir_review_first_pass_candidate_eval as first_pass
import dcoir_review_repair_candidate_eval as repair_eval


REPORT_SCHEMA = "dcoir_review_repair_critic_candidate_eval_report_v1"


def _fixture() -> dict[str, Any]:
    return repair_eval.select_cases(["repair-coordinated-two-edit"])[0]


def _author_base(case: dict[str, Any], edits: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "defect_present": True,
        "action": "repair_set",
        "edits": edits,
        "confidence": 0.99,
        "display_title": case["title"],
        "display_body": case["body"],
        "rationale": "Controlled repair candidate for critic evaluation.",
        "validation": case["validation"],
    }


def load_cases() -> list[dict[str, Any]]:
    case = _fixture()
    source_lines = case["files"][case["path"]].splitlines()
    complete = [
        dict(
            edit,
            original=source_lines[int(edit["start_line"]) - 1],
            purpose="Required repair edit.",
        )
        for edit in case["expected_edits"]
    ]
    partial = complete[:1]
    extra = list(complete)
    extra.append(
        {
            "path": case["path"],
            "start_line": 2,
            "end_line": 2,
            "original": '    """Return True when cache age is between 0 and 60 inclusive."""',
            "replacement": '    """Return True when cache age is within the inclusive 0..60 range."""',
            "purpose": "Unnecessary wording cleanup unrelated to the verified defect.",
        }
    )
    return [
        {
            "id": "critic-complete-accept",
            "expected_accept": True,
            "author": _author_base(case, complete),
            "case": case,
        },
        {
            "id": "critic-partial-reject",
            "expected_accept": False,
            "author": _author_base(case, partial),
            "case": case,
        },
        {
            "id": "critic-unnecessary-extra-reject",
            "expected_accept": False,
            "author": _author_base(case, extra),
            "case": case,
        },
    ]


def select_cases(requested: list[str]) -> list[dict[str, Any]]:
    cases = load_cases()
    if not requested:
        return cases
    by_id = {case["id"]: case for case in cases}
    selected: list[dict[str, Any]] = []
    for case_id in requested:
        if case_id not in by_id:
            raise ValueError(f"Unknown repair critic benchmark case id: {case_id}")
        selected.append(by_id[case_id])
    if len({case["id"] for case in selected}) != len(selected):
        raise ValueError("Repair critic case selection contains duplicate ids")
    return selected


def _candidate_config(review: Any, candidate: dict[str, Any]) -> Any:
    config = copy.copy(repair_eval._candidate_config(review, candidate))
    config.model = str(candidate["model"])
    config.model_stack = [str(candidate["model"])]
    if hasattr(config, "fallback_models"):
        config.fallback_models = []
    if hasattr(config, "openrouter_route"):
        config.openrouter_route = ""
    if hasattr(config, "openrouter_service_tier"):
        config.openrouter_service_tier = ""
    config.openrouter_session_id_prefix = "dcoir-review-repair-critic-benchmark"
    return config


def score_response(expected_accept: bool, accepted: bool) -> dict[str, bool]:
    return {
        "correct": accepted is expected_accept,
        "unsafe_accept": accepted and not expected_accept,
    }


def _run_case(
    review: Any,
    v21: Any,
    v36: Any,
    candidate: dict[str, Any],
    spec: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    case = spec["case"]
    config = _candidate_config(review, candidate)
    config.openrouter_request_timeout_seconds = timeout_seconds
    finding = repair_eval._verified_finding(v21, case)
    author = spec["author"]
    file_cache = dict(case["files"])
    prompt = v36._repair_critic_prompt(review, finding, author, file_cache, config)
    original_builder = review.hardened.build_openrouter_payload
    review.hardened.build_openrouter_payload = repair_eval._candidate_payload_builder(original_builder, candidate)
    started = time.monotonic()
    try:
        raw, model_used, service_tier = review.hardened.openrouter_review(
            prompt,
            v36.REPAIR_SET_CRITIC_SCHEMA,
            config,
            reporter=None,
        )
        accepted, confidence, reason = v36._parse_critic(raw, review.hardened)
        scored = score_response(bool(spec["expected_accept"]), accepted)
        error = ""
    except Exception as exc:
        raw = {}
        model_used = ""
        service_tier = ""
        accepted = False
        confidence = 0.0
        reason = f"{type(exc).__name__}: {str(exc)[:500]}"
        scored = {"correct": False, "unsafe_accept": False}
        error = reason
    finally:
        review.hardened.build_openrouter_payload = original_builder
    elapsed = time.monotonic() - started
    return {
        "case_id": spec["id"],
        "expected_accept": bool(spec["expected_accept"]),
        "accepted": bool(accepted),
        "confidence": float(confidence),
        "reason": str(reason or "")[:1200],
        "model_used": str(model_used or ""),
        "service_tier": str(service_tier or ""),
        "latency_seconds": elapsed,
        "error": error,
        "raw": raw,
        "score": scored,
    }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * pct
    lo = int(index)
    hi = min(lo + 1, len(ordered) - 1)
    fraction = index - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * fraction


def run_live(
    candidates: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    if timeout_seconds <= 0:
        raise ValueError("Request timeout must be a positive number of seconds")
    if not os.environ.get("OPENROUTER_API_KEY", "").strip():
        raise RuntimeError("OPENROUTER_API_KEY is required only for --execute-live")
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    v21 = importlib.import_module("dcoir_review.finding_verifier")
    v36 = importlib.import_module("dcoir_review_required_runtime_patch_v36")

    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        results = [
            _run_case(review, v21, v36, candidate, spec, timeout_seconds)
            for spec in cases
        ]
        failures = [
            row["case_id"]
            for row in results
            if not row["score"]["correct"] and not row["score"]["unsafe_accept"] and not row["error"]
        ]
        unsafe = [row["case_id"] for row in results if row["score"]["unsafe_accept"]]
        errors = [row["case_id"] for row in results if row["error"]]
        latencies = [float(row["latency_seconds"]) for row in results]
        rows.append(
            {
                "candidate": {
                    "id": candidate["id"],
                    "model": candidate["model"],
                    "benchmark_role": "repair-critic-direct",
                },
                "case_results": results,
                "quality": {
                    "acceptance_eligible_quality_floor": not failures and not unsafe and not errors,
                    "repair_failure_case_ids": failures,
                    "unsafe_accept_case_ids": unsafe,
                    "request_error_case_ids": errors,
                },
                "economics": {
                    "cost_measured": False,
                    "exact_cost_usd": 0.0,
                    "serial_wall_seconds": sum(latencies),
                    "p50_request_seconds": statistics.median(latencies) if latencies else 0.0,
                    "p95_request_seconds": _percentile(latencies, 0.95),
                },
            }
        )
    return {
        "schema_version": REPORT_SCHEMA,
        "benchmark_stage": "repair-critic",
        "mode": "live-no-publication",
        "no_publication": True,
        "candidates": rows,
    }


def plan(candidates: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA,
        "benchmark_stage": "repair-critic",
        "mode": "plan-no-network",
        "no_publication": True,
        "candidate_ids": [str(candidate["id"]) for candidate in candidates],
        "case_ids": [str(case["id"]) for case in cases],
        "case_counts": {
            "selected_cases": len(cases),
            "planned_total_requests": len(candidates) * len(cases),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be a positive number of seconds")

    matrix = first_pass.load_matrix()
    candidates = first_pass.selected_candidates(matrix, args.candidate)
    cases = select_cases([str(item).strip() for item in args.case if str(item).strip()])
    report = (
        run_live(candidates, cases, timeout_seconds=args.timeout_seconds)
        if args.execute_live
        else plan(candidates, cases)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
