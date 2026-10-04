#!/usr/bin/env python3
"""Offline regression checks for the DCOIR repair candidate benchmark."""

from __future__ import annotations

from types import SimpleNamespace

import dcoir_review_repair_candidate_eval as repair_eval


def main() -> None:
    cases = repair_eval.load_cases()
    assert [case["id"] for case in cases] == ["repair-upper-bound-one-line"]
    selected = repair_eval.select_cases(["repair-upper-bound-one-line"])
    assert len(selected) == 1
    plan = repair_eval.plan(
        [{"id": "a", "model": "vendor/a"}, {"id": "b", "model": "vendor/b"}],
        selected,
    )
    assert plan["case_counts"]["planned_total_requests"] == 4

    case = selected[0]
    repair = SimpleNamespace(REPAIR_MARKER="_repair")
    v36 = SimpleNamespace(REPAIR_SET_OUTCOME="verified-repair-set")
    item = {
        "_repair": {
            "outcome": "verified-repair-set",
            "critic_accepted": True,
            "author_model": "vendor/a",
            "critic_model": "vendor/b",
            "edits": [
                {
                    "path": case["path"],
                    "start_line": case["line"],
                    "end_line": case["line"],
                    "replacement": case["expected_replacement"],
                }
            ],
        }
    }
    score = repair_eval.score_item(item, case, repair, v36)
    assert score["correct"] is True and score["unsafe_accept"] is False

    bad = {
        "_repair": dict(
            item["_repair"],
            edits=[dict(item["_repair"]["edits"][0], replacement="    return True")],
        )
    }
    score = repair_eval.score_item(bad, case, repair, v36)
    assert score["correct"] is False and score["unsafe_accept"] is True
    print("dcoir_review_repair_candidate_eval_selftest passed")


if __name__ == "__main__":
    main()
