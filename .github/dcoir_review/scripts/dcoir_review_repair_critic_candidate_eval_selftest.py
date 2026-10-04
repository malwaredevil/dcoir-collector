#!/usr/bin/env python3
"""Offline regression checks for repair critic candidate benchmark."""

from __future__ import annotations

import dcoir_review_repair_critic_candidate_eval as target


def main() -> None:
    cases = target.load_cases()
    assert [case["id"] for case in cases] == [
        "critic-complete-accept",
        "critic-partial-reject",
        "critic-unnecessary-extra-reject",
    ]
    assert target.score_response(True, True) == {"correct": True, "unsafe_accept": False}
    assert target.score_response(True, False) == {"correct": False, "unsafe_accept": False}
    assert target.score_response(False, False) == {"correct": True, "unsafe_accept": False}
    assert target.score_response(False, True) == {"correct": False, "unsafe_accept": True}

    plan = target.plan(
        [{"id": "a", "model": "vendor/a"}, {"id": "b", "model": "vendor/b"}],
        cases,
    )
    assert plan["case_counts"]["selected_cases"] == 3
    assert plan["case_counts"]["planned_total_requests"] == 6

    complete = cases[0]["author"]["edits"]
    partial = cases[1]["author"]["edits"]
    extra = cases[2]["author"]["edits"]
    assert len(complete) == 2
    assert len(partial) == 1
    assert len(extra) == 3
    assert extra[-1]["start_line"] == 2

    print("dcoir_review_repair_critic_candidate_eval_selftest passed")


if __name__ == "__main__":
    main()
