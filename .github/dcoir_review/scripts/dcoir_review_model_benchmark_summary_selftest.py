#!/usr/bin/env python3
"""Deterministic self-test for DCOIR model benchmark summary rendering."""

from __future__ import annotations

from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import dcoir_review_model_benchmark_summary as target


def main() -> None:
    plan = target.render(
        {
            "mode": "plan-no-network",
            "no_publication": True,
            "candidate_ids": ["a", "b"],
            "case_counts": {"planned_total_requests": 28},
        }
    )
    assert "paid_network_calls: `0`" in plan
    assert "planned_requests_if_live: `28`" in plan

    live = target.render(
        {
            "mode": "live-no-publication",
            "no_publication": True,
            "candidates": [
                {
                    "candidate": {"id": "good", "benchmark_role": "routine"},
                    "quality": {
                        "acceptance_eligible_quality_floor": True,
                        "false_negative_case_ids": [],
                        "false_positive_case_ids": [],
                        "request_error_case_ids": [],
                    },
                    "economics": {
                        "exact_cost_usd": 0.01,
                        "serial_wall_seconds": 2.5,
                        "p50_request_seconds": 1.0,
                        "p95_request_seconds": 1.5,
                    },
                },
                {
                    "candidate": {"id": "cheap-but-misses", "benchmark_role": "routine"},
                    "quality": {
                        "acceptance_eligible_quality_floor": False,
                        "false_negative_case_ids": ["known-p1"],
                        "false_positive_case_ids": [],
                        "request_error_case_ids": [],
                    },
                    "economics": {
                        "exact_cost_usd": 0.0001,
                        "serial_wall_seconds": 0.5,
                        "p50_request_seconds": 0.5,
                        "p95_request_seconds": 0.5,
                    },
                },
            ],
        }
    )
    assert "| good | routine | PASS |" in live
    assert "| cheap-but-misses | routine | FAIL | 1 |" in live
    assert "p50 sec" in live and "p95 sec" in live
    assert "| good | routine | PASS | 0 | 0 | 0 | 0.010000 | 2.500 | 1.000 | 1.500 |" in live
    assert "quality floor passed" in live
    assert "does not change production models" in live
    print("dcoir_review_model_benchmark_summary_selftest passed")


if __name__ == "__main__":
    main()
