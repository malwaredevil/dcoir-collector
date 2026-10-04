#!/usr/bin/env python3
"""Offline regression checks for the DCOIR repair candidate benchmark."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_repair_candidate_eval as repair_eval


def _marker_from_expected(case):
    return {
        "outcome": "verified-repair-set",
        "critic_accepted": True,
        "author_model": "vendor/a",
        "critic_model": "vendor/b",
        "edits": [
            {
                "path": edit["path"],
                "start_line": edit["start_line"],
                "end_line": edit["end_line"],
                "replacement": edit["replacement"],
            }
            for edit in case["expected_edits"]
        ],
    }


def main() -> None:
    cases = repair_eval.load_cases()
    assert [case["id"] for case in cases] == [
        "repair-upper-bound-one-line",
        "repair-coordinated-two-edit",
    ]

    selected = repair_eval.select_cases(["repair-coordinated-two-edit"])
    assert len(selected) == 1
    assert len(selected[0]["expected_edits"]) == 2

    plan = repair_eval.plan(
        [{"id": "a", "model": "vendor/a"}, {"id": "b", "model": "vendor/b"}],
        selected,
    )
    assert plan["case_counts"]["planned_total_requests"] == 4

    repair = SimpleNamespace(REPAIR_MARKER="_repair")
    v36 = SimpleNamespace(REPAIR_SET_OUTCOME="verified-repair-set")

    for case in cases:
        item = {"_repair": _marker_from_expected(case)}
        score = repair_eval.score_item(item, case, repair, v36)
        assert score["correct"] is True and score["unsafe_accept"] is False

        partial_edits = list(item["_repair"]["edits"][:-1])
        bad = {"_repair": dict(item["_repair"], edits=partial_edits)}
        score = repair_eval.score_item(bad, case, repair, v36)
        assert score["correct"] is False and score["unsafe_accept"] is True

    print("dcoir_review_repair_candidate_eval_selftest passed")


if __name__ == "__main__":
    main()
