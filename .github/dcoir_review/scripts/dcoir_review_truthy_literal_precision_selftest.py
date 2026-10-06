#!/usr/bin/env python3
"""Regression checks for stable DCOIR Review truthy-literal precision."""

from __future__ import annotations

import importlib

from dcoir_review.entrypoint import DcoirReviewEntrypoint


def _diff(path: str, line: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        "index 0000000..1111111 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -0,0 +1 @@\n"
        f"+{line}\n"
    )


def _has_truthy_sentinel(review, labels: set[str] | frozenset[str], path: str, line: str) -> bool:
    return any(item.label in labels for item in review.detect_risk_sentinels(_diff(path, line)))


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert entrypoint.patch_module_names[-1] == "dcoir_review.truthy_literal_precision"

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v20 = importlib.import_module("dcoir_review_required_runtime_patch_v20")
    truthy = importlib.import_module("dcoir_review.truthy_literal_precision")

    assert truthy.RAW_TRUTHY_LABEL in truthy.TRUTHY_LABELS
    assert truthy.CANONICAL_TRUTHY_LABEL in truthy.TRUTHY_LABELS
    assert truthy.CANONICAL_TRUTHY_LABEL == "Python branch condition contains an always-truthy literal"

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
        assert truthy.python_bare_truthy_or_operand(line) is False, line
        assert not _has_truthy_sentinel(review, truthy.TRUTHY_LABELS, "probe.py", line), line
        assert v20._line_kind("probe.py", line) != v20.PYTHON_TRUTHY_LITERAL_BRANCH, line

    invalid_python = [
        'if severity == "critical" or "high": return True',
        'if ready or ("fallback"): return True',
        'while ready or "continue":',
        'elif ready or "fallback":',
    ]
    for line in invalid_python:
        assert truthy.python_bare_truthy_or_operand(line) is True, line
        assert _has_truthy_sentinel(review, truthy.TRUTHY_LABELS, "probe.py", line), line
        assert v20._line_kind("probe.py", line) == v20.PYTHON_TRUTHY_LITERAL_BRANCH, line

    # A line that the Python parser cannot safely classify must not be silently
    # suppressed; fail-closed behavior preserves the pre-precision risk signal.
    unparsable = 'if ready or "fallback": ???'
    assert truthy.python_bare_truthy_or_operand(unparsable) is None
    assert _has_truthy_sentinel(review, truthy.TRUTHY_LABELS, "probe.py", unparsable)

    # PowerShell remains governed by the comparison-aware detector and can
    # still use the raw hardened label rather than the Python canonical title.
    assert not _has_truthy_sentinel(review, truthy.TRUTHY_LABELS, "probe.ps1", 'if ($Ready -or "Critical" -eq $Severity) { return $true }')
    assert _has_truthy_sentinel(review, truthy.TRUTHY_LABELS, "probe.ps1", 'if ($Ready -or "Critical") { return $true }')

    detector_before = review.detect_risk_sentinels
    line_kind_before = v20._line_kind
    truthy.apply_pareto_context_module(review)
    truthy.apply_pareto_context_module(review)
    assert review.detect_risk_sentinels is detector_before
    assert v20._line_kind is line_kind_before

    print("dcoir_review_truthy_literal_precision_selftest passed")


if __name__ == "__main__":
    main()
