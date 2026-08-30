#!/usr/bin/env python3
"""Regression checks for DCOIR Review v30 false-positive precision."""

from __future__ import annotations

import importlib

from dcoir_review.entrypoint import DcoirReviewEntrypoint


TRUTHY_LABEL = "truthy literal branch condition"


def _diff(path: str, line: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        "index 0000000..1111111 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -0,0 +1 @@\n"
        f"+{line}\n"
    )


def _has_truthy_sentinel(review, path: str, line: str) -> bool:
    return any(item.label == TRUTHY_LABEL for item in review.detect_risk_sentinels(_diff(path, line)))


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    names = entrypoint.patch_module_names
    assert "dcoir_review_required_runtime_patch_v30" in names
    assert names[-1] == "dcoir_review_required_runtime_patch_v30", names[-4:]

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v25 = importlib.import_module("dcoir_review_required_runtime_patch_v25")
    v28 = importlib.import_module("dcoir_review_required_runtime_patch_v28")
    v30 = importlib.import_module("dcoir_review_required_runtime_patch_v30")

    valid_python = [
        'if len(rejected) != 1 or "fallback_emulation" not in rejected[0].get("reason", ""): raise SystemExit()',
        'if ready or "x" in allowed: return True',
        'if ready or "x" not in allowed: return True',
        'if ready or "x" == candidate: return True',
        'if ready or "x" != candidate: return True',
        'if ready or "x" is candidate: return True',
        'if ready or "x" is not candidate: return True',
        'if ready or "x" < candidate: return True',
        'if ready or "x" >= candidate: return True',
    ]
    for line in valid_python:
        assert not _has_truthy_sentinel(review, "probe.py", line), line

    valid_powershell = [
        'if ($Ready -or "Critical" -eq $Severity) { return $true }',
        'if ($Ready -or "Critical" -ne $Severity) { return $true }',
        'if ($Ready -or "Critical" -in $Allowed) { return $true }',
        'if ($Ready -or "Critical" -notin $Blocked) { return $true }',
        'if ($Ready -or "Critical" -like $Pattern) { return $true }',
    ]
    for line in valid_powershell:
        assert not _has_truthy_sentinel(review, "probe.ps1", line), line

    assert _has_truthy_sentinel(review, "probe.py", 'if severity == "critical" or "high": return True')
    assert _has_truthy_sentinel(review, "probe.ps1", 'if ($Severity -eq "High" -or "Critical") { return $true }')

    assert "defect_present" in v25.REPAIR_AUTHOR_SCHEMA["required"]
    assert v25.REPAIR_AUTHOR_SCHEMA["properties"]["defect_present"] == {"type": "boolean"}

    class Hardened:
        class ReviewQualityError(RuntimeError):
            pass

    finding = {
        "path": "probe.py",
        "line": 1,
        "title": "Alleged truthy literal",
        "body": "The quoted operand was alleged to be a bare truthy literal.",
        "severity": "high",
        "confidence": 0.99,
    }
    absent_raw = {
        "defect_present": False,
        "action": "no_safe_single_line_fix",
        "replacement": "",
        "confidence": 0.99,
        "display_title": "No defect present",
        "display_body": "The quoted value is the left operand of a not-in membership test.",
        "rationale": "The exact syntax is a boolean membership expression, not a bare literal operand.",
        "validation": "python3 -m py_compile probe.py",
    }
    absent_author = v28._author_result(absent_raw, finding, "probe.py", 1, Hardened)
    assert absent_author["defect_present"] is False
    assert absent_author["action"] == "no_safe_single_line_fix"
    assert absent_author["replacement"] == ""

    suppressed = v28._declined_item(
        finding,
        "probe.py",
        1,
        absent_author["rationale"],
        author=absent_author,
        author_model="test-author",
        author_tier="test",
        outcome="author-declined",
    )
    assert suppressed[v25.REPAIR_MARKER]["outcome"] == v30.SUPPRESSED_OUTCOME
    assert suppressed[v25.REPAIR_MARKER]["defect_present"] is False
    kept, count = v30.filter_suppressed_findings([suppressed])
    assert kept == []
    assert count == 1

    real_raw = {
        "defect_present": True,
        "action": "no_safe_single_line_fix",
        "replacement": "",
        "confidence": 0.99,
        "display_title": "Real multi-line issue",
        "display_body": "The defect is real but cannot be repaired safely on one line.",
        "rationale": "A declaration and an adjacent call site must both change.",
        "validation": "python3 -m py_compile probe.py",
    }
    real_author = v28._author_result(real_raw, finding, "probe.py", 1, Hardened)
    real_item = v28._declined_item(
        finding,
        "probe.py",
        1,
        real_author["rationale"],
        author=real_author,
        author_model="test-author",
        author_tier="test",
        outcome="author-declined",
    )
    kept, count = v30.filter_suppressed_findings([real_item])
    assert count == 0
    assert len(kept) == 1
    assert kept[0][v25.REPAIR_MARKER]["outcome"] == "author-declined"

    low_confidence_raw = dict(absent_raw)
    low_confidence_raw["confidence"] = 0.80
    low_author = v28._author_result(low_confidence_raw, finding, "probe.py", 1, Hardened)
    low_item = v28._declined_item(
        finding,
        "probe.py",
        1,
        low_author["rationale"],
        author=low_author,
        author_model="test-author",
        author_tier="test",
        outcome="author-declined",
    )
    kept, count = v30.filter_suppressed_findings([low_item])
    assert count == 0
    assert len(kept) == 1
    assert kept[0][v25.REPAIR_MARKER].get("suppression_declined")

    print("dcoir_review_required_runtime_patch_v30_selftest passed")


if __name__ == "__main__":
    main()
