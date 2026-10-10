#!/usr/bin/env python3
"""Offline provenance and context-selection tests for Issue #618 replay corpus.

This only checks labeled evidence and prompt-context wiring. It does not run
models and must never claim a real reviewer recall improvement by itself.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from dcoir_review.cross_file_contract_context import build_cross_file_contract_context


def main() -> None:
    root = SCRIPT_DIR.parent
    path = root / "evaluation" / "cross_file_recall_corpus_v1.json"
    corpus = json.loads(path.read_text(encoding="utf-8"))
    assert corpus["schema_version"] == "dcoir_cross_file_review_cases_v1"
    cases = corpus.get("cases")
    assert isinstance(cases, list) and len(cases) >= 6
    lookup = {case["id"]: case for case in cases}
    assert len(lookup) == len(cases)
    assert sum(case["expected"] == "finding" for case in cases) >= 3
    assert sum(case["expected"] == "clean" for case in cases) >= 3

    missed = [case for case in cases if case["provenance"]["dcoir_review_result"] == "missed"]
    assert len(missed) == 1 and missed[0]["id"] == "stale-tracked-source-inventory-p1"
    not_reviewed = [
        case for case in cases
        if case["provenance"]["dcoir_review_result"] == "not_run_on_this_head"
    ]
    assert any(case["id"] == "git-unavailable-filesystem-fallback-p1" for case in not_reviewed)

    for case in cases:
        assert case["expected"] in {"finding", "clean"}
        assert case["defect_class"] and case["counterexample"] and case["supporting_contract"]
        assert case["provenance"]["pr"] in (613, 617)
        assert len(case["provenance"]["reviewed_head"]) == 40
        assert case["provenance"]["reference"].startswith(
            "https://github.com/malwaredevil/dcoir-collector/pull/"
        )
        assert case["changed_diff"].startswith("diff --git ")
        if case["expected"] == "finding":
            assert case["expected_anchor"]
            assert case["safe_control_id"] in lookup
            assert lookup[case["safe_control_id"]]["expected"] == "clean"
        else:
            assert case["severity"] == "none" and not case["expected_anchor"]

        context = build_cross_file_contract_context(
            case["focus_path"], case["changed_diff"]
        )
        assert len(context) <= 2200
        if case["related_path"]:
            assert json.dumps(case["related_path"]) in context
            assert "Do not report an issue solely from this list" in context

    print(
        "cross-file recall offline corpus passed: "
        f"{len(cases)} provenance-labeled cases, "
        f"{sum(c['expected'] == 'finding' for c in cases)} findings, "
        f"{sum(c['expected'] == 'clean' for c in cases)} safe controls"
    )


if __name__ == "__main__":
    main()
