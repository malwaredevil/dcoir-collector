#!/usr/bin/env python3
"""Regression checks for DCOIR Review v31 structural truthy-literal filtering."""

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
    assert entrypoint.patch_module_names[-1] == "dcoir_review_required_runtime_patch_v31"

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v20 = importlib.import_module("dcoir_review_required_runtime_patch_v20")
    v31 = importlib.import_module("dcoir_review_required_runtime_patch_v31")

    valid_python = [
        'if not ("local" in clause or "workstation" in clause):',
        'if ready or "x" in allowed: return True',
        'if ready or "x" not in allowed: return True',
        'if ready or "x" == candidate: return True',
        'if ready or "x" != candidate: return True',
        'if ready or "x" is candidate: return True',
        'if ready or "x" is not candidate: return True',
        'if ready or "x" < candidate: return True',
        'if ready or "x" >= candidate: return True',
        'elif ready or "x" not in allowed:',
    ]
    for line in valid_python:
        assert v31.python_bare_truthy_or_operand(line) is False, line
        assert not _has_truthy_sentinel(review, "probe.py", line), line
        assert v20._line_kind("probe.py", line) != v20.PYTHON_TRUTHY_LITERAL_BRANCH, line

    invalid_python = [
        'if severity == "critical" or "high": return True',
        'if ready or ("fallback"): return True',
        'while ready or "continue":',
        'elif ready or "fallback":',
    ]
    for line in invalid_python:
        assert v31.python_bare_truthy_or_operand(line) is True, line
        assert _has_truthy_sentinel(review, "probe.py", line), line
        assert v20._line_kind("probe.py", line) == v20.PYTHON_TRUTHY_LITERAL_BRANCH, line

    # A line that the Python parser cannot safely classify must not be silently
    # suppressed; fail-closed behavior preserves the pre-v31 risk signal.
    unparsable = 'if ready or "fallback": ???'
    assert v31.python_bare_truthy_or_operand(unparsable) is None
    assert _has_truthy_sentinel(review, "probe.py", unparsable)

    # PowerShell remains governed by the comparison-aware v30 detector.
    assert not _has_truthy_sentinel(review, "probe.ps1", 'if ($Ready -or "Critical" -eq $Severity) { return $true }')
    assert _has_truthy_sentinel(review, "probe.ps1", 'if ($Ready -or "Critical") { return $true }')

    detector_before = review.detect_risk_sentinels
    line_kind_before = v20._line_kind
    v31.apply_pareto_context_module(review)
    v31.apply_pareto_context_module(review)
    assert review.detect_risk_sentinels is detector_before
    assert v20._line_kind is line_kind_before

    print("dcoir_review_required_runtime_patch_v31_selftest passed")


if __name__ == "__main__":
    main()
