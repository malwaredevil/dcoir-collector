#!/usr/bin/env python3
"""No-publication live benchmark for DCOIR Review repair author/critic routing.

Plan mode makes no network calls. Live mode runs a tiny controlled repair corpus
through the production repair-set author -> deterministic validation ->
independent critic path. It never publishes a GitHub review or mutates a branch.
"""

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


REPORT_SCHEMA = "dcoir_review_repair_candidate_eval_report_v1"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "openrouter-pr-review-pareto.yml"


def _fixture() -> dict[str, Any]:
    path = "evaluation/repair_probe.py"
    file_text = (
        "def is_recent(age_minutes: int) -> bool:\n"
        "    \"\"\"Return True when age_minutes is between 0 and 60 inclusive.\"\"\"\n"
        "    return age_minutes >= 0 and age_minutes >= 60\n"
    )
    return {
        "id": "repair-upper-bound-one-line",
        "path": path,
        "line": 3,
        "file_text": file_text,
        "expected_replacement": "    return age_minutes >= 0 and age_minutes <= 60",
        "diff": (
            "diff --git a/evaluation/repair_probe.py b/evaluation/repair_probe.py\n"
            "--- a/evaluation/repair_probe.py\n"
            "+++ b/evaluation/repair_probe.py\n"
            "@@ -1,3 +1,3 @@\n"
            " def is_recent(age_minutes: int) -> bool:\n"
            "     \"\"\"Return True when age_minutes is between 0 and 60 inclusive.\"\"\"\n"
            "+    return age_minutes >= 0 and age_minutes >= 60\n"
        ),
    }


def load_cases() -> list[dict[str, Any]]:
    return [_fixture()]


def select_cases(requested: list[str]) -> list[dict[str, Any]]:
    cases = load_cases()
    if not requested:
        return cases
    by_id = {case["id"]: case for case in cases}
    selected: list[dict[str, Any]] = []
    for case_id in requested:
        if case_id not in by_id:
            raise ValueError(f"Unknown repair benchmark case id: {case_id}")
        selected.append(dict(by_id[case_id]))
    if len({case["id"] for case in selected}) != len(selected):
        raise ValueError("Repair case selection contains duplicate ids")
    return selected


def _candidate_config(review: Any, candidate: dict[str, Any]) -> Any:
    model = str(candidate.get("model", "") or "").strip()
    if not model or model.startswith("openrouter/"):
        raise ValueError(f"Repair benchmark requires a pinned direct model id: {candidate.get('id')}")
    if candidate.get("tools") or candidate.get("plugins"):
        raise ValueError(f"Repair benchmark does not enable candidate tools/plugins: {candidate.get('id')}")
    config = copy.copy(review.load_pareto_context_config(str(CONFIG_PATH)))
    config.model = model
    config.model_stack = [model]
    effort = str(candidate.get("reasoning_effort", "") or "").strip()
    if effort:
        config.review_reasoning_effort = effort
    config.openrouter_session_id_prefix = "dcoir-review-repair-benchmark"
    config.debug = False
    return config


def _verified_finding(v21: Any, case: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": "Upper-bound comparison is inverted",
        "severity": "high",
        "confidence": 1.0,
        "path": case["path"],
        "line": case["line"],
        "body": "The documented inclusive 0..60 range is contradicted by a >= 60 upper-bound comparison.",
        "suggested_replacement": "",
        "validation": "python -m py_compile evaluation/repair_probe.py",
        v21.VERIFIER_MARKER: {
            "mode": "model-judge",
            "supported": True,
            "confidence": 0.99,
            "evidence": "The docstring requires 0 through 60 inclusive, but the changed line uses age_minutes >= 60.",
            "reason": "The changed line contradicts the local function contract.",
            "model_used": "benchmark-verifier",
            "head_sha": "benchmark-head",
            "line": case["line"],
        },
    }


def score_item(item: dict[str, Any], case: dict[str, Any], repair: Any, v36: Any) -> dict[str, Any]:
    marker = item.get(repair.REPAIR_MARKER) if isinstance(item.get(repair.REPAIR_MARKER), dict) else {}
    outcome = str(marker.get("outcome", "") or "")
    edits = marker.get("edits") if isinstance(marker.get("edits"), list) else []
    expected = case["expected_replacement"]
    correct_edit = (
        outcome == v36.REPAIR_SET_OUTCOME
        and bool(marker.get("critic_accepted"))
        and len(edits) == 1
        and edits[0].get("path") == case["path"]
        and int(edits[0].get("start_line", 0) or 0) == case["line"]
        and int(edits[0].get("end_line", 0) or 0) == case["line"]
        and edits[0].get("replacement") == expected
    )
    unsafe_accept = outcome == v36.REPAIR_SET_OUTCOME and not correct_edit
    return {
        "correct": correct_edit,
        "unsafe_accept": unsafe_accept,
        "outcome": outcome,
        "author_model": str(marker.get("author_model", "") or ""),
        "critic_model": str(marker.get("critic_model", "") or ""),
        "critic_accepted": bool(marker.get("critic_accepted", False)),
        "reason": str(marker.get("reason", "") or "")[:800],
        "edit_count": len(edits),
        "edits": edits,
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


def _run_case(review: Any, v21: Any, repair: Any, v36: Any, candidate: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    config = _candidate_config(review, candidate)
    file_map = {case["path"]: case["file_text"]}
    original_fetch = review.fetch_pr_file_text
    original_debug = review.hardened.write_debug_json_artifact_safely
    review.fetch_pr_file_text = lambda _gh, path, _head: file_map[path]
    review.hardened.write_debug_json_artifact_safely = lambda *args, **kwargs: None
    started = time.monotonic()
    try:
        right_index = review.base.build_diff_line_index(case["diff"])
        item = v36._build_repair_set_for_finding(
            review,
            1,
            _verified_finding(v21, case),
            object(),
            "benchmark-head",
            case["diff"],
            right_index,
            config,
            dict(file_map),
        )
        score = score_item(item, case, repair, v36)
        error = ""
    except Exception as exc:
        item = {}
        score = {"correct": False, "unsafe_accept": False, "outcome": "request-error", "reason": type(exc).__name__}
        error = type(exc).__name__
    finally:
        review.fetch_pr_file_text = original_fetch
        review.hardened.write_debug_json_artifact_safely = original_debug
    elapsed = time.monotonic() - started
    return {
        "case_id": case["id"],
        "ok": not bool(error),
        "error": error,
        "latency_seconds": elapsed,
        "score": score,
        "result_marker": item.get(repair.REPAIR_MARKER, {}) if isinstance(item, dict) else {},
    }


def run_live(candidates: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    if not os.environ.get("OPENROUTER_API_KEY", "").strip():
        raise RuntimeError("OPENROUTER_API_KEY is required only for --execute-live")
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    v21 = importlib.import_module("dcoir_review.finding_verifier")
    repair = importlib.import_module("dcoir_review.repair_pipeline")
    v36 = importlib.import_module("dcoir_review_required_runtime_patch_v36")

    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        case_results = [_run_case(review, v21, repair, v36, candidate, case) for case in cases]
        failures = [r["case_id"] for r in case_results if not r["score"].get("correct") and not r["score"].get("unsafe_accept") and not r.get("error")]
        unsafe = [r["case_id"] for r in case_results if r["score"].get("unsafe_accept")]
        errors = [r["case_id"] for r in case_results if r.get("error")]
        latencies = [float(r["latency_seconds"]) for r in case_results]
        rows.append(
            {
                "candidate": {
                    "id": candidate["id"],
                    "model": candidate["model"],
                    "benchmark_role": "repair-author-with-production-independent-critic",
                },
                "case_results": case_results,
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
        "benchmark_stage": "repair",
        "mode": "live-no-publication",
        "no_publication": True,
        "candidates": rows,
    }


def plan(candidates: list[dict[str, Any]], cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA,
        "benchmark_stage": "repair",
        "mode": "plan-no-network",
        "no_publication": True,
        "candidate_ids": [str(candidate["id"]) for candidate in candidates],
        "case_ids": [str(case["id"]) for case in cases],
        "case_counts": {
            "selected_cases": len(cases),
            "planned_total_requests": len(candidates) * len(cases) * 2,
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
    del args.timeout_seconds

    matrix = first_pass.load_matrix()
    candidates = first_pass.selected_candidates(matrix, args.candidate)
    cases = select_cases([str(item).strip() for item in args.case if str(item).strip()])
    report = run_live(candidates, cases) if args.execute_live else plan(candidates, cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
