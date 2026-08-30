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
    assert "dcoir_review_required_runtime_patch_v31" in names
    assert names.index("dcoir_review_required_runtime_patch_v30") < names.index("dcoir_review_required_runtime_patch_v31")
    assert names[-1] == "dcoir_review_required_runtime_patch_v31", names[-4:]

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v20 = importlib.import_module("dcoir_review_required_runtime_patch_v20")
    v21 = importlib.import_module("dcoir_review_required_runtime_patch_v21")
    v25 = importlib.import_module("dcoir_review_required_runtime_patch_v25")
    v28 = importlib.import_module("dcoir_review_required_runtime_patch_v28")
    v30 = importlib.import_module("dcoir_review_required_runtime_patch_v30")

    # Applying only the v30 overlay again in a reused interpreter must be a no-op
    # rather than stacking prompt/parser/synthesis/renderer wrappers.
    prompt_before = v25._repair_author_prompt
    author_result_before = v28._author_result
    declined_before = v28._declined_item
    synthesis_before = review.synthesize_fixes_for_findings
    renderer_before = review.base.build_inline_comment
    v30.apply_pareto_context_module(review)
    v30.apply_pareto_context_module(review)
    assert v25._repair_author_prompt is prompt_before
    assert v28._author_result is author_result_before
    assert v28._declined_item is declined_before
    assert review.synthesize_fixes_for_findings is synthesis_before
    assert review.base.build_inline_comment is renderer_before

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

    # The final renderer must ignore model-authored semantics for a verifier-
    # proven deterministic sentinel while preserving the human-applied native
    # GitHub suggestion produced by the verified repair pipeline.
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    deterministic = {
        "title": "model wording should not replace deterministic sentinel template",
        "severity": "high",
        "confidence": 0.99,
        "path": ".github/dcoir_review/evaluation/live_suggestion_probe.py",
        "line": 10,
        "body": "model body should not replace deterministic sentinel detail",
        "suggested_replacement": '    if severity in {"critical", "high"}:',
        "_anchored_line_text": '    if severity == "critical" or "high":',
        "_risk_sentinel_key": [
            ".github/dcoir_review/evaluation/live_suggestion_probe.py",
            10,
            v20.PYTHON_TRUTHY_LITERAL_BRANCH,
        ],
        "_risk_sentinel_kind": v20.PYTHON_TRUTHY_LITERAL_BRANCH,
        v21.VERIFIER_MARKER: {
            "mode": "deterministic-core-sentinel",
            "supported": True,
            "kind": v20.PYTHON_TRUTHY_LITERAL_BRANCH,
            "head_sha": "probe-head",
            "line": 10,
        },
        v25.REPAIR_MARKER: {
            "version": v30.VERSION,
            "outcome": "native-suggestion",
            "path": ".github/dcoir_review/evaluation/live_suggestion_probe.py",
            "line": 10,
        },
    }
    rendered = review.base.build_inline_comment(deterministic, "test-model", config)
    assert "Python branch condition contains an always-truthy literal" in rendered
    assert "A non-empty string literal after `or` is always truthy" in rendered
    assert "model wording should not replace deterministic sentinel template" not in rendered
    assert "model body should not replace deterministic sentinel detail" not in rendered
    assert '```suggestion\n    if severity in {"critical", "high"}:\n```' in rendered

    # A verifier-supported ordinary model finding remains model-authored; v30
    # canonicalization is deliberately scoped to deterministic-core-sentinel.
    ordinary = {
        "title": "Verified ordinary title",
        "severity": "medium",
        "confidence": 0.99,
        "path": "probe.py",
        "line": 3,
        "body": "Verified ordinary body.",
        "suggested_replacement": "",
        v21.VERIFIER_MARKER: {
            "mode": "model-judge",
            "supported": True,
            "confidence": 0.99,
            "evidence": "The exact line contradicts the documented boundary.",
            "head_sha": "probe-head",
            "line": 3,
        },
    }
    ordinary_rendered = review.base.build_inline_comment(ordinary, "test-model", config)
    assert "Verified ordinary title" in ordinary_rendered
    assert "Verified ordinary body." in ordinary_rendered

    print("dcoir_review_required_runtime_patch_v30_selftest passed")


if __name__ == "__main__":
    main()
