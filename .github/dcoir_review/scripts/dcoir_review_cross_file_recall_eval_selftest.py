#!/usr/bin/env python3
"""Offline selftests for the #618 paired per-file OpenRouter evaluation harness."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import dcoir_review_cross_file_recall_eval as evaluation


def sample_finding(case: dict, *, path: str | None = None, line: int | None = None, text: str | None = None):
    candidates = evaluation.mutation.added_lines(evaluation.focus_patch(case))
    target = next(number for number, source in candidates if case["expected_anchor"] in source)
    return {
        "title": "Synthetic regression",
        "body": text if text is not None else " ".join(group[0] for group in case["match_groups"]),
        "validation": "Check the failing counterexample.",
        "path": case["focus_path"] if path is None else path,
        "line": target if line is None else line,
        "severity": "high" if case["severity"] == "P1" else "medium",
        "suggested_replacement": "",
    }


def main() -> int:
    cases = evaluation.load_cases()
    assert len(cases) == 6
    config = evaluation.review.load_pareto_context_config(
        str(evaluation.DCOIR_ROOT / "openrouter-pr-review-pareto.yml")
    )
    positives = [case for case in cases if case["expected"] == "finding"]
    clean = [case for case in cases if case["expected"] == "clean"]
    for case in cases:
        pair = evaluation.prompts(case, config)
        assert pair["baseline"] and pair["enhanced"]
        assert "supporting_contract" not in pair["enhanced"]
        assert "ground_truth_rationale" not in pair["enhanced"]
        assert len(pair["enhanced"]) < 120000
        if case["related_path"]:
            assert pair["baseline"] != pair["enhanced"]
            assert "Cross-file contract review cues" in pair["enhanced"]
            assert "Cross-file contract review cues" not in pair["baseline"]
            assert len(pair["enhanced"]) - len(pair["baseline"]) <= 2200 + 4
        else:
            assert pair["baseline"] == pair["enhanced"]
    for case in positives:
        good = sample_finding(case)
        assert evaluation.score(case, {"ok": True, "result": {"findings": [good]}})["correct"]
        assert not evaluation.score(case, {"ok": True, "result": {"findings": [good, good]}})["correct"]
        if case["severity"] == "P1":
            too_low = dict(good, severity="low")
            assert not evaluation.score(case, {"ok": True, "result": {"findings": [too_low]}})["correct"]
        assert evaluation.score(case, {"ok": True, "result": {"findings": []}})["disposition"] == "false-negative"
        invalid = sample_finding(case, line=999)
        assert not evaluation.score(case, {"ok": True, "result": {"findings": [invalid]}})["correct"]
        unrelated = sample_finding(case, text="Improve formatting and whitespace only.")
        assert not evaluation.score(case, {"ok": True, "result": {"findings": [unrelated]}})["correct"]
    for case in clean:
        assert evaluation.score(case, {"ok": True, "result": {"findings": []}})["correct"]
        assert not evaluation.score(
            case, {"ok": True, "result": {"findings": [{"title": "style", "path": case["focus_path"], "line": 1}]}}
        )["correct"]

    with patch.object(evaluation.base, "call_openrouter", side_effect=AssertionError("unexpected network")):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "plan.json"
            rc = evaluation.main([
                "--candidate", "sonnet5.5-high",
                "--case", "stale-tracked-source-inventory-p1",
                "--case", "fresh-tracked-inventory-verified",
                "--max-requests", "4",
                "--output", str(path),
            ])
            assert rc == 0
            report = json.loads(path.read_text(encoding="utf-8"))
            assert report["mode"] == "plan"
            assert report["network_requests_made"] == 0
            assert report["planned_requests"] == 4
            assert report["results"] == []
        try:
            evaluation.main([
                "--execute-live",
                "--case", "stale-tracked-source-inventory-p1",
                "--max-requests", "2",
                "--max-cost-usd", "0.5",
            ])
        except SystemExit as exc:
            assert "--operator-approved" in str(exc)
        else:
            raise AssertionError("Live request was not approval-gated")
    print("PASS: Issue618 paired first-pass evaluation selftest, no network")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
