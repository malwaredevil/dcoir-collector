#!/usr/bin/env python3
"""Regression checks for DCOIR Review v27 exact-anchor preservation."""

from __future__ import annotations

import importlib

from dcoir_review.entrypoint import DcoirReviewEntrypoint


PATH = ".github/dcoir_review/evaluation/live_verifier_probe.py"


def patched_review():
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    return review


def probe_diff() -> str:
    lines = [
        '"""TEST ONLY - NEVER MERGE: controlled DCOIR Review verifier probe.',
        "",
        "This file intentionally contains one deterministic semantic bug that should be",
        "found by ordinary model review, not by a high-risk sentinel. The function's",
        "contract is explicit so a verifier can judge the finding against full-file",
        "context and the exact changed line.",
        '"""',
        "",
        "",
        "def is_recent(age_minutes: int) -> bool:",
        '    """Return True when age_minutes is between 0 and 60 inclusive."""',
        "    return age_minutes >= 0 and age_minutes >= 60",
    ]
    body = "\n".join("+" + line for line in lines)
    return (
        f"diff --git a/{PATH} b/{PATH}\n"
        "new file mode 100644\n"
        "index 0000000..1111111\n"
        "--- /dev/null\n"
        f"+++ b/{PATH}\n"
        "@@ -0,0 +1,12 @@\n"
        f"{body}\n"
    )


def test_exact_postable_anchor_survives_review_body_fallback(review) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    diff = probe_diff()
    line_index = review.hardened.build_added_line_index(diff)
    result = {
        "summary": "Identified a correctness bug in the range check.",
        "findings": [
            {
                "title": "Inverted upper-bound comparison in is_recent",
                "severity": "medium",
                "confidence": 0.99,
                "path": PATH,
                "line": 12,
                "body": (
                    "is_recent uses age_minutes >= 60 instead of age_minutes <= 60, "
                    "violating the documented inclusive range."
                ),
                "suggested_replacement": "",
                "validation": "python3 -m py_compile .github/dcoir_review/evaluation/live_verifier_probe.py",
            }
        ],
    }
    findings, unanchored = review.split_findings_with_review_body_fallback(
        result,
        config,
        line_index,
        diff,
        [],
    )
    assert not unanchored, unanchored
    assert len(findings) == 1, findings
    assert findings[0]["line"] == 12, findings
    assert findings[0].get("_reanchored_from_line") is None, findings


def test_valid_anchor_is_immutable_even_when_adjacent_prose_scores_higher(review) -> None:
    diff = probe_diff()
    line_index = review.hardened.build_added_line_index(diff)
    changed_lines_by_path = {PATH: list(review.hardened.iter_added_diff_lines(diff))}
    finding = {
        "title": "Inclusive range boundary finding",
        "body": "The documented inclusive age_minutes range is violated by the upper-bound comparison.",
        "path": PATH,
        "line": 12,
        "confidence": 0.99,
    }
    anchored = review.reanchor_finding_to_changed_line(
        finding,
        line_index,
        changed_lines_by_path,
        [],
    )
    assert anchored["line"] == 12, anchored
    assert anchored.get("_reanchored_from_line") is None, anchored


def main() -> None:
    review = patched_review()
    test_exact_postable_anchor_survives_review_body_fallback(review)
    test_valid_anchor_is_immutable_even_when_adjacent_prose_scores_higher(review)
    print("dcoir_review_required_runtime_patch_v27_selftest passed")


if __name__ == "__main__":
    main()
