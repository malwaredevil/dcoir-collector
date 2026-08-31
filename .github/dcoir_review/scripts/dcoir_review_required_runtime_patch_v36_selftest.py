#!/usr/bin/env python3
"""Regression checks for DCOIR Review v36 coordinated repair sets."""

from __future__ import annotations

import importlib
from pathlib import Path

from dcoir_review.entrypoint import DcoirReviewEntrypoint


def _edit(path: str, start: int, end: int, original: str, replacement: str, purpose: str = "fix") -> dict:
    return {
        "path": path,
        "start_line": start,
        "end_line": end,
        "original": original,
        "replacement": replacement,
        "purpose": purpose,
    }


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    names = entrypoint.patch_module_names
    assert "dcoir_review_required_runtime_patch_v36" in names
    assert names.index("dcoir_review_required_runtime_patch_v35") < names.index("dcoir_review_required_runtime_patch_v36")
    assert names.index("dcoir_review_required_runtime_patch_v36") < names.index("dcoir_review_required_runtime_patch_v31")

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v25 = importlib.import_module("dcoir_review_required_runtime_patch_v25")
    v30 = importlib.import_module("dcoir_review_required_runtime_patch_v30")
    v36 = importlib.import_module("dcoir_review_required_runtime_patch_v36")
    assert getattr(review, v36.APPLIED_MARKER, False) is True
    assert hasattr(review, "build_review_comments_for_finding")

    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    assert config.debug is False
    assert set(v36.REPAIR_SET_AUTHOR_SCHEMA["properties"]["action"]["enum"]) == {"repair_set", "no_safe_repair"}
    assert v36.REPAIR_SET_AUTHOR_SCHEMA["properties"]["edits"]["maxItems"] >= 3
    source = Path(".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v36.py").read_text(encoding="utf-8")
    for phrase in ("contiguous multi-line block", "non-contiguous ranges", "several files", "exact current text"):
        assert phrase in source
    for forbidden in ("git push", "create_commit(", "update_file(", "merge_pull_request"):
        assert forbidden not in source

    files = {"probe.py": "x = 1\ny = 2\nz = x + y\n"}
    edits = [_edit("probe.py", 1, 2, "x = 1\ny = 2", "x = 2\ny = 3", "correct both inputs")]
    updated, reason = v36._apply_edits_to_files(files, edits)
    assert reason == ""
    assert updated["probe.py"].startswith("x = 2\ny = 3\n")

    edits = [
        _edit("probe.py", 1, 1, "x = 1", "x = 10", "first range"),
        _edit("probe.py", 3, 3, "z = x + y", "z = (x + y) * 2", "second range"),
    ]
    updated, reason = v36._apply_edits_to_files(files, edits)
    assert reason == ""
    assert "x = 10" in updated["probe.py"] and "* 2" in updated["probe.py"]

    files2 = {"a.py": "VALUE = 1\n", "b.py": "from a import VALUE\nRESULT = VALUE\n"}
    edits2 = [
        _edit("a.py", 1, 1, "VALUE = 1", "VALUE = 2", "producer"),
        _edit("b.py", 2, 2, "RESULT = VALUE", "RESULT = VALUE * 2", "consumer"),
    ]
    updated, reason = v36._apply_edits_to_files(files2, edits2)
    assert reason == "" and set(updated) == {"a.py", "b.py"}

    overlapping = [
        _edit("probe.py", 1, 2, "x = 1\ny = 2", "x = 2\ny = 3"),
        _edit("probe.py", 2, 3, "y = 2\nz = x + y", "y = 4\nz = x + y"),
    ]
    _updated, reason = v36._apply_edits_to_files(files, overlapping)
    assert "overlapping" in reason
    stale = [_edit("probe.py", 1, 1, "x = 999", "x = 2")]
    _updated, reason = v36._apply_edits_to_files(files, stale)
    assert "did not match exact head text" in reason
    broken = [_edit("probe.py", 1, 1, "x = 1", "if (")]
    _updated, reason = v36._apply_edits_to_files(files, broken)
    assert "Python syntax invalid" in reason

    right_lines = {("probe.py", 1): 1, ("probe.py", 2): 2, ("probe.py", 3): 3, ("other.py", 5): 4}
    annotated = v36._annotate_native_eligibility(
        [
            _edit("probe.py", 1, 3, "a\nb\nc", "d\ne\nf"),
            _edit("other.py", 5, 5, "old", "new"),
            _edit("outside.py", 9, 9, "old", "new"),
        ],
        right_lines,
    )
    assert [item["native_suggestion"] for item in annotated] == [True, True, False]

    finding = {
        "title": "Coordinated bug",
        "severity": "high",
        "confidence": 0.98,
        "path": "probe.py",
        "line": 2,
        "body": "The verified defect requires coordinated edits.",
        "validation": "python3 -m py_compile probe.py",
        v25.REPAIR_MARKER: {
            "version": v36.VERSION,
            "outcome": v36.REPAIR_SET_OUTCOME,
            "repair_set_id": "R01",
            "edits": annotated,
        },
    }
    comments = v36.build_review_comments_for_finding(review, finding, "model", config)
    assert len(comments) == 2
    assert comments[0]["path"] == "probe.py"
    assert comments[0]["start_line"] == 1 and comments[0]["line"] == 3
    assert comments[0]["start_side"] == "RIGHT" and comments[0]["side"] == "RIGHT"
    assert "```suggestion\nd\ne\nf\n```" in comments[0]["body"]
    assert "outside.py:9-9" in comments[0]["body"]
    assert comments[1]["path"] == "other.py" and comments[1]["line"] == 5
    assert "start_line" not in comments[1]

    absent_author = {
        "defect_present": False,
        "confidence": 0.99,
        "display_title": "No defect",
        "display_body": "The alleged defect is absent.",
    }
    suppressed = v36._declined_item(finding, absent_author, "exact evidence disproves the claim")
    assert suppressed[v25.REPAIR_MARKER]["outcome"] == v30.SUPPRESSED_OUTCOME

    publisher_before = review.build_review_comments_for_finding
    synth_before = v25.synthesize_verified_repairs
    v36.apply_pareto_context_module(review)
    assert review.build_review_comments_for_finding is publisher_before
    assert v25.synthesize_verified_repairs is synth_before

    print("dcoir_review_required_runtime_patch_v36_selftest passed")


if __name__ == "__main__":
    main()
